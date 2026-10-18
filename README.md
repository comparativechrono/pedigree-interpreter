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

**`pedigree_processing(FamID, raw_image_dir='.', export=False, output_dir='.', image_path=None, upscale_factor=10)`** reads a pedigree image and returns a pandas DataFrame with the columns FamilyID, IndividualID, PaternalID, MaternalID, Sex (1 male, 2 female, 0 unknown) and Phenotype (1 unaffected, 2 affected). PaternalID and MaternalID are 0 for anyone whose parents aren't in the drawing.

- **FamID** (string): the family ID, which fills the FamilyID column. Unless `image_path` is given, the image read is `raw_image_dir/<FamID>.png`
- **raw_image_dir** (string): the folder the image is in (default: the working directory)
- **export** (bool): whether to write the PED file as well, as `output_dir/<FamID>.ped` (default: False)
- **output_dir** (string): the folder to write the PED file in, made if it doesn't exist (default: the working directory)
- **image_path** (string): the image to read, in place of `raw_image_dir/<FamID>.png`. Any format Pillow opens will do, JPEG included
- **upscale_factor** (number): how many times to enlarge the image before reading it (default: 10). The thresholds for lines and symbols are set in pixels and suit an image several thousand pixels across, so the default is right for an image a few hundred pixels across, such as a pedigree cut from a paper or a screenshot. For a larger image or a scan, a smaller factor gives much the same result more quickly and with less memory

The image is enlarged in memory, so nothing is written next to it.

**`PED_export(PED_df, output_dir='.')`** writes a DataFrame from `pedigree_processing` as a PED file, named after the family ID in its first row (`output_dir/<FamilyID>.ped`), and returns the file's path.

## What PedInterp expects of a drawing

PedInterp reads pedigrees drawn in the usual way, in black on white:

- squares for males, circles for females and diamonds for people whose sex isn't known
- the symbols of affected people filled in, and those of unaffected people left empty
- a label under each symbol
- a horizontal line between partners, from which a line goes down to a line over their children (or straight down to an only child), with a short line from that down to each child

Parents are worked out from the sex of the partners, so it doesn't matter which side the father is drawn on.

Some things aren't read yet:

- **labels of a single character**, which Tesseract seldom picks out. Labels of two or more characters, such as 12 or 101, are read well, but labels with Roman numerals, such as II-3, are often misread. A warning says how many symbols were left without a label
- **half-filled, shaded or hatched symbols**, such as those used for carriers. A half-filled symbol is left out, with a warning. The drawing is made black and white before the symbols are looked for, so a shaded symbol is read as filled if the shading is dark and as empty if it's light, and a hatched one as empty
- **a slash through the symbol of an unaffected person who has died**, which splits the symbol in two, so the person's sex may be misread
- **lines that slope**, as for twins, which are left out with a warning

OCR can misread a label (a 5 as a 3, say), so it's worth checking the table against the drawing.

## Tests

The tests draw pedigrees to read, so they need Tesseract and the DejaVu Sans font as well as pytest:

```bash
pip install -e ".[test]"
pytest
```

## License

[MIT](https://choosealicense.com/licenses/mit/)
