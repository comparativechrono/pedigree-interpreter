'''
Reading the marks drawn on the symbols (pedigree_processing(..., marks=True)): who has died, the proband and carriers,
in drawings made as Pedigree Studio makes them and in sketches; and writing them, as a PED file can't hold them.
'''
import json
import warnings

import cv2
import numpy as np
import pytest

from PedInterp import GA4GH_export, PED_export, Studio_export, pedigree_processing
from PedInterp.core import MARKS
from drawings import SHAPE, sketch_picture, studio_picture
from test_twins_and_sketches import RED, SKETCH, SKETCH_COUPLES, SKETCH_READ, SKETCH_TWINS

COLUMNS = ['IndividualID', 'PaternalID', 'MaternalID', 'Sex', 'Phenotype']

# a family drawn as Pedigree Studio draws it, with each kind of mark on symbols of each kind: slashes through symbols
# left empty and filled in (a circle's runs out past it), a dot in a symbol filled in (white) and in an empty one, and
# arrows at a symbol filled in and at an empty one
STUDIO = {'I-1': (308, 100, 'M', False), 'I-2': (516, 100, 'F', True),
          'II-1': (100, 360, 'F', False), 'II-2': (308, 360, 'M', True), 'II-3': (516, 360, 'F', False),
          'II-4': (724, 360, 'M', False),
          'III-1': (412, 620, 'F', True), 'III-2': (620, 620, 'U', False), 'III-3': (828, 620, 'M', False)}
STUDIO_COUPLES = [('I-1', 'I-2', ['II-1', 'II-2', 'II-3']), ('II-3', 'II-4', ['III-1', 'III-2', 'III-3'])]
STUDIO_MARKS = {'I-1': {'deceased'}, 'I-2': {'deceased'}, 'II-1': {'carrier'}, 'II-2': {'proband'},
                'II-3': {'deceased'}, 'II-4': {'deceased', 'carrier'}, 'III-1': {'carrier'}, 'III-2': {'deceased'},
                'III-3': {'proband'}}
STUDIO_READ = [['I-1', '0', '0', '1', '1'], ['I-2', '0', '0', '2', '2'],
               ['II-1', 'I-1', 'I-2', '2', '1'], ['II-2', 'I-1', 'I-2', '1', '2'], ['II-3', 'I-1', 'I-2', '2', '1'],
               ['II-4', '0', '0', '1', '1'],
               ['III-1', 'II-4', 'II-3', '2', '2'], ['III-2', 'II-4', 'II-3', '0', '1'],
               ['III-3', 'II-4', 'II-3', '1', '1']]

# the sketch of the twins' tests, with marks drawn on it by hand
SKETCH_MARKS = {'I-1': {'deceased'}, 'I-2': {'carrier'}, 'II-1': {'deceased'}, 'II-3': {'proband'},
                'II-5': {'deceased', 'carrier'}, 'III-2': {'proband'}}


def read(path, **options):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return pedigree_processing('FAMM', image_path=str(path), ocr=None, **options)


def rows(df):
    return [[str(value) for value in row] for row in df[COLUMNS].values.tolist()]


def marks_of(df):
    '''each person's marks, by ID, as the sets the drawings are made with'''
    names = {'Deceased': 'deceased', 'Proband': 'proband', 'Carrier': 'carrier'}
    return {str(row['IndividualID']): {names[column] for column in MARKS if row[column]}
            for _, row in df.iterrows() if any(row[column] for column in MARKS)}


@pytest.mark.parametrize('hand_drawn', [False, True])
def test_marks_in_a_studio_drawing(tmp_path, hand_drawn):
    studio_picture(tmp_path / 'marked.png', STUDIO, STUDIO_COUPLES, marks=STUDIO_MARKS)
    df = read(tmp_path / 'marked.png', marks=True, hand_drawn=hand_drawn)
    assert list(df.columns) == ['FamilyID', 'IndividualID', 'PaternalID', 'MaternalID', 'Sex', 'Phenotype'] + MARKS
    assert rows(df) == STUDIO_READ
    assert marks_of(df) == STUDIO_MARKS
    assert df[MARKS].dtypes.tolist() == [bool, bool, bool]


@pytest.mark.parametrize('seed, pen, width', [(0, RED, 4), (1, (26, 35, 50), 4), (2, (41, 128, 185), 3)])
def test_marks_in_a_sketch(tmp_path, seed, pen, width):
    sketch_picture(tmp_path / 'sketch.png', SKETCH, SKETCH_COUPLES, SKETCH_TWINS, seed=seed, pen=pen, width=width,
                   marks=SKETCH_MARKS)
    df = read(tmp_path / 'sketch.png', marks=True, hand_drawn=True)
    assert rows(df) == SKETCH_READ
    assert marks_of(df) == SKETCH_MARKS


def test_without_marks_nothing_is_read_of_them(tmp_path):
    # the table is as it always was, with nothing more in it, and the same as the start of the table read with marks
    studio_picture(tmp_path / 'marked.png', STUDIO, STUDIO_COUPLES, marks=STUDIO_MARKS)
    plain = read(tmp_path / 'marked.png')
    assert list(plain.columns) == ['FamilyID', 'IndividualID', 'PaternalID', 'MaternalID', 'Sex', 'Phenotype']
    marked = read(tmp_path / 'marked.png', marks=True)
    assert plain.equals(marked.drop(columns=MARKS))
    assert plain.attrs == marked.attrs


def test_no_marks_where_none_are_drawn(tmp_path):
    studio_picture(tmp_path / 'plain.png', STUDIO, STUDIO_COUPLES)
    df = read(tmp_path / 'plain.png', marks=True)
    assert rows(df) == STUDIO_READ
    assert not df[MARKS].values.any()


def test_letters_in_a_symbol_are_no_dot(tmp_path):
    # the Studio writes P (a pregnancy), D (a donor) or S (a surrogate) in a symbol, in the middle, where a dot would be
    studio_picture(tmp_path / 'letters.png', STUDIO, STUDIO_COUPLES,
                   inside={'II-1': 'P', 'II-2': 'D', 'II-3': 'S', 'III-2': 'P'})
    df = read(tmp_path / 'letters.png', marks=True)
    assert rows(df) == STUDIO_READ
    assert not df[MARKS].values.any()


def test_a_hatched_symbol_is_not_slashed(tmp_path):
    # a symbol hatched with lines rising to the right, as the slash does, has died no more than one left empty
    studio_picture(tmp_path / 'hatched.png', STUDIO, STUDIO_COUPLES)
    picture = cv2.imread(str(tmp_path / 'hatched.png'))
    x, y, *_ = STUDIO['II-1']
    hatching = np.zeros(picture.shape[:2], np.uint8)
    for k in range(-SHAPE, SHAPE, 14):
        cv2.line(hatching, (x + k, y + SHAPE), (x + k + SHAPE, y), 1, 3)
    inside = np.zeros_like(hatching)
    cv2.circle(inside, (x + SHAPE // 2, y + SHAPE // 2), SHAPE // 2 - 6, 1, -1)
    picture[(hatching & inside) > 0] = (50, 35, 26)
    cv2.imwrite(str(tmp_path / 'hatched.png'), picture)
    df = read(tmp_path / 'hatched.png', marks=True)
    assert not df.loc[df['IndividualID'] == 'II-1', 'Deceased'].item()


def test_a_ped_file_cannot_hold_the_marks(tmp_path):
    studio_picture(tmp_path / 'marked.png', STUDIO, STUDIO_COUPLES, marks=STUDIO_MARKS)
    df = read(tmp_path / 'marked.png', marks=True)
    with pytest.raises(ValueError, match="A PED file can't hold the marks"):
        PED_export(df, str(tmp_path))
    with pytest.raises(ValueError, match="A PED file can't hold the marks"):
        pedigree_processing('FAMM', image_path=str(tmp_path / 'marked.png'), ocr=None, marks=True, export=True,
                            output_dir=str(tmp_path))
    assert not list(tmp_path.glob('*.ped'))
    # (without the marks, it is a PED file's table again)
    assert PED_export(df.drop(columns=MARKS), str(tmp_path)) == f'{tmp_path}/FAMM.ped'


def test_ga4gh_pedigree_with_marks(tmp_path):
    studio_picture(tmp_path / 'marked.png', STUDIO, STUDIO_COUPLES, marks=STUDIO_MARKS)
    df = read(tmp_path / 'marked.png', marks=True)
    doc = json.load(open(GA4GH_export(df, str(tmp_path))))
    status = {p['subject']['id']: p['subject'].get('vitalStatus', {}).get('status') for p in doc['individuals']}
    assert status == {person: 'DECEASED' if 'deceased' in STUDIO_MARKS.get(person, ()) else 'ALIVE'
                      for person in status}
    assert doc['indexPatients'] == ['II-2', 'III-3']
    assert '; proband II-2, III-3.' in doc['narrative']
    assert doc['narrative'].endswith('Deaths, probands and carriers were read from the marks drawn on the symbols. '
                                     'II-1 is a carrier. II-4 is a carrier. III-1 is a carrier.')
    # without marks, as before: no vital status, and no index patient
    plain = json.load(open(GA4GH_export(read(tmp_path / 'marked.png'), str(tmp_path / 'plain'))))
    assert not any('vitalStatus' in p['subject'] for p in plain['individuals'])
    assert 'indexPatients' not in plain
    assert 'carrier' not in plain['narrative']


def test_studio_drawing_with_marks(tmp_path):
    sketch_picture(tmp_path / 'sketch.png', SKETCH, SKETCH_COUPLES, SKETCH_TWINS, seed=0, pen=RED, width=4,
                   marks=SKETCH_MARKS)
    df = read(tmp_path / 'sketch.png', marks=True, hand_drawn=True)
    drawing = json.load(open(Studio_export(df, str(tmp_path))))
    ids = [str(p) for p in df['IndividualID']]
    people = {ids[k]: p for k, p in enumerate(drawing['persons'][:len(ids)])}
    drawn = {person: {mark for mark, on in (('deceased', p['deceased']), ('proband', p['proband']),
                                            ('carrier', p['centerText'] == 'dot')) if on}
             for person, p in people.items()}
    assert {person: m for person, m in drawn.items() if m} == SKETCH_MARKS
    # studio2ga4gh reads them back from the drawing (and a pregnancy lost, III-3's triangle, is one who has died)
    studio2ga4gh = pytest.importorskip('studio2ga4gh')
    kindred, = studio2ga4gh.convert(drawing).kindreds
    by_number = {p['id']: person for person, p in people.items()}
    members = {by_number.get(m.id, m.id): m for m in kindred.members}
    assert {person for person, m in members.items() if m.vital_status == 'DECEASED'} == \
        {person for person, m in SKETCH_MARKS.items() if 'deceased' in m} | {'III-3'}
    assert {person for person, m in members.items() if m.index} == \
        {person for person, m in SKETCH_MARKS.items() if 'proband' in m}
