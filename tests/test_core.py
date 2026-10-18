import os
import shutil

import numpy as np
import pandas as pd
import pytest
from PIL import Image, ImageDraw, ImageFont

from PedInterp import PED_export, pedigree_processing
from PedInterp.core import categorize_normalize_lines, detect_symbols, merge_duplicate_lines, stroke_width

needs_tesseract = pytest.mark.skipif(shutil.which('tesseract') is None, reason='needs the Tesseract OCR engine')

SYMBOL = 40   # the width of a symbol, in pixels
COLUMNS = ['IndividualID', 'PaternalID', 'MaternalID', 'Sex', 'Phenotype']


def draw_pedigree(path, people, couples, size, symbol=SYMBOL, line=3, **save_options):
    '''
    Draws a pedigree in the usual style, in black on white, with symbols symbol pixels across and lines line pixels wide.
    people: id -> (x, y, sex 'M', 'F' or 'U', affected), with (x, y) the middle of the person's symbol
    couples: (partner drawn on the left, partner drawn on the right, [children])
    '''
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
        draw.line([(lx + half, ly), (rx - half, ry)], fill='black', width=line)
        middle = (lx + rx) / 2
        sibship = people[children[0]][1] - half - 30
        draw.line([(middle, ly), (middle, sibship)], fill='black', width=line)
        xs = [people[child][0] for child in children] + [middle]
        draw.line([(min(xs), sibship), (max(xs), sibship)], fill='black', width=line)
        for child in children:
            cx, cy = people[child][:2]
            draw.line([(cx, sibship), (cx, cy - half)], fill='black', width=line)
    for person, (x, y, sex, affected) in people.items():
        box = [x - half, y - half, x + half, y + half]
        fill = 'black' if affected else 'white'
        if sex == 'M':
            draw.rectangle(box, outline='black', width=line, fill=fill)
        elif sex == 'F':
            draw.ellipse(box, outline='black', width=line, fill=fill)
        else:
            draw.polygon([(x, y - half), (x + half, y), (x, y + half), (x - half, y)], outline='black', width=line, fill=fill)
        draw.text((x, y + half + 8), str(person), fill='black', font=font, anchor='mt')
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
