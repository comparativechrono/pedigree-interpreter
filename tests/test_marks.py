'''
Reading the marks drawn on the symbols (pedigree_processing(..., marks=True)): who has died, the proband and carriers,
in drawings made as Pedigree Studio makes them and in sketches; and writing them, as a PED file can't hold them.
'''
import json
import warnings

import cv2
import numpy as np
import pandas as pd
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


def test_names_and_ages_under_the_symbols_are_no_marks(tmp_path):
    # as the Studio writes them under its symbols, in letters whose strokes meet as an arrow's do
    under = {'I-1': 'Nnamdi\nd. 82', 'I-2': 'Adanna\nd. 90', 'II-1': 'Ngozi, 84', 'II-2': 'Kwame, 47',
             'II-3': 'Grace, 78\nbreast cancer', 'II-4': 'Samuel\nd. 79', 'III-1': 'Ada, 14', 'III-2': '2016',
             'III-3': 'Yusuf, 7'}
    studio_picture(tmp_path / 'named.png', STUDIO, STUDIO_COUPLES, marks=STUDIO_MARKS, under=under)
    df = read(tmp_path / 'named.png', marks=True)
    assert rows(df) == STUDIO_READ
    assert marks_of(df) == STUDIO_MARKS


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


def _inside(picture, person):
    '''the inside of a person's symbol in STUDIO, within its outline'''
    x, y, sex, _ = STUDIO[person]
    inside = np.zeros(picture.shape[:2], np.uint8)
    if sex == 'F':
        cv2.circle(inside, (x + SHAPE // 2, y + SHAPE // 2), SHAPE // 2 - 4, 1, -1)
    elif sex == 'M':
        cv2.rectangle(inside, (x + 4, y + 4), (x + SHAPE - 4, y + SHAPE - 4), 1, -1)
    else:
        half = SHAPE // 2
        cv2.fillPoly(inside, [np.array([(x + half, y + 4), (x + SHAPE - 4, y + half), (x + half, y + SHAPE - 4),
                                        (x + 4, y + half)], np.int32)], 1)
    return inside


@pytest.mark.parametrize('hand_drawn', [False, True])
@pytest.mark.parametrize('offset', [0, 4, 8])
def test_a_symbol_shaded_with_dots_is_not_slashed(tmp_path, offset, hand_drawn):
    # Pedigree Studio's shading with dots (Pattern → Dots): a dot of radius 1.6 every 8 of its units, in the colour of
    # its lines, which runs along a line rising to the right as a slash does, but in dots; here in an empty circle,
    # square and diamond, with the dots where the Studio puts them (offset 0) and between, read as a drawing and as a
    # sketch (where the diamond's inside, as it is measured, is smaller)
    studio_picture(tmp_path / 'dots.png', STUDIO, STUDIO_COUPLES)
    picture = cv2.imread(str(tmp_path / 'dots.png'))
    shade = np.zeros(picture.shape[:2], np.uint8)
    for person in ('II-1', 'II-4', 'III-2'):
        x, y, *_ = STUDIO[person]
        dots = np.zeros_like(shade)
        for dx in range(8 + offset - 16, SHAPE + 16, 16):
            for dy in range(8 + offset - 16, SHAPE + 16, 16):
                cv2.circle(dots, (x + dx, y + dy), 3, 1, -1)
        shade |= dots & _inside(picture, person)
    picture[shade > 0] = (50, 35, 26)
    cv2.imwrite(str(tmp_path / 'dots.png'), picture)
    df = read(tmp_path / 'dots.png', marks=True, hand_drawn=hand_drawn)
    assert rows(df) == STUDIO_READ
    assert not df[MARKS].values.any()


def test_specks_are_no_marks(tmp_path):
    # a picture with dark specks all over it, as a poor scan may have (one pixel in 500): no slash is read from specks
    # in a row, nor an arrow or a dot
    studio_picture(tmp_path / 'specks.png', STUDIO, STUDIO_COUPLES)
    picture = cv2.imread(str(tmp_path / 'specks.png'), cv2.IMREAD_GRAYSCALE)
    picture[np.random.default_rng(0).random(picture.shape) < 0.002] = 40
    cv2.imwrite(str(tmp_path / 'specks.png'), picture)
    df = read(tmp_path / 'specks.png', marks=True)
    assert not df[MARKS].values.any()


def _arcs_one_by_one(ink, x, y, radius):
    """where ink crosses a circle round (x, y), looked at round one point, as marks._three_ways looks round many"""
    angles = np.arange(0, 360, 3)
    xs = np.round(x + radius * np.cos(np.radians(angles))).astype(np.int64)
    ys = np.round(y - radius * np.sin(np.radians(angles))).astype(np.int64)
    inside = (xs >= 0) & (ys >= 0) & (xs < ink.shape[1]) & (ys < ink.shape[0])
    on = np.zeros(len(angles), bool)
    on[inside] = ink[ys[inside], xs[inside]] > 0
    if on.all() or not on.any():
        return []
    start = int(np.argmin(on))
    on = np.roll(on, -start)
    arcs, k = [], 0
    while k < len(on):
        if on[k]:
            j = k
            while j < len(on) and on[j]:
                j += 1
            arcs.append((float((angles[start] + 3 * (k + j - 1) / 2) % 360), 3 * (j - k)))
            k = j
        else:
            k += 1
    return arcs


def test_the_points_round_which_ink_runs_three_ways():
    # the arrowhead's search looks round all the points of the ink at once (marks._three_ways): it keeps the points
    # where circles at two radii next to each other cross the ink in three arcs, each with the arcs a point looked at
    # on its own has
    from PedInterp.marks import _three_ways
    rng = np.random.default_rng(0)
    ink = np.zeros((120, 160), np.uint8)
    for _ in range(12):
        cv2.line(ink, tuple(int(v) for v in rng.integers(0, 160, 2)), tuple(int(v) for v in rng.integers(0, 120, 2)), 1,
                 int(rng.integers(1, 5)))
    ink |= (rng.random(ink.shape) < 0.02).astype(np.uint8)
    ys, xs = np.nonzero(ink)
    radii = [5.0, 7.5, 10.0, 12.5]
    found = {(int(x), int(y)): arcs for x, y, arcs in _three_ways(ink, xs, ys, radii)}
    kept = 0
    for x, y in zip(xs, ys):
        each = [_arcs_one_by_one(ink, x, y, radius) for radius in radii]
        each = [arcs if len(arcs) == 3 else None for arcs in each]
        if not any(a is not None and b is not None for a, b in zip(each, each[1:])):
            assert (int(x), int(y)) not in found
            continue
        kept += 1
        assert [None if arcs is None else [(float(m), int(w)) for m, w in arcs]
                for arcs in found[(int(x), int(y))]] == each
    assert kept > 100


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
    # (those with a slash have died, and those whose symbol is empty without one haven't; a symbol filled in may hide a
    # slash, as the Studio's through a filled square is hidden, so those without one seen have no vital status)
    assert status == {person: 'DECEASED' if 'deceased' in STUDIO_MARKS.get(person, ()) else
                      None if affected else 'ALIVE' for person, (*_, affected) in STUDIO.items()}
    assert doc['indexPatients'] == ['II-2', 'III-3']
    assert '; proband II-2, III-3.' in doc['narrative']
    assert doc['narrative'].endswith('Deaths, probands and carriers were read from the marks drawn on the symbols. '
                                     'A filled symbol may hide a slash, so the affected have no vital status unless '
                                     'one was seen. II-1 is a carrier. II-4 is a carrier. III-1 is a carrier.')
    # without marks, as before: no vital status, and no index patient
    plain = json.load(open(GA4GH_export(read(tmp_path / 'marked.png'), str(tmp_path / 'plain'))))
    assert not any('vitalStatus' in p['subject'] for p in plain['individuals'])
    assert 'indexPatients' not in plain
    assert 'carrier' not in plain['narrative']


def test_a_pregnancy_lost_has_died(tmp_path):
    # in the GA4GH Pedigree, a triangle has died, slash or none, as studio2ga4gh writes the Studio's, with a note in the
    # narrative; and each person's vital status is as studio2ga4gh gives it from the drawing made from the same table,
    # but for the affected with no slash seen, which the fill may hide
    sketch_picture(tmp_path / 'sketch.png', SKETCH, SKETCH_COUPLES, SKETCH_TWINS, seed=0, pen=RED, width=4,
                   marks=SKETCH_MARKS)
    df = read(tmp_path / 'sketch.png', marks=True, hand_drawn=True)
    assert df.attrs['layout']['III-3']['shape'] == 'triangle'
    assert not df.loc[df['IndividualID'] == 'III-3', 'Deceased'].item()
    doc = json.load(open(GA4GH_export(df, str(tmp_path))))
    status = {p['subject']['id']: p['subject'].get('vitalStatus', {}).get('status') for p in doc['individuals']}
    assert status['III-3'] == 'DECEASED'
    assert ' III-3 is a pregnancy loss.' in doc['narrative']
    studio2ga4gh = pytest.importorskip('studio2ga4gh')
    drawing = json.load(open(Studio_export(df, str(tmp_path))))
    kindred, = studio2ga4gh.convert(drawing).kindreds
    ids = [str(p) for p in df['IndividualID']]
    by_number = {p['id']: ids[k] for k, p in enumerate(drawing['persons'][:len(ids)])}
    from_drawing = {by_number.get(m.id, m.id): m.vital_status for m in kindred.members}
    affected = {str(r.IndividualID): int(r.Phenotype) == 2 for r in df.itertuples(index=False)}
    for person, said in status.items():
        assert said == from_drawing[person] or (said is None and affected[person] and
                                                from_drawing[person] == 'ALIVE'), person


def test_marks_left_missing_are_not_marks(tmp_path):
    # a table whose marks were filled in by hand, with some left missing: those people haven't the mark
    studio_picture(tmp_path / 'marked.png', STUDIO, STUDIO_COUPLES, marks=STUDIO_MARKS)
    df = read(tmp_path / 'marked.png', marks=True)
    df['Carrier'] = df['Carrier'].astype('boolean')
    df.loc[df['IndividualID'] == 'II-1', 'Carrier'] = pd.NA
    df['Deceased'] = df['Deceased'].astype(object)
    df.loc[df['IndividualID'] == 'I-1', 'Deceased'] = None
    doc = json.load(open(GA4GH_export(df, str(tmp_path))))
    assert ' II-1 is a carrier.' not in doc['narrative'] and ' II-4 is a carrier.' in doc['narrative']
    status = {p['subject']['id']: p['subject'].get('vitalStatus', {}).get('status') for p in doc['individuals']}
    assert status['I-1'] == 'ALIVE' and status['I-2'] == 'DECEASED'
    drawing = json.load(open(Studio_export(df, str(tmp_path))))
    centres = {p['id']: p['centerText'] for p in drawing['persons']}
    assert sum(text == 'dot' for text in centres.values()) == 2


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
