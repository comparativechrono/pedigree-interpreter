import json
import subprocess
import sys

import pandas as pd
import pytest
from PIL import Image

from PedInterp import GA4GH_export, PED_export, pedigree_processing
from PedInterp.cli import main
from test_core import (COLUMNS, THREE_GENERATIONS, THREE_GENERATIONS_NUMBERED, TWO_GENERATIONS,
                       TWO_GENERATIONS_NUMBERED, draw_pedigree, needs_tesseract)


def read_ped(path):
    return pd.read_csv(path, sep='\t', header=None, dtype=str, names=['FamilyID'] + COLUMNS)


def test_writes_what_the_python_functions_write(tmp_path, capsys):
    draw_pedigree(tmp_path / 'FAMP.png', *THREE_GENERATIONS, labels=False)
    assert main([str(tmp_path / 'FAMP.png'), '-d', str(tmp_path / 'cli'), '--labels', 'none']) == 0
    expected = PED_export(pedigree_processing('FAMP', image_path=str(tmp_path / 'FAMP.png'), ocr=None),
                          str(tmp_path / 'python'))
    assert (tmp_path / 'cli' / 'FAMP.ped').read_text() == open(expected).read()
    assert read_ped(tmp_path / 'cli' / 'FAMP.ped')[COLUMNS].values.tolist() == THREE_GENERATIONS_NUMBERED
    out = capsys.readouterr().out
    assert 'IndividualID' in out and 'III-3' in out
    assert out.strip().endswith(f"wrote {tmp_path / 'cli' / 'FAMP.ped'}")


def without_times(doc):
    # a GA4GH file as written, but for when
    doc = dict(doc, date=None)
    doc['individuals'] = [dict(i, metaData=dict(i['metaData'], created=None)) for i in doc['individuals']]
    return doc


def test_ga4gh(tmp_path, capsys):
    # --ga4gh writes a GA4GH Pedigree too, as GA4GH_export does, with the condition given
    draw_pedigree(tmp_path / 'FAMP.png', *THREE_GENERATIONS, labels=False)
    assert main([str(tmp_path / 'FAMP.png'), '-d', str(tmp_path / 'cli'), '--labels', 'none', '-q', '--ga4gh',
                 '--condition', 'MONDO:0007739', 'Huntington disease']) == 0
    assert capsys.readouterr().out.splitlines()[-1] == f"wrote {tmp_path / 'cli'}/FAMP_ga4gh-pedigree.json"
    df = pedigree_processing('FAMP', image_path=str(tmp_path / 'FAMP.png'), ocr=None)
    expected = GA4GH_export(df, str(tmp_path / 'python'), condition=('MONDO:0007739', 'Huntington disease'))
    doc = json.loads((tmp_path / 'cli' / 'FAMP_ga4gh-pedigree.json').read_text())
    assert without_times(doc) == without_times(json.load(open(expected)))
    assert (tmp_path / 'cli' / 'FAMP.ped').exists()


def test_condition_errors(tmp_path, capsys):
    # --condition belongs to --ga4gh, and must be a term a GA4GH file can name; nothing is read or written otherwise
    draw_pedigree(tmp_path / 'FAMP.png', *TWO_GENERATIONS, labels=False)
    out = tmp_path / 'out'
    assert main([str(tmp_path / 'FAMP.png'), '--labels', 'none', '-d', str(out), '--condition', 'MONDO:0007739', 'HD']) == 1
    assert '--ga4gh' in capsys.readouterr().err
    assert main([str(tmp_path / 'FAMP.png'), '--labels', 'none', '-d', str(out), '--ga4gh', '--condition', 'HD', 'Huntington']) == 1
    assert 'ontology term' in capsys.readouterr().err
    assert not out.exists()


def test_family_named_after_the_picture(tmp_path, monkeypatch, capsys):
    draw_pedigree(tmp_path / 'my family.jpg', *TWO_GENERATIONS, labels=False, quality=95)
    monkeypatch.chdir(tmp_path)
    assert main(['my family.jpg', '--labels', 'none', '-q']) == 0
    ped = read_ped(tmp_path / 'my_family.ped')
    assert set(ped['FamilyID']) == {'my_family'}
    assert ped[COLUMNS].values.tolist() == TWO_GENERATIONS_NUMBERED
    # -q leaves out the table, but not the file's name
    assert capsys.readouterr().out == 'wrote ./my_family.ped\n'


def test_family_option(tmp_path):
    draw_pedigree(tmp_path / 'scan.png', *TWO_GENERATIONS, labels=False)
    assert main([str(tmp_path / 'scan.png'), '-f', 'FAM9', '-d', str(tmp_path), '--labels', 'none']) == 0
    assert set(read_ped(tmp_path / 'FAM9.ped')['FamilyID']) == {'FAM9'}
    assert not (tmp_path / 'scan.ped').exists()


@pytest.mark.parametrize('family', ['FAM 9', ''])
def test_family_with_a_space(tmp_path, family, capsys):
    draw_pedigree(tmp_path / 'scan.png', *TWO_GENERATIONS, labels=False)
    assert main([str(tmp_path / 'scan.png'), '-f', family, '--labels', 'none']) == 1
    assert 'must be a word with no spaces' in capsys.readouterr().err


def test_upscale(tmp_path):
    draw_pedigree(tmp_path / 'small.png', *THREE_GENERATIONS, labels=False)
    small = Image.open(tmp_path / 'small.png')
    small.resize((small.width * 3, small.height * 3), Image.LANCZOS).save(tmp_path / 'large.png')
    assert main([str(tmp_path / 'large.png'), '-d', str(tmp_path), '--labels', 'none', '--upscale', '3.0']) == 0
    assert read_ped(tmp_path / 'large.ped')[COLUMNS].values.tolist() == THREE_GENERATIONS_NUMBERED


def test_says_how_much_it_enlarged_the_picture(tmp_path, capsys):
    draw_pedigree(tmp_path / 'p.png', *THREE_GENERATIONS, labels=False)
    factor = pedigree_processing('P', image_path=str(tmp_path / 'p.png'), ocr=None).attrs['upscale_factor']
    assert main([str(tmp_path / 'p.png'), '-d', str(tmp_path), '--labels', 'none']) == 0
    assert f'(the picture was read enlarged {factor:g} times)' in capsys.readouterr().out
    assert main([str(tmp_path / 'p.png'), '-d', str(tmp_path), '--labels', 'none', '-q']) == 0
    assert 'the picture was read enlarged' not in capsys.readouterr().out


@pytest.mark.parametrize('factor', ['0', '-2', 'ten', 'nan'])
def test_upscale_must_be_a_positive_number(tmp_path, factor, capsys):
    with pytest.raises(SystemExit) as stopped:
        main([str(tmp_path / 'x.png'), '--upscale', factor])
    assert stopped.value.code == 2
    assert 'expected a number' in capsys.readouterr().err


def test_no_such_picture(tmp_path, capsys):
    assert main([str(tmp_path / 'missing.png')]) == 1
    assert 'missing.png: no such file' in capsys.readouterr().err


def test_not_a_picture(tmp_path, capsys):
    (tmp_path / 'notes.png').write_text('not a picture')
    assert main([str(tmp_path / 'notes.png'), '--labels', 'none']) == 1
    assert capsys.readouterr().err.startswith('pedinterp: ')
    assert not (tmp_path / 'notes.ped').exists()


def test_no_pedigree_in_the_picture(tmp_path, capsys):
    Image.new('RGB', (300, 200), 'white').save(tmp_path / 'blank.png')
    assert main([str(tmp_path / 'blank.png'), '-d', str(tmp_path), '--labels', 'none']) == 1
    assert 'No pedigree symbols were found' in capsys.readouterr().err
    assert not (tmp_path / 'blank.ped').exists()


def test_without_pytesseract(tmp_path, monkeypatch, capsys):
    # asked to read the labels when they can't be, it numbers the people, and says how to do that without the warning
    monkeypatch.setitem(sys.modules, 'pytesseract', None)
    draw_pedigree(tmp_path / 'FAMC.png', *TWO_GENERATIONS)
    assert main([str(tmp_path / 'FAMC.png'), '-d', str(tmp_path), '-q']) == 0
    err = capsys.readouterr().err
    assert "warning: The labels can't be read with Tesseract" in err
    assert 'Give --labels none' in err and 'ocr=None' not in err
    assert read_ped(tmp_path / 'FAMC.ped')[COLUMNS].values.tolist() == TWO_GENERATIONS_NUMBERED


@needs_tesseract
def test_reads_the_labels(tmp_path):
    draw_pedigree(tmp_path / 'FAMC.png', *TWO_GENERATIONS)
    assert main([str(tmp_path / 'FAMC.png'), '-d', str(tmp_path)]) == 0
    assert read_ped(tmp_path / 'FAMC.ped')[COLUMNS].values.tolist() == [['101', '0', '0', '1', '2'],
                                                                         ['102', '0', '0', '2', '1'],
                                                                         ['201', '101', '102', '1', '2'],
                                                                         ['202', '101', '102', '2', '1']]


def test_runs_as_a_module():
    result = subprocess.run([sys.executable, '-m', 'PedInterp.cli', '--version'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith('pedinterp ')
