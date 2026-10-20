'''
Pedigree Studio drawings of the pedigrees PedInterp reads (Studio_export): drawn as the picture was, with what a PED
file can't hold, and read back as the same family by studio2ped and studio2ga4gh, the lab's converters from the Studio.
'''
import json
import warnings

import pandas as pd
import pytest

from PedInterp import PED_export, Studio_export, pedigree_processing
from PedInterp.studio import AFFECTED_COLOUR, CLOSEST, MARGIN, ROW_GAP, studio_drawing
from drawings import sketch_picture, studio_picture
from test_twins_and_sketches import (OKAFOR, OKAFOR_COUPLES, OKAFOR_READ, RED, SKETCH, SKETCH_COUPLES, SKETCH_READ,
                                     SKETCH_TWINS)

COLUMNS = ['IndividualID', 'PaternalID', 'MaternalID', 'Sex', 'Phenotype']


def read(path, **options):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return pedigree_processing('FAMS', image_path=str(path), ocr=None, **options)


def by_person(drawing, df):
    '''the drawing's people, by their IDs in the table (the table's order, then any unknown parents)'''
    ids = [str(p) for p in df['IndividualID']]
    return {ids[k] if k < len(ids) else p['text']: p for k, p in enumerate(drawing['persons'])}


def couples(drawing):
    '''the couples joined in a drawing, as (the one on the left, the other): how they are joined'''
    return {(s['fromId'], s['toId']): s['type'] for s in drawing['partnerships']}


def studio2ped_rows(drawing):
    '''the PED file studio2ped writes from a drawing, as rows, without the family ID'''
    studio2ped = pytest.importorskip('studio2ped')
    (_, content), = studio2ped.convert(drawing, 'BACK').files
    return [line.split('\t')[1:] for line in content.splitlines() if line and not line.startswith('#')]


def studio2ga4gh_relations(drawing):
    studio2ga4gh = pytest.importorskip('studio2ga4gh')
    kindred, = studio2ga4gh.convert(drawing).kindreds
    return {(r.individual, r.kin, r.relative) for r in kindred.relations}


def test_a_sketch_as_a_studio_drawing(tmp_path):
    # a sketch, with twins who aren't identical and a pregnancy lost, becomes a Studio drawing of the same family
    sketch_picture(tmp_path / 'sketch.png', SKETCH, SKETCH_COUPLES, SKETCH_TWINS, seed=0, pen=RED, width=4)
    df = read(tmp_path / 'sketch.png', hand_drawn=True)
    path = Studio_export(df, str(tmp_path / 'out'))
    assert path == f"{tmp_path / 'out'}/FAMS.studio.json"
    drawing = json.load(open(path))
    assert drawing['version'] == 5
    people = by_person(drawing, df)
    assert list(people) == [row[0] for row in SKETCH_READ]
    assert {pid: p['shape'] for pid, p in people.items()} == {
        'I-1': 'male', 'I-2': 'female', 'II-1': 'female', 'II-2': 'male', 'II-3': 'male', 'II-4': 'female',
        'II-5': 'male', 'III-1': 'male', 'III-2': 'female', 'III-3': 'miscarriage'}
    assert [pid for pid, p in people.items() if p['fillMode'] == 'solid'] == ['I-1', 'II-2', 'III-1']
    assert drawing['legendLabels'] == {AFFECTED_COLOUR: 'Affected'}
    # the Studio numbers people itself, as PedInterp has numbered them, so they have no text of their own
    assert {p['text'] for p in people.values()} == {''}
    # twins who aren't identical, joined to their parents' line
    (twin,) = drawing['twinLinks']
    assert (twin['child1Id'], twin['child2Id'], twin['type']) == (people['II-2']['id'], people['II-3']['id'], 'nonidentical')
    assert studio2ped_rows(drawing) == SKETCH_READ
    relations = studio2ga4gh_relations(drawing)
    assert ('II-2', 'KIN:011', 'II-3') in relations
    assert ('II-5', 'KIN:028', 'III-1') in relations and ('II-4', 'KIN:027', 'III-1') in relations


def test_drawn_where_the_picture_has_them(tmp_path):
    # each row of symbols is a generation, at the Studio's spacing, and each row is in the order of the picture, no
    # two people closer than the Studio's symbols allow
    sketch_picture(tmp_path / 'sketch.png', SKETCH, SKETCH_COUPLES, SKETCH_TWINS, seed=0, pen=RED, width=4)
    df = read(tmp_path / 'sketch.png', hand_drawn=True)
    people = by_person(studio_drawing(df), df)
    for generation, y in (('I', MARGIN), ('II', MARGIN + ROW_GAP), ('III', MARGIN + 2*ROW_GAP)):
        row = [p for pid, p in people.items() if pid.split('-')[0] == generation]
        assert {p['y'] for p in row} == {y}
        xs = [p['x'] for p in row]
        assert xs == sorted(xs) and all(b - a >= CLOSEST for a, b in zip(xs, xs[1:]))
    assert min(p['x'] for p in people.values()) == MARGIN
    # and across the rows, where the picture has them
    assert people['II-1']['x'] < people['I-1']['x'] < people['I-2']['x'] < people['II-5']['x']


def test_identical_twins_and_cousins_who_marry(tmp_path):
    # the Okafor family sketched: identical twins, a pregnancy lost and one going on, and first cousins who marry,
    # whose line is double, as the Studio draws it
    sketch_picture(tmp_path / 'okafor.png', OKAFOR, OKAFOR_COUPLES, [('IV-3', 'IV-4', 'MZ')], seed=0, pen=RED,
                   width=4, room=(44, 60))
    df = read(tmp_path / 'okafor.png', hand_drawn=True)
    drawing = studio_drawing(df)
    people = by_person(drawing, df)
    assert (people['IV-2']['shape'], people['IV-5']['shape']) == ('miscarriage', 'unknown')
    assert sorted(couples(drawing).values()) == ['consanguineous', 'normal', 'normal', 'normal']
    assert couples(drawing)[(people['III-2']['id'], people['III-3']['id'])] == 'consanguineous'
    (twin,) = drawing['twinLinks']
    assert (twin['child1Id'], twin['child2Id'], twin['type']) == (people['IV-3']['id'], people['IV-4']['id'], 'identical')
    assert studio2ped_rows(drawing) == OKAFOR_READ
    relations = studio2ga4gh_relations(drawing)
    assert {('IV-3', 'KIN:010', 'IV-4'), ('III-2', 'KIN:030', 'III-3')} <= relations


def test_couples_without_children(tmp_path):
    # a PED file can't hold a couple who have no children, but the drawing has them, as the picture does
    people = {'I-1': (200, 60, 'M', False), 'I-2': (420, 60, 'F', False),
              'II-1': (120, 300, 'F', True), 'II-2': (320, 300, 'M', False), 'II-3': (520, 300, 'F', False)}
    studio_picture(tmp_path / 'couple.png', people, [('I-1', 'I-2', ['II-1', 'II-2']), ('II-2', 'II-3', [])])
    df = read(tmp_path / 'couple.png')
    assert df[COLUMNS].astype(str).values.tolist() == [
        ['I-1', '0', '0', '1', '1'], ['I-2', '0', '0', '2', '1'], ['II-1', 'I-1', 'I-2', '2', '2'],
        ['II-2', 'I-1', 'I-2', '1', '1'], ['II-3', '0', '0', '2', '1']]
    drawing = studio_drawing(df)
    ids = by_person(drawing, df)
    assert set(couples(drawing)) == {(ids['I-1']['id'], ids['I-2']['id']), (ids['II-2']['id'], ids['II-3']['id'])}
    assert len(drawing['childLinks']) == 2


def test_the_condition_names_the_colour_key(tmp_path):
    # as ga4gh2studio names it, with the term, which studio2ga4gh reads back
    sketch_picture(tmp_path / 'sketch.png', SKETCH, SKETCH_COUPLES, SKETCH_TWINS, seed=0, pen=RED, width=4)
    df = read(tmp_path / 'sketch.png', hand_drawn=True)
    drawing = studio_drawing(df, condition=('MONDO:0007739', 'Huntington disease'))
    assert drawing['legendLabels'] == {AFFECTED_COLOUR: 'Huntington disease [MONDO:0007739]'}
    with pytest.raises(ValueError, match='ontology term'):
        studio_drawing(df, condition=('HD', 'Huntington disease'))


def test_a_table_made_by_hand(tmp_path):
    # a table that wasn't read from a picture is drawn by generation, in its own order; a child with one parent in it
    # is given an unknown parent for the line to come from, as ga4gh2studio gives one; IDs that aren't numbers as the
    # Studio numbers people are written under the symbols
    df = pd.DataFrame({'FamilyID': 'F', 'IndividualID': ['dad', 'mum', 'kid', 'half'],
                       'PaternalID': ['0', '0', 'dad', 'dad'], 'MaternalID': ['0', '0', 'mum', '0'],
                       'Sex': [1, 2, 2, 1], 'Phenotype': [1, 2, 1, 2]})
    drawing = studio_drawing(df)
    texts = [p['text'] for p in drawing['persons']]
    assert texts == ['dad', 'mum', 'kid', 'half', 'unknown parent']
    dad, mum, kid, half, unknown = drawing['persons']
    assert (dad['y'], mum['y'], unknown['y'], kid['y'], half['y']) == (MARGIN,)*3 + (MARGIN + ROW_GAP,)*2
    assert unknown['shape'] == 'unknown' and kid['x'] + CLOSEST <= half['x']
    assert len({p['x'] for p in (dad, mum, unknown)}) == 3
    links = {link['childId']: link['partnershipId'] for link in drawing['childLinks']}
    assert links[kid['id']] != links[half['id']]
    pships = {s['id']: {s['fromId'], s['toId']} for s in drawing['partnerships']}
    assert pships[links[half['id']]] == {dad['id'], unknown['id']}
    # and the PED file is the table, nothing more
    path = PED_export(df, str(tmp_path))
    assert open(path).read().splitlines()[2] == 'F\tkid\tdad\tmum\t2\t1'
