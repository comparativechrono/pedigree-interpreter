import importlib.util
import os
import shutil
import subprocess
import sys
import warnings

import numpy as np
import pandas as pd
import pytest
from PIL import Image, ImageDraw, ImageFont

import PedInterp.core as core
from PedInterp import PED_export, pedigree_processing
from PedInterp.core import (SYMBOL_PIXELS, categorize_normalize_lines, choose_upscale, detect_symbols,
                            erase_loose_marks, generation_id, generation_places, merge_duplicate_lines, roman_numeral,
                            stroke_width)

needs_tesseract = pytest.mark.skipif(shutil.which('tesseract') is None or importlib.util.find_spec('pytesseract') is None,
                                     reason='needs the Tesseract OCR engine and pytesseract')

SYMBOL = 40   # the width of a symbol, in pixels
COLUMNS = ['IndividualID', 'PaternalID', 'MaternalID', 'Sex', 'Phenotype']


def draw_pedigree(path, people, couples, size, symbol=SYMBOL, line=3, labels=True, gap=0, slash=(), **save_options):
    '''
    Draws a pedigree in the usual style, in black on white, with symbols symbol pixels across and lines line pixels wide.
    people: id -> (x, y, sex 'M', 'F' or 'U', affected), with (x, y) the middle of the person's symbol
    couples: (partner drawn on the left, partner drawn on the right, [children])
    labels: whether to write each person's id under their symbol
    gap: how far short of the symbols the lines stop
    slash: the people whose symbols have a slash through them, as for someone who has died
    '''
    if labels:
        try:
            font = ImageFont.truetype('DejaVuSans.ttf', 22)
        except OSError:
            pytest.skip('needs the DejaVu Sans font to draw the labels')
    image = Image.new('RGB', size, 'white')
    draw = ImageDraw.Draw(image)
    half = symbol / 2
    for left, right, children in couples:
        lx, ly = people[left][:2]
        rx, ry = people[right][:2]
        draw.line([(lx + half + gap, ly), (rx - half - gap, ry)], fill='black', width=line)
        middle = (lx + rx) / 2
        sibship = people[children[0]][1] - half - 30
        draw.line([(middle, ly), (middle, sibship)], fill='black', width=line)
        xs = [people[child][0] for child in children] + [middle]
        draw.line([(min(xs), sibship), (max(xs), sibship)], fill='black', width=line)
        for child in children:
            cx, cy = people[child][:2]
            draw.line([(cx, sibship), (cx, cy - half - gap)], fill='black', width=line)
    for person, (x, y, sex, affected) in people.items():
        box = [x - half, y - half, x + half, y + half]
        fill = 'black' if affected else 'white'
        if sex == 'M':
            draw.rectangle(box, outline='black', width=line, fill=fill)
        elif sex == 'F':
            draw.ellipse(box, outline='black', width=line, fill=fill)
        else:
            draw.polygon([(x, y - half), (x + half, y), (x, y + half), (x - half, y)], outline='black', width=line, fill=fill)
        if labels:
            draw.text((x, y + half + 8), str(person), fill='black', font=font, anchor='mt')
        if person in slash:
            draw.line([(x - half - 6, y + half + 6), (x + half + 6, y - half - 6)], fill='black', width=line)
    image.save(path, **save_options)


def as_rows(df):
    return [[str(value) for value in row] for row in df[COLUMNS].values.tolist()]


TWO_GENERATIONS = ({101: (200, 80, 'M', True), 102: (440, 80, 'F', False),
                    201: (240, 260, 'M', True), 202: (400, 260, 'F', False)},
                   [(101, 102, [201, 202])], (640, 420))

# a daughter drawn to the left of the man who married into the family, a child whose sex isn't known,
# and a child drawn right under the partners' line
THREE_GENERATIONS = ({101: (260, 70, 'M', True), 102: (520, 70, 'F', False),
                      201: (200, 250, 'F', True), 202: (420, 250, 'M', False), 203: (640, 250, 'M', False),
                      301: (160, 430, 'M', True), 302: (310, 430, 'F', False), 303: (460, 430, 'U', False)},
                     [(101, 102, [201, 203]), (201, 202, [301, 302, 303])], (800, 560))
THREE_GENERATIONS_READ = [['101', '0', '0', '1', '2'],
                          ['102', '0', '0', '2', '1'],
                          ['201', '101', '102', '2', '2'],
                          ['202', '0', '0', '1', '1'],
                          ['203', '101', '102', '1', '1'],
                          ['301', '202', '201', '1', '2'],
                          ['302', '202', '201', '2', '1'],
                          ['303', '202', '201', '0', '1']]

# an only child, a woman who married into the family drawn to the left of her husband, and two-character labels
FOUR_GENERATIONS = ({11: (300, 70, 'M', True), 12: (560, 70, 'F', False),
                     21: (200, 250, 'F', False), 22: (420, 250, 'M', False),
                     24: (660, 250, 'F', False), 23: (880, 250, 'M', True),
                     31: (310, 430, 'M', True), 35: (480, 430, 'F', False),
                     32: (700, 430, 'F', True), 33: (880, 430, 'U', False), 34: (1060, 430, 'M', False),
                     41: (330, 610, 'F', True), 42: (470, 610, 'M', False)},
                    [(11, 12, [21, 23]), (21, 22, [31]), (24, 23, [32, 33, 34]), (31, 35, [41, 42])], (1200, 740))
FOUR_GENERATIONS_READ = {'11': ['0', '0', '1', '2'], '12': ['0', '0', '2', '1'],
                         '21': ['11', '12', '2', '1'], '22': ['0', '0', '1', '1'],
                         '23': ['11', '12', '1', '2'], '24': ['0', '0', '2', '1'],
                         '31': ['22', '21', '1', '2'], '35': ['0', '0', '2', '1'],
                         '32': ['23', '24', '2', '2'], '33': ['23', '24', '0', '1'], '34': ['23', '24', '1', '1'],
                         '41': ['31', '35', '2', '2'], '42': ['31', '35', '1', '1']}

# the same pedigrees with the people numbered rather than read: by generation, from the top, and from the left in each,
# and listed in that order
TWO_GENERATIONS_NUMBERED = [['I-1', '0', '0', '1', '2'],
                            ['I-2', '0', '0', '2', '1'],
                            ['II-1', 'I-1', 'I-2', '1', '2'],
                            ['II-2', 'I-1', 'I-2', '2', '1']]
THREE_GENERATIONS_NUMBERED = [['I-1', '0', '0', '1', '2'],
                              ['I-2', '0', '0', '2', '1'],
                              ['II-1', 'I-1', 'I-2', '2', '2'],
                              ['II-2', '0', '0', '1', '1'],
                              ['II-3', 'I-1', 'I-2', '1', '1'],
                              ['III-1', 'II-2', 'II-1', '1', '2'],
                              ['III-2', 'II-2', 'II-1', '2', '1'],
                              ['III-3', 'II-2', 'II-1', '0', '1']]
FOUR_GENERATIONS_NUMBERED = [['I-1', '0', '0', '1', '2'],
                             ['I-2', '0', '0', '2', '1'],
                             ['II-1', 'I-1', 'I-2', '2', '1'],
                             ['II-2', '0', '0', '1', '1'],
                             ['II-3', '0', '0', '2', '1'],
                             ['II-4', 'I-1', 'I-2', '1', '2'],
                             ['III-1', 'II-2', 'II-1', '1', '2'],
                             ['III-2', '0', '0', '2', '1'],
                             ['III-3', 'II-4', 'II-3', '2', '2'],
                             ['III-4', 'II-4', 'II-3', '0', '1'],
                             ['III-5', 'II-4', 'II-3', '1', '1'],
                             ['IV-1', 'III-1', 'III-2', '2', '2'],
                             ['IV-2', 'III-1', 'III-2', '1', '1']]
NUMBERED = {'two': (TWO_GENERATIONS, TWO_GENERATIONS_NUMBERED),
            'three': (THREE_GENERATIONS, THREE_GENERATIONS_NUMBERED),
            'four': (FOUR_GENERATIONS, FOUR_GENERATIONS_NUMBERED)}


def fake_ocr(people, size, read=None, extra=()):
    '''
    An OCR function, for pedigree_processing's ocr argument, that reads the labels draw_pedigree writes from where it
    writes them, as if it were perfect OCR. It keeps the images it is given in its list images.
    read: the text it reads for each person (the default is their label), or None for a label it misses
    extra: other words it reads, as (text, left, top, width, height) in the drawing's pixels
    '''
    font = ImageFont.truetype('DejaVuSans.ttf', 22)
    read = read or {}

    def ocr(image):
        ocr.images.append(image)
        # the image is the drawing enlarged, and the words' boxes must be in its pixels
        scale = image.shape[1] / size[0]
        words = []
        for person, (x, y, _, _) in people.items():
            text = read.get(person, str(person))
            if text is not None:
                left, top, right, bottom = font.getbbox(str(person), anchor='mt')
                top += y + SYMBOL / 2 + 8
                bottom += y + SYMBOL / 2 + 8
                words.append((text, scale * (x + left), scale * top, scale * (right - left), scale * (bottom - top)))
        return words + [(text, *(scale * value for value in box)) for text, *box in extra]

    ocr.images = []
    return ocr


@pytest.fixture
def two_generations(tmp_path):
    draw_pedigree(tmp_path / 'FAMC.png', *TWO_GENERATIONS)
    return tmp_path


@needs_tesseract
def test_two_generations(two_generations):
    df = pedigree_processing('FAMC', raw_image_dir=str(two_generations))
    assert list(df.columns) == ['FamilyID'] + COLUMNS
    assert (df['FamilyID'] == 'FAMC').all()
    assert as_rows(df) == [['101', '0', '0', '1', '2'],
                           ['102', '0', '0', '2', '1'],
                           ['201', '101', '102', '1', '2'],
                           ['202', '101', '102', '2', '1']]
    # the enlarged image is kept in memory, and nothing is written next to the original
    assert os.listdir(two_generations) == ['FAMC.png']


@needs_tesseract
@pytest.mark.parametrize('symbol, line', [(24, 3), (40, 6)])
def test_thick_lines_or_small_symbols(tmp_path, symbol, line):
    # the margin blanked out round each symbol grows with the lines' width: the lines must still reach the symbols
    draw_pedigree(tmp_path / 'FAMC.png', *TWO_GENERATIONS, symbol=symbol, line=line)
    df = pedigree_processing('FAMC', raw_image_dir=str(tmp_path))
    assert as_rows(df) == [['101', '0', '0', '1', '2'],
                           ['102', '0', '0', '2', '1'],
                           ['201', '101', '102', '1', '2'],
                           ['202', '101', '102', '2', '1']]


@needs_tesseract
def test_mother_drawn_on_the_left(tmp_path):
    draw_pedigree(tmp_path / 'FAMD.png',
                  {101: (200, 80, 'F', True), 102: (440, 80, 'M', False),
                   201: (240, 260, 'M', True), 202: (400, 260, 'F', False)},
                  [(101, 102, [201, 202])], size=(640, 420))
    df = pedigree_processing('FAMD', raw_image_dir=str(tmp_path))
    assert as_rows(df) == [['101', '0', '0', '2', '2'],
                           ['102', '0', '0', '1', '1'],
                           ['201', '102', '101', '1', '2'],
                           ['202', '102', '101', '2', '1']]


@needs_tesseract
def test_three_generations(tmp_path):
    draw_pedigree(tmp_path / 'pedigree.png', *THREE_GENERATIONS)
    df = pedigree_processing('FAME', image_path=str(tmp_path / 'pedigree.png'))
    assert as_rows(df) == THREE_GENERATIONS_READ


@needs_tesseract
@pytest.mark.parametrize('quality', [60, 85])
def test_jpeg(tmp_path, quality):
    # JPEG compression leaves a grey haze around the lines and the text
    draw_pedigree(tmp_path / 'pedigree.jpg', *THREE_GENERATIONS, quality=quality)
    df = pedigree_processing('FAME', image_path=str(tmp_path / 'pedigree.jpg'))
    assert as_rows(df) == THREE_GENERATIONS_READ


@needs_tesseract
def test_larger_image_enlarged_less(tmp_path):
    draw_pedigree(tmp_path / 'small.png', *THREE_GENERATIONS)
    small = Image.open(tmp_path / 'small.png')
    small.resize((small.width * 3, small.height * 3), Image.LANCZOS).save(tmp_path / 'large.png')
    df = pedigree_processing('FAME', image_path=str(tmp_path / 'large.png'), upscale_factor=3)
    assert as_rows(df) == THREE_GENERATIONS_READ


@needs_tesseract
def test_four_generations(tmp_path):
    draw_pedigree(tmp_path / 'FAMF.png', *FOUR_GENERATIONS)
    df = pedigree_processing('FAMF', raw_image_dir=str(tmp_path))
    read = {row[0]: row[1:] for row in as_rows(df)}
    assert read == FOUR_GENERATIONS_READ


@needs_tesseract
def test_export(two_generations, tmp_path):
    out = tmp_path / 'ped'
    df = pedigree_processing('FAMC', raw_image_dir=str(two_generations), export=True, output_dir=str(out))
    lines = (out / 'FAMC.ped').read_text().splitlines()
    assert len(lines) == len(df) == 4
    assert lines[2] == 'FAMC\t201\t101\t102\t1\t2'


def test_ped_export(tmp_path):
    df = pd.DataFrame({'FamilyID': ['F1', 'F1'], 'IndividualID': ['101', '102'], 'PaternalID': [0, 0],
                       'MaternalID': [0, 0], 'Sex': [1, 2], 'Phenotype': [2, 1]})
    path = PED_export(df, str(tmp_path / 'out'))
    assert os.path.basename(path) == 'F1.ped'
    assert open(path).read().splitlines() == ['F1\t101\t0\t0\t1\t2', 'F1\t102\t0\t0\t2\t1']


def test_symbols():
    # filled (affected) and empty (unaffected) squares, circles and diamonds, at the size of an enlarged image
    image = Image.new('L', (3000, 1400), 255)
    draw = ImageDraw.Draw(image)
    for row, fill in ((0, 0), (1, 255)):
        y = 350 + 700 * row
        for column, shape in enumerate('MFU'):
            x = 500 + 1000 * column
            box = [x - 200, y - 200, x + 200, y + 200]
            if shape == 'M':
                draw.rectangle(box, outline=0, width=30, fill=fill)
            elif shape == 'F':
                draw.ellipse(box, outline=0, width=30, fill=fill)
            else:
                draw.polygon([(x, y - 200), (x + 200, y), (x, y + 200), (x - 200, y)], outline=0, width=30, fill=fill)
        # lines joining the row's symbols, as between partners, which mustn't join them into one shape
        draw.line([(700, y), (1300, y)], fill=0, width=30)
        draw.line([(1700, y), (2300, y)], fill=0, width=30)
    gray = np.array(image)
    symbols, line_width = detect_symbols(gray, gray.size)
    assert line_width == 30
    found = sorted(((x + w // 2) // 1000, (y + h // 2) // 700, sex, phenotype) for (x, y, w, h), sex, phenotype in symbols)
    assert found == [(0, 0, 1, 2), (0, 1, 1, 1),
                     (1, 0, 2, 2), (1, 1, 2, 1),
                     (2, 0, 0, 2), (2, 1, 0, 1)]


def test_no_lines_found():
    # HoughLinesP returns None rather than an empty array when it finds no lines
    assert categorize_normalize_lines(None, 1000, 1000) == {'vertical': [], 'horizontal': []}


@pytest.mark.parametrize('shape', [(-1, 1, 4), (-1, 4)])
def test_lines_from_either_version_of_opencv(shape):
    # OpenCV 4 gives HoughLinesP's lines the shape (n, 1, 4), and OpenCV 5 the shape (n, 4).
    # Vertical lines come back from the bottom up and horizontal ones from left to right.
    lines = np.array([[100, 300, 100, 900], [700, 500, 100, 500]]).reshape(shape)
    out = categorize_normalize_lines(lines, 1000, 1000)
    assert out['vertical'] == [(100, 900, 100, 300)]
    assert out['horizontal'] == [(100, 500, 700, 500)]


def test_merging_lines():
    lines = {'horizontal': [(100, 500, 700, 500), (300, 520, 700, 520), (700, 490, 900, 490), (100, 900, 300, 900)],
             'vertical': [(100, 900, 100, 300), (120, 700, 120, 300), (2000, 900, 2000, 300)]}
    merged = merge_duplicate_lines(lines)
    # a line inside another, even sharing an end, is the same line, and lines that meet end to end are joined
    assert merged['horizontal'] == [(100, 500, 900, 500), (100, 900, 300, 900)]
    assert merged['vertical'] == [(100, 900, 100, 300), (2000, 900, 2000, 300)]


@pytest.mark.parametrize('order', [(0, 1, 2), (2, 1, 0), (0, 2, 1), (1, 0, 2)])
def test_merging_lines_in_any_order(order):
    # the third piece joins the other two, which don't touch each other
    pieces = [(100, 500, 300, 500), (600, 500, 900, 500), (250, 500, 650, 500)]
    merged = merge_duplicate_lines({'horizontal': [pieces[i] for i in order], 'vertical': []})
    assert merged['horizontal'] == [(100, 500, 900, 500)]


def test_line_width():
    mask = np.zeros((400, 400), np.uint8)
    mask[100:103, 20:380] = 255
    mask[20:380, 200:203] = 255
    assert stroke_width(mask) == 3


# Numbering people, without OCR. None of these tests needs Tesseract

@pytest.mark.parametrize('pedigree', ['two', 'three', 'four'])
def test_numbering_with_the_labels_left_in(tmp_path, pedigree):
    # the labels are drawn but not read, and must be taken neither for symbols nor for lines
    drawing, numbered = NUMBERED[pedigree]
    draw_pedigree(tmp_path / 'pedigree.png', *drawing)
    with warnings.catch_warnings():
        warnings.simplefilter('error', UserWarning)
        df = pedigree_processing('FAMN', image_path=str(tmp_path / 'pedigree.png'), ocr=None)
    assert list(df.columns) == ['FamilyID'] + COLUMNS
    assert as_rows(df) == numbered


@pytest.mark.parametrize('pedigree', ['two', 'three', 'four'])
def test_numbering_a_pedigree_without_labels(tmp_path, pedigree):
    drawing, numbered = NUMBERED[pedigree]
    draw_pedigree(tmp_path / 'pedigree.png', *drawing, labels=False)
    df = pedigree_processing('FAMN', image_path=str(tmp_path / 'pedigree.png'), ocr='none')
    assert as_rows(df) == numbered


@pytest.mark.parametrize('line', [1, 3])
@pytest.mark.parametrize('affected', [True, False])
def test_numbering_with_holes_in_the_labels(tmp_path, line, affected):
    # the holes in letters and numbers such as B, o, 6, 8, A, D, Q and 9 are white space inside an outline, like the
    # inside of an unfilled symbol. They must be left out even when the lines are thinner than the strokes of the text,
    # and when no symbol is filled, so that the filled symbols' size can't be compared with
    names = {101: 'Bob 68', 102: 'Ada 49', 201: 'D8 Q', 202: 'Pam 96'}
    people, couples, size = TWO_GENERATIONS
    people = {names[person]: (x, y, sex, was_affected and affected) for person, (x, y, sex, was_affected) in people.items()}
    couples = [(names[left], names[right], [names[child] for child in children]) for left, right, children in couples]
    draw_pedigree(tmp_path / 'pedigree.png', people, couples, size, line=line)
    df = pedigree_processing('FAMH', image_path=str(tmp_path / 'pedigree.png'), ocr=None)
    assert as_rows(df) == [row[:4] + [row[4] if affected else '1'] for row in TWO_GENERATIONS_NUMBERED]


def test_ocr_function(tmp_path):
    people, couples, size = THREE_GENERATIONS
    draw_pedigree(tmp_path / 'pedigree.png', *THREE_GENERATIONS)
    # as Tesseract does, the function also gives words without any text, and reads a circle as the letter O.
    # Such "text" is as tall as a symbol, and is left out, rather than being taken for a label and blanked out
    ocr = fake_ocr(people, size, extra=[('', 0, 0, *size), ('O', 500, 50, 40, 40)])
    df = pedigree_processing('FAME', image_path=str(tmp_path / 'pedigree.png'), ocr=ocr)
    assert as_rows(df) == THREE_GENERATIONS_READ
    # the function was given the drawing enlarged three times, in grey
    (image,) = ocr.images
    assert image.dtype == np.uint8
    assert image.shape == (3 * size[1], 3 * size[0])


def test_labels_that_were_not_read(tmp_path):
    # OCR misses two labels, which are left in the drawing: the two people are numbered by their place in it
    people, couples, size = THREE_GENERATIONS
    draw_pedigree(tmp_path / 'pedigree.png', *THREE_GENERATIONS)
    ocr = fake_ocr(people, size, read={202: None, 303: None})
    with pytest.warns(UserWarning, match=r'2 symbol\(s\) had no label .* instead: II-2, III-3\.'):
        df = pedigree_processing('FAME', image_path=str(tmp_path / 'pedigree.png'), ocr=ocr)
    assert as_rows(df) == [['101', '0', '0', '1', '2'],
                           ['102', '0', '0', '2', '1'],
                           ['201', '101', '102', '2', '2'],
                           ['II-2', '0', '0', '1', '1'],
                           ['203', '101', '102', '1', '1'],
                           ['301', 'II-2', '201', '1', '2'],
                           ['302', 'II-2', '201', '2', '1'],
                           ['III-3', 'II-2', '201', '0', '1']]


def test_number_that_is_also_a_label(tmp_path):
    # the drawing has labels of its own in the same style, but the man who married into the family is numbered last
    # in his generation. When OCR misses II-2, under the third symbol in the row, numbering it II-3 would give two
    # people the same ID, so it is marked with a star
    names = {101: 'I-1', 102: 'I-2', 201: 'II-1', 202: 'II-3', 203: 'II-2', 301: 'III-1', 302: 'III-2', 303: 'III-3'}
    people, couples, size = THREE_GENERATIONS
    people = {names[person]: place for person, place in people.items()}
    couples = [(names[left], names[right], [names[child] for child in children]) for left, right, children in couples]
    draw_pedigree(tmp_path / 'pedigree.png', people, couples, size)
    ocr = fake_ocr(people, size, read={'II-2': None})
    with pytest.warns(UserWarning, match=r'instead: II-3\*\.'):
        df = pedigree_processing('FAME', image_path=str(tmp_path / 'pedigree.png'), ocr=ocr)
    assert as_rows(df) == [['I-1', '0', '0', '1', '2'],
                           ['I-2', '0', '0', '2', '1'],
                           ['II-1', 'I-1', 'I-2', '2', '2'],
                           ['II-3', '0', '0', '1', '1'],
                           ['II-3*', 'I-1', 'I-2', '1', '1'],
                           ['III-1', 'II-3', 'II-1', '1', '2'],
                           ['III-2', 'II-3', 'II-1', '2', '1'],
                           ['III-3', 'II-3', 'II-1', '0', '1']]


def test_no_labels_read(two_generations):
    people, _, size = TWO_GENERATIONS
    ocr = fake_ocr(people, size, read={person: None for person in people})
    with pytest.warns(UserWarning, match='No labels were read'):
        df = pedigree_processing('FAMC', raw_image_dir=str(two_generations), ocr=ocr)
    assert as_rows(df) == TWO_GENERATIONS_NUMBERED


def test_without_pytesseract(two_generations, monkeypatch):
    # importing pytesseract fails while it is None in sys.modules
    monkeypatch.setitem(sys.modules, 'pytesseract', None)
    with pytest.warns(UserWarning, match="can't be read with Tesseract, as pytesseract is not installed"):
        df = pedigree_processing('FAMC', raw_image_dir=str(two_generations))
    assert as_rows(df) == TWO_GENERATIONS_NUMBERED


def test_without_the_tesseract_program(two_generations, monkeypatch):
    pytesseract = pytest.importorskip('pytesseract')
    monkeypatch.setattr(pytesseract.pytesseract, 'tesseract_cmd', str(two_generations / 'no-tesseract-here'))
    with pytest.warns(UserWarning, match="can't be read with Tesseract, as the tesseract program was not found"):
        df = pedigree_processing('FAMC', raw_image_dir=str(two_generations))
    assert as_rows(df) == TWO_GENERATIONS_NUMBERED


def test_imports_without_pytesseract():
    code = "import sys; sys.modules['pytesseract'] = None; import PedInterp; print('imported')"
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.stdout.strip() == 'imported', result.stderr


def test_unknown_ocr():
    with pytest.raises(ValueError, match='ocr must be'):
        pedigree_processing('FAMC', ocr='tesseract.js')


def test_roman_numerals():
    assert [roman_numeral(n) for n in (1, 2, 3, 4, 5, 9, 10, 14, 40, 90, 400, 1994)] == \
        ['I', 'II', 'III', 'IV', 'V', 'IX', 'X', 'XIV', 'XL', 'XC', 'CD', 'MCMXCIV']


def test_generation_places():
    # the symbols of a row needn't be drawn quite level, and come in any order
    boxes = [(500, 105, 40, 40), (100, 100, 40, 40), (300, 112, 40, 40), (200, 300, 40, 40), (50, 290, 40, 40)]
    assert generation_places(boxes) == [(0, 2), (0, 0), (0, 1), (1, 1), (1, 0)]
    assert generation_id(1, 0) == 'II-1'


def test_erasing_loose_marks():
    image = np.full((100, 300), 255, np.uint8)
    image[40:60, 10:30] = 0      # a symbol
    image[49:51, 30:200] = 0     # a line from it
    image[40:60, 250:260] = 0    # a mark that touches neither
    erase_loose_marks(image, [(5, 35, 35, 65)])
    assert (image[40:60, 10:30] == 0).all() and (image[49:51, 30:200] == 0).all()
    assert (image[40:60, 250:260] == 255).all()


# Drawings that the steps for reading without Tesseract must not make worse

@pytest.mark.parametrize('gap', [4, 6])
def test_lines_that_stop_short_of_the_symbols(tmp_path, gap):
    # the lines stop a little short of the symbols: they must be kept, not cleared away as stray marks
    people, couples, size = THREE_GENERATIONS
    draw_pedigree(tmp_path / 'pedigree.png', *THREE_GENERATIONS, gap=gap)
    df = pedigree_processing('FAMG', image_path=str(tmp_path / 'pedigree.png'), ocr=fake_ocr(people, size))
    assert as_rows(df) == THREE_GENERATIONS_READ


@pytest.mark.parametrize('symbol,line', [(40, 9), (34, 7), (30, 6)])
def test_bold_lines(tmp_path, symbol, line):
    # an unfilled symbol is found by the white inside it, which thick lines make much smaller than the symbol
    people, couples, size = THREE_GENERATIONS
    draw_pedigree(tmp_path / 'pedigree.png', *THREE_GENERATIONS, symbol=symbol, line=line, labels=False)
    df = pedigree_processing('FAMB', image_path=str(tmp_path / 'pedigree.png'), ocr=None)
    rows = as_rows(df)
    # everyone is found, affected or not. (The sex of a filled symbol drawn with lines this thick can still be
    # misread, as before: the corners of a filled square are worn away with the lines)
    assert [row[4] for row in rows] == [row[4] for row in THREE_GENERATIONS_NUMBERED]
    assert [row[3] for row in rows if row[4] == '1'] == [row[3] for row in THREE_GENERATIONS_NUMBERED if row[4] == '1']


def test_a_slash_through_a_symbol(tmp_path):
    # a slash cuts the white inside 102's circle in two: one woman, not two people
    people, couples, size = THREE_GENERATIONS
    draw_pedigree(tmp_path / 'pedigree.png', *THREE_GENERATIONS, slash=(102,))
    df = pedigree_processing('FAMS', image_path=str(tmp_path / 'pedigree.png'), ocr=fake_ocr(people, size))
    assert as_rows(df) == THREE_GENERATIONS_READ


# Families laid out as Pedigree Studio lays them out: each child straight under a parent, and the generations close
# together. Hough carries a line on across gaps, the blank where a symbol was taken out among them, so the line down to
# a child was joined to the line down to the parent drawn above them, and the child was given their grandparents

# the Lynch family of the pedigree practical, where the Studio draws it, with slashes for those who have died
LYNCH = ({101: (491, 60, 'M', True), 102: (595, 60, 'F', False),
          201: (218, 190, 'F', False), 202: (322, 190, 'M', True), 203: (764, 190, 'M', True), 204: (868, 190, 'F', False),
          301: (62, 320, 'M', False), 302: (166, 320, 'F', True), 303: (296, 320, 'F', True), 304: (504, 320, 'F', False),
          305: (608, 320, 'M', False), 306: (764, 320, 'M', False), 307: (894, 320, 'M', False), 308: (998, 320, 'F', False),
          401: (62, 450, 'F', False), 402: (166, 450, 'F', False), 403: (504, 450, 'F', False), 404: (608, 450, 'F', False),
          405: (894, 450, 'F', False), 406: (998, 450, 'M', False)},
         [(101, 102, [202, 203]), (201, 202, [302, 303, 304]), (203, 204, [306, 307]),
          (301, 302, [401, 402]), (304, 305, [403, 404]), (307, 308, [405, 406])], (1060, 520))
LYNCH_DIED = (101, 102, 202, 302)
LYNCH_NUMBERED = [['I-1', '0', '0', '1', '2'], ['I-2', '0', '0', '2', '1'],
                  ['II-1', '0', '0', '2', '1'], ['II-2', 'I-1', 'I-2', '1', '2'],
                  ['II-3', 'I-1', 'I-2', '1', '2'], ['II-4', '0', '0', '2', '1'],
                  ['III-1', '0', '0', '1', '1'], ['III-2', 'II-2', 'II-1', '2', '2'],
                  ['III-3', 'II-2', 'II-1', '2', '2'], ['III-4', 'II-2', 'II-1', '2', '1'],
                  ['III-5', '0', '0', '1', '1'], ['III-6', 'II-3', 'II-4', '1', '1'],
                  ['III-7', 'II-3', 'II-4', '1', '1'], ['III-8', '0', '0', '2', '1'],
                  ['IV-1', 'III-1', 'III-2', '2', '1'], ['IV-2', 'III-1', 'III-2', '2', '1'],
                  ['IV-3', 'III-5', 'III-4', '2', '1'], ['IV-4', 'III-5', 'III-4', '2', '1'],
                  ['IV-5', 'III-7', 'III-8', '2', '1'], ['IV-6', 'III-7', 'III-8', '1', '1']]


@pytest.mark.parametrize('slash', [(), LYNCH_DIED])
@pytest.mark.parametrize('labels', [True, False])
def test_children_drawn_under_their_parents(tmp_path, slash, labels):
    draw_pedigree(tmp_path / 'lynch.png', *LYNCH, slash=slash, labels=labels)
    with warnings.catch_warnings():
        warnings.simplefilter('error', UserWarning)
        df = pedigree_processing('LYNCH', image_path=str(tmp_path / 'lynch.png'), ocr=None)
    assert as_rows(df) == LYNCH_NUMBERED


def test_partners_on_either_side(tmp_path):
    # a man with a partner on each side, and a child with each: the lines to the two partners are not one line
    people = {101: (300, 70, 'F', False), 102: (460, 70, 'M', True), 103: (620, 70, 'F', False),
              201: (380, 250, 'M', True), 202: (540, 250, 'F', False)}
    couples = [(101, 102, [201]), (102, 103, [202])]
    draw_pedigree(tmp_path / 'pedigree.png', people, couples, (1000, 400), labels=False)
    df = pedigree_processing('FAMP', image_path=str(tmp_path / 'pedigree.png'), ocr=None)
    assert as_rows(df) == [['I-1', '0', '0', '2', '1'], ['I-2', '0', '0', '1', '2'], ['I-3', '0', '0', '2', '1'],
                           ['II-1', 'I-2', 'I-1', '1', '2'], ['II-2', 'I-2', 'I-3', '2', '1']]


def test_enlarged_to_suit_its_symbols(tmp_path):
    # by default a picture is enlarged so that its symbols are about SYMBOL_PIXELS across, whatever its size: one drawn
    # three times as large is enlarged a third as much, and both are read correctly
    draw_pedigree(tmp_path / 'small.png', *THREE_GENERATIONS, labels=False)
    small = Image.open(tmp_path / 'small.png')
    small.resize((small.width * 3, small.height * 3), Image.LANCZOS).save(tmp_path / 'large.png')
    factors = [choose_upscale(str(tmp_path / name)) for name in ('small.png', 'large.png')]
    assert 0.7 * SYMBOL_PIXELS < factors[0] * SYMBOL < 1.3 * SYMBOL_PIXELS
    assert factors[1] == pytest.approx(factors[0] / 3, rel=0.1)
    for name, factor in zip(('small.png', 'large.png'), factors):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            df = pedigree_processing('FAMS', image_path=str(tmp_path / name), ocr=None)
        assert as_rows(df) == THREE_GENERATIONS_NUMBERED and df.attrs['upscale_factor'] == factor


def test_never_enlarged_past_max_pixels(tmp_path, monkeypatch):
    draw_pedigree(tmp_path / 'p.png', *THREE_GENERATIONS, labels=False)
    width, height = Image.open(tmp_path / 'p.png').size
    monkeypatch.setattr(core, 'MAX_PIXELS', 4 * width * height)
    assert choose_upscale(str(tmp_path / 'p.png')) <= 2


def test_a_picture_without_symbols_is_enlarged_to_5000_pixels(tmp_path):
    Image.new('RGB', (1000, 600), 'white').save(tmp_path / 'blank.png')
    assert choose_upscale(str(tmp_path / 'blank.png')) == 5


@pytest.mark.parametrize('factor, warned', [(1, "No one's parents were found, though the symbols are in 3 rows"),
                                            (2, 'joined to no one')])
def test_missed_lines_are_warned(tmp_path, factor, warned):
    # enlarged too little, this drawing loses some of its lines: a warning says so, and how much it was enlarged
    draw_pedigree(tmp_path / 'p.png', *THREE_GENERATIONS, labels=False)
    with pytest.warns(UserWarning, match=warned) as caught:
        pedigree_processing('FAMW', image_path=str(tmp_path / 'p.png'), ocr=None, upscale_factor=factor)
    assert any(f'enlarged {factor} times' in str(w.message) for w in caught)


def test_one_parent_is_warned(tmp_path, monkeypatch):
    # as when the line to one partner is missed
    real = core.trackRelation

    def lose_a_mother(lines, people):
        people, connections = real(lines, people)
        people['III-1']['MaternalID'] = 0
        return people, connections

    monkeypatch.setattr(core, 'trackRelation', lose_a_mother)
    draw_pedigree(tmp_path / 'p.png', *THREE_GENERATIONS, labels=False)
    with pytest.warns(UserWarning, match='III-1: only a father was found'):
        pedigree_processing('FAMW', image_path=str(tmp_path / 'p.png'), ocr=None)


def test_no_symbols_suggests_cutting_the_picture_down(tmp_path):
    Image.new('RGB', (400, 300), 'white').save(tmp_path / 'blank.png')
    with pytest.raises(ValueError, match='cut the picture down to the pedigree'):
        pedigree_processing('FAMB', image_path=str(tmp_path / 'blank.png'), ocr=None)
