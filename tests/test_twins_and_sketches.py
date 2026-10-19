'''
Twins, labels written against lines, and pedigrees sketched by hand: drawn as Pedigree Studio draws them and as
people sketch them with its Draw tool (see drawings.py), and read with people numbered (ocr=None).
'''
import json
import warnings

import pandas as pd
import pytest
from PIL import Image

import PedInterp.core as core
from PedInterp import GA4GH_export, pedigree_processing
from PedInterp.core import twin_groups
from drawings import sketch_picture, studio_picture

COLUMNS = ['IndividualID', 'PaternalID', 'MaternalID', 'Sex', 'Phenotype']


def read(path, **options):
    '''the rows read from a picture, its twins and the warnings given'''
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        df = pedigree_processing('FAMT', image_path=str(path), ocr=None, **options)
    rows = [[str(value) for value in row] for row in df[COLUMNS].values.tolist()]
    return rows, df.attrs['twins'], [str(w.message) for w in caught]


# ---------------------------------------------------------------------------------------------------------------------
# twins, as Pedigree Studio draws them
# ---------------------------------------------------------------------------------------------------------------------
# two brothers who are twins between their sisters, one of whom has married and has a daughter
TWINS = {'I-1': (300, 60, 'M', True), 'I-2': (520, 60, 'F', False),
         'II-1': (120, 300, 'F', False), 'II-2': (320, 300, 'M', True), 'II-3': (500, 300, 'M', True),
         'II-4': (700, 300, 'F', False), 'II-5': (900, 300, 'M', False),
         'III-1': (800, 540, 'F', True)}
TWINS_COUPLES = [('I-1', 'I-2', ['II-1', 'II-2', 'II-3', 'II-4']), ('II-4', 'II-5', ['III-1'])]
TWINS_READ = [['I-1', '0', '0', '1', '2'], ['I-2', '0', '0', '2', '1'],
              ['II-1', 'I-1', 'I-2', '2', '1'], ['II-2', 'I-1', 'I-2', '1', '2'], ['II-3', 'I-1', 'I-2', '1', '2'],
              ['II-4', 'I-1', 'I-2', '2', '1'], ['II-5', '0', '0', '1', '1'],
              ['III-1', 'II-5', 'II-4', '2', '2']]


@pytest.mark.parametrize('kind', ['MZ', 'DZ'])
@pytest.mark.parametrize('hand_drawn', [False, True])
def test_twins(tmp_path, kind, hand_drawn):
    # the twins' row is read as it is drawn: the twins are children of their parents, like their sisters, with nothing
    # read between them, and they are identical if there is a bar between their lines
    studio_picture(tmp_path / 'twins.png', TWINS, TWINS_COUPLES, [('II-2', 'II-3', kind)])
    rows, twins, _ = read(tmp_path / 'twins.png', hand_drawn=hand_drawn)
    assert rows == TWINS_READ
    assert twins == [['II-2', 'II-3', kind]]


def test_identical_twins_drawn_close_together_are_not_a_diamond(tmp_path):
    # the twins are close together, under a line close above them: the triangle their lines make with the bar is
    # small, and was read as a symbol, a diamond, someone of unknown sex between the twins and their parents
    people = {'I-1': (220, 60, 'M', False), 'I-2': (440, 60, 'F', True),
              'II-1': (150, 280, 'F', True), 'II-2': (290, 280, 'F', False), 'II-3': (430, 280, 'F', False),
              'II-4': (640, 280, 'M', False)}
    studio_picture(tmp_path / 'close.png', people, [('I-1', 'I-2', ['II-1', 'II-2', 'II-3', 'II-4'])],
                   [('II-2', 'II-3', 'MZ')])
    for hand_drawn in (False, True):
        rows, twins, _ = read(tmp_path / 'close.png', hand_drawn=hand_drawn)
        assert rows == [['I-1', '0', '0', '1', '1'], ['I-2', '0', '0', '2', '2'],
                        ['II-1', 'I-1', 'I-2', '2', '2'], ['II-2', 'I-1', 'I-2', '2', '1'],
                        ['II-3', 'I-1', 'I-2', '2', '1'], ['II-4', 'I-1', 'I-2', '1', '1']]
        assert twins == [['II-2', 'II-3', 'MZ']]


def test_twins_drawn_far_apart_with_families_of_their_own(tmp_path):
    # each twin has a husband and a child, on the far side, and the lines to the twins are long and nearly level
    people = {'I-1': (520, 60, 'M', False), 'I-2': (740, 60, 'F', False),
              'II-1': (140, 300, 'M', False), 'II-2': (340, 300, 'F', True), 'II-3': (920, 300, 'F', True),
              'II-4': (1120, 300, 'M', False),
              'III-1': (240, 540, 'M', True), 'III-2': (1020, 540, 'F', False)}
    couples = [('I-1', 'I-2', ['II-2', 'II-3']), ('II-1', 'II-2', ['III-1']), ('II-3', 'II-4', ['III-2'])]
    for kind in ('MZ', 'DZ'):
        studio_picture(tmp_path / 'far.png', people, couples, [('II-2', 'II-3', kind)])
        rows, twins, _ = read(tmp_path / 'far.png')
        assert rows == [['I-1', '0', '0', '1', '1'], ['I-2', '0', '0', '2', '1'],
                        ['II-1', '0', '0', '1', '1'], ['II-2', 'I-1', 'I-2', '2', '2'],
                        ['II-3', 'I-1', 'I-2', '2', '2'], ['II-4', '0', '0', '1', '1'],
                        ['III-1', 'II-1', 'II-2', '1', '2'], ['III-2', 'II-4', 'II-3', '2', '1']]
        assert twins == [['II-2', 'II-3', kind]]


def test_twin_groups():
    # twins are set side by side, each set with the one on the left first; twins joined only through a third are
    # identical only if all are
    df = pd.DataFrame({'FamilyID': 'F', 'IndividualID': ['I-1', 'II-1', 'II-2', 'II-3', 'II-4', 'II-5'],
                       'PaternalID': 0, 'MaternalID': 0, 'Sex': 1, 'Phenotype': 1})
    df.attrs['twins'] = [['II-1', 'II-2', 'MZ'], ['II-2', 'II-3', 'DZ'], ['II-4', 'II-5', 'MZ']]
    assert twin_groups(df) == [('II-1', [('II-2', True), ('II-3', False)]), ('II-4', [('II-5', True)])]
    df.attrs['twins'] = []
    assert twin_groups(df) == []


def test_ga4gh_export_of_twins(tmp_path):
    # a PED file can't hold twins, but a GA4GH Pedigree can, as studio2ga4gh writes them
    studio_picture(tmp_path / 'twins.png', TWINS, TWINS_COUPLES, [('II-2', 'II-3', 'MZ')])
    df = pedigree_processing('FAMT', image_path=str(tmp_path / 'twins.png'), ocr=None)
    doc = json.loads(open(GA4GH_export(df, str(tmp_path))).read())
    twinned = [(r['individualId'], r['relation']['id'], r['relativeId']) for r in doc['relationships']
               if r['relation']['id'] in ('KIN:010', 'KIN:011')]
    assert twinned == [('II-2', 'KIN:010', 'II-3')]
    assert doc['narrative'].endswith('Twins: II-2, II-3 (identical).')
    # and twins who aren't identical
    df.attrs['twins'] = [['II-2', 'II-3', 'DZ']]
    doc = json.loads(open(GA4GH_export(df, str(tmp_path))).read())
    assert [(r['individualId'], r['relation']['id'], r['relativeId']) for r in doc['relationships']
            if r['relation']['id'] in ('KIN:010', 'KIN:011')] == [('II-2', 'KIN:011', 'II-3')]
    assert doc['narrative'].endswith('Twins: II-2, II-3 (not identical).')


# ---------------------------------------------------------------------------------------------------------------------
# labels written against lines
# ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('top', [262, 270, 276])
@pytest.mark.parametrize('hand_drawn', [False, True])
def test_label_written_against_a_line(tmp_path, top, hand_drawn):
    # a man who married into the family is drawn a little higher than his wife and her sisters, so that the line over
    # them passes close above him: his number, written over his symbol, crosses the line (262), touches it (270) or
    # nearly does (276), and is no line down to him
    people = {'I-1': (300, 60, 'M', False), 'I-2': (520, 60, 'F', False),
              'II-1': (140, 300, 'F', False), 'II-2': (330, top, 'M', True), 'II-3': (520, 300, 'F', True),
              'II-4': (720, 300, 'F', False), 'III-1': (230, 540, 'M', False)}
    studio_picture(tmp_path / 'label.png', people, [('I-1', 'I-2', ['II-1', 'II-3', 'II-4']), ('II-1', 'II-2', ['III-1'])])
    rows, _, _ = read(tmp_path / 'label.png', hand_drawn=hand_drawn)
    assert rows == [['I-1', '0', '0', '1', '1'], ['I-2', '0', '0', '2', '1'],
                    ['II-1', 'I-1', 'I-2', '2', '1'], ['II-2', '0', '0', '1', '2'], ['II-3', 'I-1', 'I-2', '2', '2'],
                    ['II-4', 'I-1', 'I-2', '2', '1'], ['III-1', 'II-2', 'II-1', '1', '1']]


def test_labels_are_taken_out_but_not_the_lines(tmp_path):
    # erase_labels takes out the words over the symbols, and leaves the lines whole where the words cross them
    people = {'I-1': (300, 60, 'M', False), 'I-2': (520, 60, 'F', False),
              'II-1': (140, 300, 'F', False), 'II-2': (330, 262, 'M', True), 'II-3': (520, 300, 'F', True)}
    studio_picture(tmp_path / 'label.png', people, [('I-1', 'I-2', ['II-1', 'II-3']), ('II-1', 'II-2', [])])
    real = core.erase_labels
    seen = {}

    def spy(line_mask, dark, boxes, size):
        before = line_mask.copy()
        found = real(line_mask, dark, boxes, size)
        seen.update(before=before, after=line_mask.copy(), size=size, found=found)
        return found

    core.erase_labels = spy
    try:
        df = pedigree_processing('FAMT', image_path=str(tmp_path / 'label.png'), ocr=None)
    finally:
        core.erase_labels = real
    assert seen['found'] >= 10    # the letters of the five labels, or most of them
    # the line over the children, 60 pixels above them, which II-2's label crosses, runs on unbroken from II-1 to
    # II-3, as it did
    scale = df.attrs['upscale_factor']
    band = slice(int((240 - 6) * scale), int((240 + 6) * scale))
    across = slice(int((140 + 52) * scale), int((520 + 52) * scale))
    assert (seen['before'][band, across] > 0).any(axis=0).all()
    assert (seen['after'][band, across] > 0).any(axis=0).all()
    # and the labels are gone: nothing is left over I-1, where his label was
    over = (slice(int((60 - 34) * scale), int((60 - 8) * scale)), slice(int(320 * scale), int(390 * scale)))
    assert (seen['before'][over] > 0).any() and not (seen['after'][over] > 0).any()


def test_founders_drawn_at_different_heights_are_one_row(tmp_path):
    # the Studio takes everyone within a symbol and a half of the top of a row as in it, and so does PedInterp
    people = {'I-1': (300, 60, 'M', False), 'I-2': (520, 110, 'F', True),
              'II-1': (250, 330, 'F', True), 'II-2': (450, 330, 'M', False)}
    studio_picture(tmp_path / 'uneven.png', people, [('I-1', 'I-2', ['II-1', 'II-2'])])
    rows, _, _ = read(tmp_path / 'uneven.png')
    assert rows == [['I-1', '0', '0', '1', '1'], ['I-2', '0', '0', '2', '2'],
                    ['II-1', 'I-1', 'I-2', '2', '2'], ['II-2', 'I-1', 'I-2', '1', '1']]


# ---------------------------------------------------------------------------------------------------------------------
# sketched by hand
# ---------------------------------------------------------------------------------------------------------------------
# three generations sketched by hand, symbols of unequal sizes; twins who are not identical, and a pregnancy lost
# (a triangle), whose sex isn't known
SKETCH = {'I-1': (330, 90, 70, 'M', True), 'I-2': (520, 95, 54, 'F', False),
          'II-1': (150, 300, 60, 'F', False), 'II-2': (300, 305, 46, 'M', True), 'II-3': (420, 300, 66, 'M', False),
          'II-4': (600, 300, 58, 'F', False), 'II-5': (780, 305, 72, 'M', False),
          'III-1': (520, 520, 50, 'M', True), 'III-2': (690, 515, 66, 'F', False), 'III-3': (850, 520, 48, 'T', False)}
SKETCH_COUPLES = [('I-1', 'I-2', ['II-1', 'II-2', 'II-3', 'II-4']), ('II-4', 'II-5', ['III-1', 'III-2', 'III-3'])]
SKETCH_TWINS = [('II-2', 'II-3', 'DZ')]
SKETCH_READ = [['I-1', '0', '0', '1', '2'], ['I-2', '0', '0', '2', '1'],
               ['II-1', 'I-1', 'I-2', '2', '1'], ['II-2', 'I-1', 'I-2', '1', '2'], ['II-3', 'I-1', 'I-2', '1', '1'],
               ['II-4', 'I-1', 'I-2', '2', '1'], ['II-5', '0', '0', '1', '1'],
               ['III-1', 'II-5', 'II-4', '1', '2'], ['III-2', 'II-5', 'II-4', '2', '1'], ['III-3', 'II-5', 'II-4', '0', '1']]
RED, BLUE, DARK, GREEN = (192, 57, 43), (41, 128, 185), (26, 35, 50), (39, 174, 96)


@pytest.mark.parametrize('seed, pen, width', [(0, RED, 4), (1, BLUE, 3), (2, DARK, 2), (4, RED, 3)])
def test_sketch(tmp_path, seed, pen, width):
    # each sketch differs, as one drawn by hand would, with Pedigree Studio's pens, from thin to thick
    sketch_picture(tmp_path / 'sketch.png', SKETCH, SKETCH_COUPLES, SKETCH_TWINS, seed=seed, pen=pen, width=width)
    rows, twins, _ = read(tmp_path / 'sketch.png', hand_drawn=True)
    assert rows == SKETCH_READ
    assert twins == [['II-2', 'II-3', 'DZ']]


def test_sketch_with_identical_twins(tmp_path):
    sketch_picture(tmp_path / 'sketch.png', SKETCH, SKETCH_COUPLES, [('II-2', 'II-3', 'MZ')], seed=3, pen=RED, width=4)
    rows, twins, _ = read(tmp_path / 'sketch.png', hand_drawn=True)
    assert rows == SKETCH_READ
    assert twins == [['II-2', 'II-3', 'MZ']]


def _studio(x, y):
    '''where Pedigree Studio draws a person whose symbol's corner is at (x, y), as the middle of the symbol in the
    picture it saves, which is twice the size'''
    return 2 * (x + 26), 2 * (y + 26)


# the Okafor family of the workbench's examples, where Pedigree Studio draws its people, sketched at the size the
# Studio saves its pictures, with as much room over the children as it leaves: identical twins drawn as far apart as
# the other children, whose lines come in flat and close over their symbols, and a pregnancy lost (a triangle) and
# one going on (a diamond), whose sex isn't known
OKAFOR = {'I-1': (*_studio(512, 160), 96, 'M', False), 'I-2': (*_studio(616, 160), 110, 'F', False),
          'II-1': (*_studio(356, 290), 100, 'F', False), 'II-2': (*_studio(460, 290), 112, 'M', False),
          'II-3': (*_studio(668, 290), 92, 'F', True), 'II-4': (*_studio(772, 290), 118, 'M', False),
          'III-1': (*_studio(304, 420), 120, 'M', False), 'III-2': (*_studio(460, 420), 98, 'M', False),
          'III-3': (*_studio(590, 420), 116, 'F', False), 'III-4': (*_studio(720, 420), 90, 'F', False),
          'III-5': (*_studio(850, 420), 104, 'M', False),
          'IV-1': (*_studio(382, 550), 108, 'F', False), 'IV-2': (*_studio(460, 550), 84, 'T', False),
          'IV-3': (*_studio(551, 550), 120, 'M', True), 'IV-4': (*_studio(642, 550), 112, 'M', True),
          'IV-5': (*_studio(746, 550), 100, 'U', False)}
OKAFOR_COUPLES = [('I-1', 'I-2', ['II-2', 'II-3']), ('II-1', 'II-2', ['III-1', 'III-2']),
                  ('II-3', 'II-4', ['III-3', 'III-4', 'III-5']),
                  ('III-2', 'III-3', ['IV-1', 'IV-2', 'IV-3', 'IV-4', 'IV-5'])]
OKAFOR_READ = [['I-1', '0', '0', '1', '1'], ['I-2', '0', '0', '2', '1'],
               ['II-1', '0', '0', '2', '1'], ['II-2', 'I-1', 'I-2', '1', '1'], ['II-3', 'I-1', 'I-2', '2', '2'],
               ['II-4', '0', '0', '1', '1'],
               ['III-1', 'II-2', 'II-1', '1', '1'], ['III-2', 'II-2', 'II-1', '1', '1'],
               ['III-3', 'II-4', 'II-3', '2', '1'], ['III-4', 'II-4', 'II-3', '2', '1'],
               ['III-5', 'II-4', 'II-3', '1', '1'],
               ['IV-1', 'III-2', 'III-3', '2', '1'], ['IV-2', 'III-2', 'III-3', '0', '1'],
               ['IV-3', 'III-2', 'III-3', '1', '2'], ['IV-4', 'III-2', 'III-3', '1', '2'],
               ['IV-5', 'III-2', 'III-3', '0', '1']]


@pytest.mark.parametrize('seed', [0, 2, 3, 5])
def test_sketch_with_identical_twins_far_apart(tmp_path, seed):
    # the lines to the twins run close over their symbols, which closing the gaps between the strokes of their
    # scribbles runs together; and the white between a family's lines, round a symbol, is no piece of the symbol
    sketch_picture(tmp_path / 'okafor.png', OKAFOR, OKAFOR_COUPLES, [('IV-3', 'IV-4', 'MZ')], seed=seed, pen=RED,
                   width=4, room=(44, 60))
    rows, twins, _ = read(tmp_path / 'okafor.png', hand_drawn=True)
    assert rows == OKAFOR_READ
    assert twins == [['IV-3', 'IV-4', 'MZ']]


@pytest.mark.parametrize('studio', [('I-1', 'I-2'), ('I-1', 'I-2', 'II-1', 'II-2', 'II-3', 'II-4')])
def test_sketch_begun_with_the_studios_symbols(tmp_path, studio):
    # the first generation or two drawn with the Studio's symbols, the rest finished by hand
    people = dict(SKETCH)
    for pid in studio:
        x, y, _, sex, affected = people[pid]
        people[pid] = (x, y, 104, sex, affected)
    sketch_picture(tmp_path / 'mixed.png', people, SKETCH_COUPLES, SKETCH_TWINS, seed=0, pen=GREEN, width=4,
                   studio=studio, size=(1000, 640))
    rows, twins, _ = read(tmp_path / 'mixed.png', hand_drawn=True)
    assert rows == SKETCH_READ
    assert twins == [['II-2', 'II-3', 'DZ']]


def test_transparent_sketch(tmp_path):
    # a picture saved with a transparent background, as a drawing app may save it, reads as one on white
    sketch_picture(tmp_path / 'clear.png', SKETCH, SKETCH_COUPLES, SKETCH_TWINS, seed=1, pen=BLUE, width=3,
                   transparent=True)
    assert Image.open(tmp_path / 'clear.png').getpixel((2, 2))[3] == 0
    rows, twins, _ = read(tmp_path / 'clear.png', hand_drawn=True)
    assert rows == SKETCH_READ
    assert twins == [['II-2', 'II-3', 'DZ']]


def test_a_sketch_is_read_without_its_labels(tmp_path, monkeypatch):
    # labels written by hand are not read with Tesseract unless asked for, and people are numbered
    def tesseract(image):
        raise AssertionError('Tesseract should not be asked to read a sketch')

    monkeypatch.setattr(core, 'tesseract_words', tesseract)
    sketch_picture(tmp_path / 'sketch.png', SKETCH, SKETCH_COUPLES, SKETCH_TWINS, seed=0, pen=RED, width=4)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        df = pedigree_processing('FAMT', image_path=str(tmp_path / 'sketch.png'), hand_drawn=True)
    assert list(df['IndividualID'])[:2] == ['I-1', 'I-2']
    with pytest.raises(AssertionError, match='Tesseract should not'):
        pedigree_processing('FAMT', image_path=str(tmp_path / 'sketch.png'), hand_drawn=True, ocr='tesseract')


def test_lines_missed_in_a_sketch_suggest_reading_it_as_one(tmp_path, monkeypatch):
    # when lines seem to have been missed, the warnings say that a sketch reads better as one; not when it was read so
    monkeypatch.setattr(core, 'missed_lines', lambda *args: ['II-1: only a father was found, so a line may have been missed'])
    sketch_picture(tmp_path / 'sketch.png', SKETCH, SKETCH_COUPLES, SKETCH_TWINS, seed=0, pen=RED, width=4)
    _, _, warned = read(tmp_path / 'sketch.png')
    assert core.HAND_DRAWN_HINT in warned
    _, _, warned = read(tmp_path / 'sketch.png', hand_drawn=True)
    assert core.HAND_DRAWN_HINT not in warned


@pytest.mark.parametrize('pedigree', ['two', 'three', 'four'])
@pytest.mark.parametrize('symbol, line', [(40, 3), (60, 4)])
def test_a_drawing_read_as_a_sketch(tmp_path, pedigree, symbol, line):
    # a pedigree drawn with software, read as if it were drawn by hand, reads as it does otherwise: its labels,
    # written large and close under the symbols, are no symbols filled in, nor spaces closed in by them
    from test_core import NUMBERED, draw_pedigree
    drawing, rows = NUMBERED[pedigree]
    draw_pedigree(tmp_path / 'p.png', *drawing, symbol=symbol, line=line)
    assert read(tmp_path / 'p.png', hand_drawn=True)[0] == rows
