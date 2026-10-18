# Pedigree Interpreter Package

PedInterp reads an image of a clinical pedigree and turns it into a table laid out like a PED file, giving each person's parents, sex and affection status. The table can then be written out as a PED file.

## Prerequisites

PedInterp reads the labels in a drawing with the [Tesseract OCR engine](https://github.com/tesseract-ocr/tesseract), which has to be installed separately from the Python dependencies. The [Tesseract installation guide](https://tesseract-ocr.github.io/tessdoc/Installation.html) covers each operating system. On Ubuntu or Debian, for example:

```bash
sudo apt install tesseract-ocr
```

and on macOS, with Homebrew:

```bash
brew install tesseract
```

Without Tesseract, PedInterp still reads the drawing, but numbers the people by generation rather than reading their labels. This is also how it runs in a browser: see [Without Tesseract, and in a browser](#without-tesseract-and-in-a-browser).

## Installation

The Python dependencies are installed with the package:

```bash
pip install PedInterp
```

## Usage

```python
from PedInterp import pedigree_processing, PED_export

df = pedigree_processing('FAM1', raw_image_dir='images')   # reads images/FAM1.png
PED_export(df, output_dir='ped')                            # writes ped/FAM1.ped
```

**`pedigree_processing(FamID, raw_image_dir='.', export=False, output_dir='.', image_path=None, upscale_factor=10, ocr='tesseract')`** reads a pedigree image and returns a pandas DataFrame with the columns FamilyID, IndividualID, PaternalID, MaternalID, Sex (1 male, 2 female, 0 unknown) and Phenotype (1 unaffected, 2 affected). There is a row for each person, generation by generation, and from left to right within a generation. PaternalID and MaternalID are 0 for anyone whose parents aren't in the drawing.

- **FamID** (string): the family ID, which fills the FamilyID column. Unless `image_path` is given, the image read is `raw_image_dir/<FamID>.png`
- **raw_image_dir** (string): the folder the image is in (default: the working directory)
- **export** (bool): whether to write the PED file as well, as `output_dir/<FamID>.ped` (default: False)
- **output_dir** (string): the folder to write the PED file in, made if it doesn't exist (default: the working directory)
- **image_path** (string): the image to read, in place of `raw_image_dir/<FamID>.png`. Any format Pillow opens will do, JPEG included
- **upscale_factor** (number): how many times to enlarge the image before reading it (default: 10). The thresholds for lines and symbols are set in pixels and suit an image several thousand pixels across, so the default is right for an image a few hundred pixels across, such as a pedigree cut from a paper or a screenshot. For a larger image or a scan, a smaller factor gives much the same result more quickly and with less memory
- **ocr**: how to read the labels (default: `'tesseract'`). `None` or `'none'` numbers the people instead, and a function can read the labels with other OCR. See [Without Tesseract, and in a browser](#without-tesseract-and-in-a-browser)

The image is enlarged in memory, so nothing is written next to it.

**`PED_export(PED_df, output_dir='.')`** writes a DataFrame from `pedigree_processing` as a PED file, named after the family ID in its first row (`output_dir/<FamilyID>.ped`), and returns the file's path.

## What PedInterp expects of a drawing

PedInterp reads pedigrees drawn in the usual way, in black on white:

- squares for males, circles for females and diamonds for people whose sex isn't known
- the symbols of affected people filled in, and those of unaffected people left empty
- a label under each symbol, if the labels are to be read
- a horizontal line between partners, from which a line goes down to a line over their children (or straight down to an only child), with a short line from that down to each child
- each generation in a row of its own, if the people are to be numbered

Parents are worked out from the sex of the partners, so it doesn't matter which side the father is drawn on.

Some things aren't read yet:

- **labels of a single character**, which Tesseract seldom picks out. Labels of two or more characters, such as 12 or 101, are read well, but labels with Roman numerals, such as II-3, are often misread. Anyone whose label isn't read is given an ID from their place in the drawing instead, with a warning (see [When only some labels are read](#when-only-some-labels-are-read))
- **half-filled, shaded or hatched symbols**, such as those used for carriers. A half-filled symbol is left out. When the labels are read, a warning names its label, but when the people are numbered nothing shows that it was missed, and the others in its row are numbered as if it weren't there. The drawing is made black and white before the symbols are looked for, so a shaded symbol is read as filled if the shading is dark and as empty if it's light, and a hatched one as empty
- **a slash through the symbol of an unaffected person who has died**, which splits the symbol in two, so the person's sex may be misread
- **lines that slope**, as for twins, which are left out with a warning

OCR can misread a label (a 5 as a 3, say), so it's worth checking the table against the drawing.

## Without Tesseract, and in a browser

PedInterp doesn't need Tesseract, or pytesseract, to read a drawing. It imports without them, and it can number the people rather than read their labels. That lets it run in a browser under [Pyodide](https://pyodide.org), which provides OpenCV, numpy, pandas and Pillow but can't run the tesseract program.

### The `ocr` argument

- `'tesseract'`, the default, reads the labels with Tesseract. If pytesseract isn't installed, or the tesseract program can't be found or run (as under Pyodide), a warning says why, and the people are numbered instead
- `None` or `'none'` leaves the labels unread and numbers the people. This is also the better choice for a drawing without labels: with no real labels to measure it against, a symbol that Tesseract takes for a letter (a circle for an O) passes for a label, and is blanked out
- a function reads the labels with other OCR, such as tesseract.js in a browser: see [Reading the labels with other OCR](#reading-the-labels-with-other-ocr)

### Numbering

People are numbered in the usual way for pedigrees. Each row of symbols, from the top, is a generation, numbered in Roman numerals, and the people in a row are numbered from the left: the two people at the top of a drawing are I-1 and I-2, and those in the row below are II-1, II-2 and so on. Parents are given by the same IDs. A new row starts wherever the middle of a symbol is more than half a symbol's height below the one above it, so a symbol drawn a little out of line keeps its place in its row.

When the labels aren't read they are still in the drawing, so PedInterp keeps them from being taken for symbols or lines:

- the holes in letters and numbers (in 0, 6, 8, 9, A, B, D and so on) are white space inside an outline, like the inside of an unfilled symbol, but much smaller. Nothing less than three line widths across is taken for a symbol, and nor is anything less than 0.4 times the size of a typical symbol. The typical symbol is the median filled one, as text is never taken for a filled symbol, or, if none is filled, a size that nine in ten of the shapes found are smaller than. Line widths alone wouldn't do, as the lines of a drawing can be much thinner than the strokes of its text
- once the symbols have been found, every dark mark that doesn't reach a symbol's outline is cleared away before the lines are looked for. The lines all touch symbols, so they stay, while labels and stray marks go

Both are done when the labels are read as well, as OCR can miss some.

### When only some labels are read

Tesseract often misses labels of a single character, and any OCR can miss a label now and then. Anyone whose label wasn't read is given an ID from their place in the drawing, just as when the people are numbered (III-2, say), and a warning names them. If such an ID is the same as a label that was read, which can happen when the drawing's own labels are in the same style, a star is added to keep the two apart: II-3\*. If no labels are read at all, everyone is numbered, with a warning.

### Reading the labels with other OCR

`ocr` can be a function. PedInterp calls it with the image to be read, which is the drawing in grey as a numpy `uint8` array, enlarged as many times as `upscale_factor` but no more than three (Tesseract reads text best when it's a few tens of pixels high, and misreads labels enlarged ten times). The function returns the words it finds as an iterable of `(text, left, top, width, height)`, measured in that image's pixels. The words are then treated just as Tesseract's are: words without text are ignored, and so is anything much taller than the typical word, such as a symbol read as a letter. The rest are scaled up to the enlarged drawing, blanked out, and matched with the nearest symbols.

tesseract.js works asynchronously, and `pedigree_processing` can't wait for it, so in a browser the simplest way is to read the image with tesseract.js first, in the sparse text mode that PedInterp uses with Tesseract. For tesseract.js 7:

```js
const worker = await Tesseract.createWorker("eng");
await worker.setParameters({ tessedit_pageseg_mode: Tesseract.PSM.SPARSE_TEXT });
const { data } = await worker.recognize(imageFile, {}, { blocks: true });
const words = (data.blocks ?? []).flatMap((block) => block.paragraphs).flatMap((paragraph) => paragraph.lines)
  .flatMap((line) => line.words)
  .map(({ text, bbox }) => [text, bbox.x0, bbox.y0, bbox.x1 - bbox.x0, bbox.y1 - bbox.y0]);
pyodide.globals.set("words", pyodide.toPy(words));
```

then give `pedigree_processing` a function that scales the words' boxes from the image tesseract.js read to the one it is given:

```python
from PIL import Image
from PedInterp import pedigree_processing

width = Image.open('FAM1.png').width   # the width of the image tesseract.js read

def read_words(image):
    scale = image.shape[1] / width
    return [(text, left * scale, top * scale, w * scale, h * scale) for text, left, top, w, h in words]

df = pedigree_processing('FAM1', image_path='FAM1.png', ocr=read_words)
```

If the labels are small, tesseract.js may read them better from a copy of the image drawn two or three times larger on a canvas, with `width` then the canvas's width.

### Under Pyodide

PedInterp is plain Python, so it can be copied into Pyodide's file system with the image to read, after loading the packages it needs:

```js
const pyodide = await loadPyodide();
await pyodide.loadPackage(["numpy", "pandas", "opencv-python", "pillow"]);
pyodide.FS.mkdirTree("/home/pyodide/PedInterp");   // Pyodide starts in /home/pyodide, which is on Python's path
for (const file of ["__init__.py", "core.py"]) {
  pyodide.FS.writeFile(`/home/pyodide/PedInterp/${file}`, await (await fetch(`PedInterp/${file}`)).text());
}
pyodide.FS.writeFile("/home/pyodide/FAM1.png", new Uint8Array(await imageFile.arrayBuffer()));
const ped = pyodide.runPython(`
from PedInterp import pedigree_processing
pedigree_processing('FAM1', image_path='FAM1.png', ocr=None).to_csv(sep='\\t', header=False, index=False)
`);
```

Reading a drawing takes a few seconds, and a good deal of memory for a large one, as the image is enlarged. Under Pyodide in Node, the four-generation test drawing, 1200 by 740 pixels, took about 10 seconds to read when enlarged ten times, and Pyodide's memory grew to about 880 MB; enlarged five times, it took 3 seconds and under 300 MB, and gave the same table. In a browser, then, it's worth choosing `upscale_factor` so that the enlarged image is a few thousand pixels across rather than more, and running Pyodide in a web worker, so that the page doesn't freeze while it works.

### Checking PedInterp under Pyodide

The script `tests/pyodide/check.mjs` runs PedInterp under Pyodide 0.29.5 in Node. It copies PedInterp's source into Pyodide's file system with the test pedigrees, drawn beforehand in ordinary Python. Each pedigree is read with `ocr=None`, one again with an `ocr` function given words from JavaScript, as from tesseract.js, and one with the default `ocr`, which should warn that Tesseract can't be run. Every table is checked against the one it should be. It needs Node 18 or later, as Pyodide does:

```bash
cd tests/pyodide
npm install        # Pyodide 0.29.5
python draw.py     # draws the pedigrees, with the Python the tests run with
node check.mjs
```

The first time, Pyodide downloads the wheels it needs (numpy, pandas, opencv-python, Pillow and their dependencies) from its CDN, and keeps them in `tests/pyodide/packages`. If Node can't reach the CDN, for instance behind a proxy it doesn't use, `check.mjs` lists the files it's missing, and they can be downloaded into that folder by hand from `https://cdn.jsdelivr.net/pyodide/v0.29.5/full/`. The check isn't part of the GitHub workflow.

## Tests

The tests draw pedigrees to read, so they need the DejaVu Sans font as well as pytest. The tests that read the labels with Tesseract need Tesseract too, and are skipped without it; the others, which number the people or read the labels through an `ocr` function, don't.

```bash
pip install -e ".[test]"
pytest
```

## License

[MIT](https://choosealicense.com/licenses/mit/)
