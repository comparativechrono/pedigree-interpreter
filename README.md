# Pedigree Interpreter Package

PedInterp reads an image of a clinical pedigree, drawn with software such as [Pedigree Studio](https://github.com/comparativechrono/pedigreestudio) or sketched by hand, and turns it into a table laid out like a PED file, giving each person's parents, sex and affection status, and which children are twins. The table can then be written out as a PED file; as a GA4GH Pedigree, which can hold the twins as well; or as a Pedigree Studio drawing, laid out as the picture was, which turns a pedigree sketched by hand into one to carry on with in the Studio. Asked to, it also reads the marks drawn on the symbols: who has died, the proband and carriers (see [Deaths, probands and carriers](#deaths-probands-and-carriers)).

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

The Python dependencies are installed with the package, which needs Python 3.9 or later:

```bash
pip install PedInterp
```

## Usage

```python
from PedInterp import pedigree_processing, PED_export, GA4GH_export, Studio_export

df = pedigree_processing('FAM1', raw_image_dir='images')   # reads images/FAM1.png
PED_export(df, output_dir='ped')                            # writes ped/FAM1.ped
GA4GH_export(df, output_dir='ped')                          # writes ped/FAM1_ga4gh-pedigree.json

sketch = pedigree_processing('FAM2', image_path='sketch.png', hand_drawn=True)   # a pedigree sketched by hand
sketch.attrs['twins']                                                         # e.g. [['II-2', 'II-3', 'MZ']]
Studio_export(sketch, output_dir='drawings')   # writes drawings/FAM2.studio.json, to open in Pedigree Studio

marked = pedigree_processing('FAM2', image_path='sketch.png', hand_drawn=True, marks=True)   # deaths, the proband, carriers
marked[['IndividualID', 'Deceased', 'Proband', 'Carrier']]                  # True or False for each person
Studio_export(marked, output_dir='drawings')   # with them drawn; PED_export refuses the table, as a PED file can't hold them
```

**`pedigree_processing(FamID, raw_image_dir='.', export=False, output_dir='.', image_path=None, upscale_factor=None, ocr='auto', hand_drawn=False, marks=False)`** reads a pedigree image and returns a pandas DataFrame with the columns FamilyID, IndividualID, PaternalID, MaternalID, Sex (1 male, 2 female, 0 unknown) and Phenotype (1 unaffected, 2 affected), and with `marks=True`, Deceased, Proband and Carrier. There is a row for each person, generation by generation, and from left to right within a generation. PaternalID and MaternalID are 0 for anyone whose parents aren't in the drawing. What a PED file can't hold is kept in the DataFrame's `attrs`, out of the table and the PED file, for the GA4GH Pedigree and the Studio drawing: the twins (`df.attrs['twins']`: see [Twins](#twins)), the couples joined by a line, with children or without (`df.attrs['partners']`), and where each person was drawn (`df.attrs['layout']`, by ID: the box round their symbol in the picture's pixels, the row of symbols they are in, counted from 0 at the top, and the symbol's shape: `square`, `circle`, `diamond` or `triangle`).

- **FamID** (string): the family ID, which fills the FamilyID column. Unless `image_path` is given, the image read is `raw_image_dir/<FamID>.png`
- **raw_image_dir** (string): the folder the image is in (default: the working directory)
- **export** (bool): whether to write the PED file as well, as `output_dir/<FamID>.ped` (default: False)
- **output_dir** (string): the folder to write the PED file in, made if it doesn't exist (default: the working directory)
- **image_path** (string): the image to read, in place of `raw_image_dir/<FamID>.png`. Any format Pillow opens will do, JPEG included
- **upscale_factor** (number): how many times to enlarge the image before reading it. The symbols are found best at about 200 pixels across (`SYMBOL_PIXELS`), or 100 for a sketch (`SKETCH_PIXELS`), so by default PedInterp measures the symbols in a copy of the image 2,000 pixels across on its longer side, and enlarges the image by as much as makes them that size (`choose_upscale(image_path)` gives the factor, rounded down to one decimal place, and the result records it in `df.attrs['upscale_factor']`). A pedigree cut from a paper may be enlarged ten times or more, and a scan or a photograph much less, or even made smaller, which is quicker and takes less memory. The factor is kept between 0.25 and 20, and the enlarged image never has more than 60 million pixels (`MAX_PIXELS`). When a limit keeps it well short of what the symbols need, a warning says so: a larger copy of a very small picture would read better, and a page with a small pedigree on it should be cut down to the pedigree
- **ocr**: how to read the labels (default: `'auto'`, which is `'tesseract'` unless `hand_drawn` is given, when the people are numbered). `None` or `'none'` numbers the people instead, and a function can read the labels with other OCR. See [Without Tesseract, and in a browser](#without-tesseract-and-in-a-browser)
- **hand_drawn** (bool): whether the pedigree is sketched by hand, in whole or in part, as with Pedigree Studio's Draw tool (default: False). See [Pedigrees drawn by hand](#pedigrees-drawn-by-hand)
- **marks** (bool): whether to read the marks drawn on the symbols as well as their shapes and fills (default: False): a slash through the symbol of someone who has died, an arrow pointing at the proband's symbol, and a dot in the middle of a carrier's. The DataFrame then has three more columns, Deceased, Proband and Carrier, each True or False. A PED file can't hold them, so `export=True` can't be given with them. See [Deaths, probands and carriers](#deaths-probands-and-carriers)

The image is enlarged in memory, so nothing is written next to it.

**`PED_export(PED_df, output_dir='.')`** writes a DataFrame from `pedigree_processing` as a PED file, named after the family ID in its first row (`output_dir/<FamilyID>.ped`), and returns the file's path. A DataFrame read with `marks=True` has marks a PED file can't hold, and `PED_export` raises a `ValueError` rather than lose them: it refuses any DataFrame with a column Deceased, Proband or Carrier, and `df.drop(columns=['Deceased', 'Proband', 'Carrier'])` leaves the rest, to write as a PED file.

**`GA4GH_export(PED_df, output_dir='.', condition=None)`** writes it as a GA4GH Pedigree (`output_dir/<FamilyID>_ga4gh-pedigree.json`), and returns the file's path. It is the form that [studio2ga4gh](https://github.com/comparativechrono/studio2ga4gh) writes and the lab's other GA4GH tools read, such as ga4gh2studio, phenopacket-toolkit and [PedNet](https://github.com/comparativechrono/PedNet): each person is a Phenopacket, and each parent is joined to their children by a relationship (`KIN:028` for a father, `KIN:027` for a mother). Twins are written as studio2ga4gh writes them: each twin is related to the first of their set, on the left, as an identical twin (`KIN:010`, isMonozygoticMultipleBirthSiblingOf) or a non-identical one (`KIN:011`, isPolyzygoticMultipleBirthSiblingOf), and the narrative names them. So are the marks of a DataFrame read with `marks=True`: the proband is an index patient (`indexPatients`) and is named in the narrative, and the narrative says who is a carrier, as a Phenopacket has no place for that. Each person's vital status is `DECEASED` if a slash was read through their symbol, or if it is a triangle, for a pregnancy lost (as studio2ga4gh writes the Studio's, with a note in the narrative), and `ALIVE` if their symbol is left empty with no slash through it. A symbol filled in may hide a slash, as it hides the Studio's through a filled square, so the affected have no vital status unless a slash was seen. Without marks, no vital status or index patient is written, as nothing was read of them. It is written with [pedigree-ga4gh](https://github.com/comparativechrono/pedigree-ga4gh), which is installed with PedInterp.

- **condition** (pair of strings, optional): the condition the pedigree is about, as an ontology term and its label, such as `('MONDO:0007739', 'Huntington disease')`, or an HPO term such as `('HP:0000365', 'Hearing impairment')`, which is written as a phenotype rather than a disease (default: `('MONDO:0000001', 'disease')`, Mondo's most general term, as a picture doesn't say what the condition is). A GA4GH Pedigree records who is affected only through their conditions, so the affected have it, and the unaffected have it marked as excluded (looked for, and not found), so that their phenotypes can be read back from the file as they are in the PED file. The narrative names the picture, and how many times it was enlarged.

**`Studio_export(PED_df, output_dir='.', condition=None)`** writes it as a [Pedigree Studio](https://github.com/comparativechrono/pedigreestudio) drawing (`output_dir/<FamilyID>.studio.json`), and returns the file's path: open it in the Studio to carry on with the drawing, as when a pedigree has been sketched quickly and is wanted as a proper drawing. It is laid out as the picture was, a row of symbols to a generation, at the Studio's sizes, and spaced out a little where the picture's symbols are closer together than the Studio's (the Studio's **Tidy** lays it out afresh). The affected are filled in, with a colour key that names the condition, given as for `GA4GH_export` (as `Huntington disease [MONDO:0007739]`, which studio2ga4gh reads back as that term), or says "Affected"; twins are drawn as twins, identical or not, couples without children are joined, and a triangle, for a pregnancy lost, is the Studio's symbol for one. A child with only one parent in the table is given an unknown parent for the line to come from, as ga4gh2studio gives one. People numbered as the Studio numbers them (I-1, II-3) show the Studio's numbers, and anyone with a label of their own has it written under their symbol. A DataFrame that wasn't read from a picture is drawn by generation, in the order of its rows. The file is in the form the Studio saves, which [studio2ped](https://github.com/comparativechrono/studio2ped) and [studio2ga4gh](https://github.com/comparativechrono/studio2ga4gh) read: studio2ped gives back the PED file PedInterp writes. The marks of a DataFrame read with `marks=True` are drawn as the Studio draws them: a slash through the symbol of someone who has died, the proband's arrow and a carrier's dot, which studio2ga4gh reads back.

## From the command line

Installing PedInterp also installs the `pedinterp` command, which reads a picture of a pedigree and writes the PED file:

```bash
pedinterp FAM1.png -d ped                  # writes ped/FAM1.ped
pedinterp scan.jpg -f FAM2 --labels none   # numbers the people rather than reading their labels
pedinterp FAM1.png --ga4gh --condition MONDO:0007739 "Huntington disease"   # FAM1.ped and FAM1_ga4gh-pedigree.json
pedinterp sketch.png --hand-drawn --studio # a pedigree sketched by hand: sketch.ped, and sketch.studio.json to open in Pedigree Studio
pedinterp sketch.png --hand-drawn --marks --studio   # who has died, the proband and carriers too, in sketch.studio.json only
```

The family ID is the picture's name without its ending, unless `-f` gives another, and the PED file is named after it. The PED file's table is printed too, as it is in the file, with how many times the picture was enlarged under it, unless `-q` is given. `--upscale` does what `upscale_factor` does, `--labels none` what `ocr=None` does, and `--hand-drawn` what `hand_drawn=True` does (and then the labels aren't read unless `--labels tesseract` is given). `--ga4gh` writes the GA4GH Pedigree too, as `GA4GH_export` does, and `--studio` the Pedigree Studio drawing, as `Studio_export` does, with `--condition ID LABEL` for the condition in either. `--marks` does what `marks=True` does: the table printed has the columns Deceased, Proband and Carrier, and as a PED file can't hold them, no PED file is written, so `--studio`, `--ga4gh` or both must be given to say what is. If the picture can't be read, or has no pedigree in it, the command says why and exits with status 1; warnings, such as one for a label that wasn't matched to a symbol, are printed without stopping it. `pedinterp --help` lists the options.

## What PedInterp expects of a drawing

PedInterp reads pedigrees drawn in the usual way, dark on white:

- squares for males, circles for females and diamonds for people whose sex isn't known; a triangle, for a pregnancy that was lost, is read as someone whose sex isn't known, as studio2ped writes it
- the symbols of affected people filled in, and those of unaffected people left empty. Any colour is dark enough, as the darkest of a pixel's red, green and blue is what counts, so a symbol filled in yellow, as Pedigree Studio may fill one, is filled
- a label by each symbol, if the labels are to be read
- a line between partners, from which a line goes down to a line over their children (or straight down to an only child), with a short line from that down to each child; twins are joined to one point of the line over the children by two slanting lines, with a bar between them if they are identical
- each generation in a row of its own, if the people are to be numbered

Parents are worked out from the sex of the partners, so it doesn't matter which side the father is drawn on.

The lines are read as networks: once the symbols are blanked out, the lines that join a couple to each other and to their children are joined to one another and to nothing else, so each network of lines is a family. Where a line ends at a symbol, it meets the symbol from the side, as a partner's line does, or from above, as the line down to a child does, straight or slanting. A line that ends near no symbol, having stopped a little short of the line it was meant to meet, is joined to the line it points at. Nothing depends on the lines being straight, level or upright, which is what lets PedInterp read twins and sketches.

Some things aren't read yet:

- **labels of a single character**, which Tesseract seldom picks out. Labels of two or more characters, such as 12 or 101, are read well, but labels with Roman numerals, such as II-3, are often misread. Anyone whose label isn't read is given an ID from their place in the drawing instead, with a warning (see [When only some labels are read](#when-only-some-labels-are-read))
- **half-filled, shaded or hatched symbols**, such as those sometimes used for carriers (a carrier's dot is read with `marks=True`: see [Deaths, probands and carriers](#deaths-probands-and-carriers)). A half-filled symbol is left out. When the labels are read, a warning names its label, but when the people are numbered nothing shows that it was missed, and the others in its row are numbered as if it weren't there. The drawing is made black and white before the symbols are looked for, so a shaded symbol is read as filled if the shading is dark and as empty if it's light, and a hatched one as empty
- **a slash through the symbol of an unaffected person who has died**, which splits the white inside the symbol in two. The two pieces are joined again, and the symbol's shape is taken from the outline round both, but a slash at an odd angle can still lead to the sex being misread
- **lines of descent other than parents'**, such as adoption, and partners who have no children together, which a PED file can't hold

OCR can misread a label (a 5 as a 3, say), so it's worth checking the table against the drawing. Tesseract often misreads small Roman numerals, such as the numbers Pedigree Studio writes over its symbols (III-2 as Il-2, say); as they are the same numbering that PedInterp gives when it numbers the people, a picture from the Studio reads more quickly and as well with `ocr=None` (`--labels none`).

## Twins

Twins are read from the lines that join them to their parents' line: two children side by side whose lines slant towards each other and meet at a point above them. They are identical if a bar is drawn across between their lines, below that point. Where the lines meet is found both by fitting each line near its twin and by following the two along the skeleton to where they join: in a sketch, the lines may bend as they come to the twins, running close over the tops of their symbols, and fitted near their ends they don't point to where they meet. `df.attrs['twins']` lists each pair as `[twin, twin, 'MZ']` for identical twins or `'DZ'` for twins who aren't, with the twin on the left first; triplets are two pairs. The twins are children of their parents like their brothers and sisters, and their lines may be long and nearly level, as the Studio draws them when the twins are far apart, with families of their own. Two brothers' or sisters' lines that lean towards each other, so that they come within about a symbol's width of each other at the top, are taken for twins' lines too, so lines down to children who aren't twins are best drawn upright.

The triangle that identical twins' lines make with their bar is white closed in by lines, like the inside of a symbol, and was read as one: someone of unknown sex, a diamond, between the twins and their parents, which put the twins' row wrong. A small shape with lines leading down from it to two or more people, and to no one else, is now known for the point the twins' lines come from, and the people are numbered without it.

A PED file can't hold twins, and `PED_export` and the table `pedinterp` prints leave them out, but `GA4GH_export` and `Studio_export` write them.

## Pedigrees drawn by hand

`hand_drawn=True` (`--hand-drawn`) reads a pedigree sketched by hand, in whole or in part: drawn with a pen or a mouse, as with Pedigree Studio's Draw tool, or begun with the Studio's symbols and finished by hand. It allows for what makes a sketch rough:

- symbols of unequal sizes, down to about four tenths of the typical one
- outlines that don't quite close, or run on past where they began, and symbols drawn in two strokes
- filled symbols scribbled or hatched in, rather than filled solid
- lines that wobble and slope, stop short of what they join or run a little past it, and a line down to a child drawn as a stroke of its own, not quite meeting the line above
- any pen colour darker than a light grey

The picture is read at a size where its symbols are about 100 pixels across, which is about the size Pedigree Studio saves its pictures at, and the labels aren't read unless asked for, as labels written by hand can't be, and Tesseract may take the strokes that fill a symbol in for letters.

To turn a sketch into a Pedigree Studio drawing, write it with `Studio_export` (`--studio`): `pedinterp sketch.png --hand-drawn --studio` writes `sketch.studio.json`, laid out as the sketch is, which the Studio opens.

Sketches are read well, but not as surely as drawings. On 96 pedigrees drawn with Pedigree Studio and its Draw tool for testing, and kept apart from those used in making these changes (a quarter drawn with the Studio's symbols, with twins, a quarter begun with them and finished by hand, and half sketched throughout, with symbols from about 0.6 to 1.4 times the size of the Studio's), it read every person right in all 24 drawn with symbols, 23 of the 24 begun with them, and 40 of the 48 sketches, getting about 97% of the sketched people right (445 of 459). It read every pair of twins right in the drawings, with `hand_drawn` or without, all 13 in those begun with the Studio's symbols, and 20 of 23 in the sketches. On the four earlier sets, used while making these changes, it read 51 of the 60 sketched pairs right: the bar between twins' lines is short and easily lost in a rough sketch, and lines to twins drawn close over their symbols may be cut short by them. An independent check, on 81 pedigrees drawn by a separate program, in the Studio's style and sketched, found much the same: it read every drawing right, with `hand_drawn` or without, all 6 pictures begun with symbols and finished by hand, and 16 of its 20 sketches, and most of the rest of what it misread had a line drawn close beside a symbol scribbled in, or a small triangle that was missed. Warnings say when a line seems to have been missed, so check the table against the sketch. Sketches read best when:

- the lines touch, or nearly touch, the symbols and the lines they join
- the symbols are kept apart from each other, and from the lines that pass by them: a line drawn close beside a symbol filled in by scribbling or hatching, such as the line down from a couple drawn close to one of them, or the line over a family's children drawn close over a child, may be taken for part of the symbol, which then loses that line
- the outlines of symbols are closed, especially where a line leaves them. A small triangle, for a pregnancy lost, is the symbol most often missed
- twins' lines meet at a clear point, with the bar of identical twins drawn right across between them, not up against the point the lines come from

When PedInterp reads a picture without `hand_drawn`, and finds no symbols or what looks like a missed line, its error or warning says to read the picture with `hand_drawn=True` if it was drawn by hand.

## Deaths, probands and carriers

By default PedInterp reads a pedigree's structure and who is affected, which is what a PED file holds. `marks=True` (`--marks`) reads three of the marks drawn on the symbols too, and adds a column for each to the table, True or False:

- **Deceased**: a slash through the symbol, rising to the right. Through a symbol left empty, it's seen inside the symbol, where it must run along ink nearly all the way on both sides of the middle; only ink across the line from each point of it counts, so a row of dots, as in a symbol the Studio shades with them, or of specks in a poor scan, isn't taken for one. A symbol filled in hides the slash, so there it's read from where it runs out past the symbol at both ends, as a slash drawn by hand usually does, and as Pedigree Studio draws one through a circle or a diamond. The Studio draws the slash through a filled square from corner to corner, inside it, where it can't be seen, so that one isn't read.
- **Proband**: an arrow pointing at the symbol from below on the left, with a head at the end by the symbol, as the Studio draws it. Drawn by hand, it may touch the symbol, or run into other lines further on, but it reads best drawn clear of them.
- **Carrier**: a dot in the middle of the symbol, thicker than the lines: dark in a symbol left empty, and white in one filled in solidly, as the Studio draws it. A dot can't be seen in a symbol scribbled in.

Other marks aren't read: the upright line of a presymptomatic carrier, letters and numbers written in a symbol (P for a pregnancy, D for a donor, S for a surrogate), which aren't taken for a dot, the brackets round someone adopted, and text written beside a symbol, such as an age or a cause of death.

A PED file can't hold the marks, so `PED_export` refuses a table that has them, and so does `export=True`; `pedinterp --marks` writes no PED file, and needs `--studio`, `--ga4gh` or both. `GA4GH_export` writes them as studio2ga4gh writes the Studio's marks, but gives the affected a vital status only where a slash was seen, and `Studio_export` draws them as the Studio does. Without `marks=True`, nothing about the reading changes: the table, and everything else PedInterp gives back, is as it was before the option was added.

The marks were tested on 192 pedigrees drawn with Pedigree Studio and its Draw tool, as for the sketches above, and kept apart from those used in making the option: a quarter drawn with the Studio's symbols, a quarter begun with them and finished by hand, and half sketched throughout, with a fifth of the people marked as having died, a proband in most families, and about one unaffected person in seven a carrier. Half were drawn with the Draw tool's black pen, 4 pixels wide, and the rest in other colours and widths; in half of the pedigrees, the Studio wrote a name and an age under most of its symbols, where it writes them. Each was read with `hand_drawn=True` if any of it was drawn by hand:

- **the Studio's own marks** were all read where they can be seen: 121 of the 140 deaths, the other 19 being slashes through filled squares, which can't be seen; all 54 probands; and all 92 carriers
- **marks drawn by hand**: 226 of 253 deaths (most of those missed were slashes through symbols scribbled in, which barely ran out past them), 127 of 130 carriers, and 66 of 102 probands. The arrows were drawn wherever they fell, and in the sketches, those drawn clear of the other lines were found 44 times in 53, but those that crossed or touched another line, or met the end of a slash, only 8 times in 30
- **no mark was read where none was drawn**: no death among the 1,514 people without a slash, no proband among the 1,751 without an arrow, and no carrier among the 1,685 without a dot; none on the same 192 pedigrees drawn without any marks; and none on the 384 pictures of the earlier tests
- **the rest was read as well with the marks as without**: 1,875 of the 1,969 people right, and 1,853 on the same pedigrees drawn without the marks

A death, an arrow or a dot is only read on a symbol that PedInterp finds, so check the table against the picture, as for any reading. The marks read best when the slash runs out past the symbol at both ends, the arrow is drawn clear of the lines, and the dot is a good deal thicker than the lines. The picture of the Okafor family that Pedigree Studio saves, in the lab's [pedigree workbench](https://github.com/comparativechrono/pedigree-workbench), reads with its five deaths and its proband, among the names, ages and causes of death written under its symbols, with `hand_drawn` or without.

## Without Tesseract, and in a browser

PedInterp doesn't need Tesseract, or pytesseract, to read a drawing. It imports without them, and it can number the people rather than read their labels. That lets it run in a browser under [Pyodide](https://pyodide.org), which provides OpenCV, numpy, pandas and Pillow but can't run the tesseract program.

### The `ocr` argument

- `'tesseract'`, the default, reads the labels with Tesseract. If pytesseract isn't installed, or the tesseract program can't be found or run (as under Pyodide), a warning says why, and the people are numbered instead
- `None` or `'none'` leaves the labels unread and numbers the people. This is also the better choice for a drawing without labels: with no real labels to measure it against, a symbol that Tesseract takes for a letter (a circle for an O) passes for a label, and is blanked out
- a function reads the labels with other OCR, such as tesseract.js in a browser: see [Reading the labels with other OCR](#reading-the-labels-with-other-ocr)

### Numbering

People are numbered in the usual way for pedigrees. Each row of symbols, from the top, is a generation, numbered in Roman numerals, and the people in a row are numbered from the left: the two people at the top of a drawing are I-1 and I-2, and those in the row below are II-1, II-2 and so on. Parents are given by the same IDs. A new row starts where the middle of a symbol is more than half a symbol's height below the one above it and more than a symbol's height below the first of its row, so a symbol drawn a little out of line keeps its place in its row, and so does a row that slopes. This is how Pedigree Studio numbers its people, as it takes everyone up to a symbol and a half below the top of a row as in it.

When the labels aren't read they are still in the drawing, so PedInterp keeps them from being taken for symbols or lines:

- the holes in letters and numbers (in 0, 6, 8, 9, A, B, D and so on) are white space inside an outline, like the inside of an unfilled symbol, but much smaller. Each shape is measured with its outline: an unfilled symbol is found by the white inside it, so the width of its outline is added on either side (for a hole in a letter, the width of the letter's stroke). Nothing less than half the size of a typical symbol is then taken for a symbol, and nor is anything less than three line widths across. The typical symbol is the median filled one, as text is never taken for a filled symbol, or, if none is filled, a size that nine in ten of the shapes found are smaller than. Line widths alone wouldn't do, as the lines of a drawing can be much thinner than the strokes of its text
- once the symbols have been found, every dark mark that couldn't be a line to a symbol is cleared away before the lines are looked for: whatever doesn't come within reach of the top or the sides of a symbol, where lines meet it. The reach is as far as the lines are traced from a symbol, so a line that stops a little short of a symbol stays, while labels under the symbols and stray marks go. If no lines are left between the symbols, a warning says so
- shapes that overlap are taken as one symbol, so the two pieces of a symbol cut by a slash count once, and a small shape inside a larger one of the other kind, such as a carrier's dot, is left out
- labels written just above the symbols, as Pedigree Studio writes its numbers, are taken out of the lines before they are read: a word is two or more small marks side by side, as tall as letters and no taller, and a line, even a short one down to a child, is a single stroke. A label written close under a line, as over someone who married into the family when the line over their partner's brothers and sisters passes above them, touches the line or crosses it, and would otherwise be read as a line down to them. Where the label is lighter than the line, as the Studio's grey numbers are, it is cut away from the line by how dark each is, and the line is kept whole where the label crosses it

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
for (const file of ["__init__.py", "core.py", "lines.py", "marks.py", "shapes.py", "studio.py"]) {
  pyodide.FS.writeFile(`/home/pyodide/PedInterp/${file}`, await (await fetch(`PedInterp/${file}`)).text());
}
pyodide.FS.writeFile("/home/pyodide/FAM1.png", new Uint8Array(await imageFile.arrayBuffer()));
const ped = pyodide.runPython(`
from PedInterp import pedigree_processing
pedigree_processing('FAM1', image_path='FAM1.png', ocr=None).to_csv(sep='\\t', header=False, index=False)
`);
```

`GA4GH_export` also needs pedigree-ga4gh, which is plain Python too: copy its folder in the same way, or install it with micropip. It is imported only when the function is called, so reading a drawing doesn't need it.

Reading a drawing takes a few seconds, and a good deal of memory for a large one, as the image is enlarged. Under Pyodide in Node, the four-generation test drawing, 1200 by 740 pixels, took between 4 and 6 seconds to read, a family with twins as Pedigree Studio draws it 1 to 2 seconds, and a sketch about 3 seconds, and Pyodide's memory grew to between 500 and 550 MB over the whole check. The factor PedInterp chooses keeps the image no larger than its symbols need, and never above 60 million pixels, but it's still worth running Pyodide in a web worker, so that the page doesn't freeze while it works.

### What a missed line looks like

The lines between the symbols can be missed: most often when the picture is enlarged too little, or far too much, and with lines much bolder than the symbols' outlines. PedInterp warns (`missed_lines`) when what it read looks like a missed line:

- someone has only one parent;
- someone below the top row has no parents, no children and no partners' line to them;
- the parents and children it found split the people into more than one family, as when the line up from someone who has children is missed;
- no one has parents at all, though the symbols are in more than one row.

The warning says how many times the picture was enlarged, and enlarging it a little more or less may help. If the lines are very thick, about a fifth of a symbol's width, enlarge it less: an unfilled symbol is measured by the white inside it, which such lines make much smaller than the symbol, so the picture is enlarged more than it needs. Not every misreading looks like one of these, such as someone given the wrong parents, so check the table against the picture.

### Checking PedInterp under Pyodide

The script `tests/pyodide/check.mjs` runs PedInterp under Pyodide 0.29.5 in Node. It copies PedInterp's source into Pyodide's file system with the test pedigrees, drawn beforehand in ordinary Python. Each pedigree is read with `ocr=None`, one again with an `ocr` function given words from JavaScript, as from tesseract.js, and one with the default `ocr`, which should warn that Tesseract can't be run. A family with twins, as Pedigree Studio draws it, and a family sketched by hand, read with `hand_drawn=True`, are read too, with their twins, and written as Pedigree Studio drawings; and a family drawn as the Studio draws it and the sketch, with who has died, the proband and carriers marked on them, are read with `marks=True`. Every table is checked against the one it should be. It needs Node 18 or later, as Pyodide does:

```bash
cd tests/pyodide
npm install        # Pyodide 0.29.5
python draw.py     # draws the pedigrees, with the Python the tests run with
node check.mjs
```

The first time, Pyodide downloads the wheels it needs (numpy, pandas, opencv-python, Pillow and their dependencies) from its CDN, and keeps them in `tests/pyodide/packages`. If Node can't reach the CDN, for instance behind a proxy it doesn't use, `check.mjs` lists the files it's missing, and they can be downloaded into that folder by hand from `https://cdn.jsdelivr.net/pyodide/v0.29.5/full/`. The check isn't part of the GitHub workflow.

## Tests

The tests draw pedigrees to read, in the usual style, as Pedigree Studio draws them and as people sketch them (`tests/drawings.py`), so they need the DejaVu Sans fonts as well as pytest. The tests that read the labels with Tesseract need Tesseract too, and are skipped without it; the others, which number the people or read the labels through an `ocr` function, don't. The tests of the Studio drawings read them back with studio2ped and studio2ga4gh, which the `test` extra installs, and skip that without them.

```bash
pip install -e ".[test]"
pytest
```

## License

[MIT](https://choosealicense.com/licenses/mit/)
