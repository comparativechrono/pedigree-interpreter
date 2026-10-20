'''
Draws the pedigrees that check.mjs reads with PedInterp under Pyodide, and writes the tables it should read from them.

The pedigrees are the tests' two-, three- and four-generation ones, each drawn with its labels and without; and, from
the tests of twins and sketches, a family with identical twins as Pedigree Studio draws it, and a family sketched by
hand, which is read with hand_drawn=True. Run this with the Python the tests run with: it needs pytest, Pillow,
OpenCV, the DejaVu Sans fonts and PedInterp's dependencies. The images and expected.json go in the folder work, next
to this file.
'''
import json
import sys
from pathlib import Path

import numpy as np

here = Path(__file__).resolve().parent
# the tests, which draw the pedigrees, and PedInterp's source, which the tests import
sys.path[:0] = [str(here.parent), str(here.parent.parent / 'src')]

import test_core  # noqa: E402
import test_twins_and_sketches as twins  # noqa: E402
from drawings import sketch_picture, studio_picture  # noqa: E402


def main():
    work = here / 'work'
    work.mkdir(exist_ok=True)
    numbered = {}
    for name, (drawing, rows) in test_core.NUMBERED.items():
        for labels in (True, False):
            case = f'{name}_generations' + ('' if labels else '_unlabelled')
            test_core.draw_pedigree(work / f'{case}.png', *drawing, labels=labels)
            numbered[case] = rows
    # the words that OCR would read in the three-generation pedigree, in the drawing's own pixels, as tesseract.js
    # might give them in a browser, and the table PedInterp should make with them
    people, _, size = test_core.THREE_GENERATIONS
    words = test_core.fake_ocr(people, size)(np.zeros((size[1], size[0]), np.uint8))
    read = {'three_generations': {'words': words, 'rows': test_core.THREE_GENERATIONS_READ}}
    # twins as Pedigree Studio draws them, and a family sketched by hand, with the twins they should be read with
    studio_picture(work / 'studio_twins.png', twins.TWINS, twins.TWINS_COUPLES, [('II-2', 'II-3', 'MZ')])
    sketch_picture(work / 'sketch.png', twins.SKETCH, twins.SKETCH_COUPLES, twins.SKETCH_TWINS, seed=0, pen=twins.RED,
                   width=4)
    more = {'studio_twins': {'rows': twins.TWINS_READ, 'twins': [['II-2', 'II-3', 'MZ']], 'hand_drawn': False},
            'sketch': {'rows': twins.SKETCH_READ, 'twins': [['II-2', 'II-3', 'DZ']], 'hand_drawn': True}}
    (work / 'expected.json').write_text(json.dumps({'numbered': numbered, 'read': read, 'more': more}, indent=1))
    print(f'Drew {len(numbered) + len(more)} pedigrees in {work}')


if __name__ == '__main__':
    main()
