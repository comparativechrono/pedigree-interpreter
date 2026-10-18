'''
Draws the pedigrees that check.mjs reads with PedInterp under Pyodide, and writes the tables it should read from them.

The pedigrees are the tests' two-, three- and four-generation ones, each drawn with its labels and without, so run
this with the Python the tests run with: it needs pytest, Pillow, the DejaVu Sans font and PedInterp's dependencies.
The images and expected.json go in the folder work, next to this file.
'''
import json
import sys
from pathlib import Path

import numpy as np

here = Path(__file__).resolve().parent
# the tests, which draw the pedigrees, and PedInterp's source, which the tests import
sys.path[:0] = [str(here.parent), str(here.parent.parent / 'src')]

import test_core  # noqa: E402


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
    (work / 'expected.json').write_text(json.dumps({'numbered': numbered, 'read': read}, indent=1))
    print(f'Drew {len(numbered)} pedigrees in {work}')


if __name__ == '__main__':
    main()
