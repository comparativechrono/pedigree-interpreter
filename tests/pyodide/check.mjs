// Checks that PedInterp works under Pyodide, as it would in a browser. Pyodide runs in Node, and PedInterp's source
// is copied into Pyodide's file system with the pedigrees that draw.py drew. Each pedigree is read without OCR
// (ocr=None), numbering the people; one is read again with an OCR function given words from JavaScript, as
// tesseract.js's would be in a browser; and one with the default ocr, which should warn that Tesseract can't be run.
// A family with twins, as Pedigree Studio draws it, and one sketched by hand (read with hand_drawn=True) are read too,
// with their twins. Every table is compared with the one it should be. Run it from this folder:
//
//   npm install          # Pyodide 0.29.5, as in package.json
//   python draw.py       # with the Python the tests run with
//   node check.mjs
//
// Pyodide's packages are wheels, which it looks for in the folder packages, next to this file: any that aren't
// there it downloads from its CDN, and keeps there for next time.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadPyodide, version } from "pyodide";

const here = dirname(fileURLToPath(import.meta.url));
const source = join(here, "..", "..", "src", "PedInterp");
const work = join(here, "work");
const packages = join(here, "packages");

if (!existsSync(join(work, "expected.json"))) {
  console.error("There are no pedigrees to read: draw them first, with python draw.py");
  process.exit(2);
}
const expected = JSON.parse(readFileSync(join(work, "expected.json"), "utf8"));

// the packages PedInterp needs, and the packages they need, from Pyodide's list of its packages
const lock = JSON.parse(readFileSync(createRequire(import.meta.url).resolve("pyodide/pyodide-lock.json"), "utf8"));
const needed = new Set();
const need = (name) => {
  if (!needed.has(name)) {
    needed.add(name);
    lock.packages[name].depends.forEach(need);
  }
};
["numpy", "pandas", "opencv-python", "pillow"].forEach(need);
const missing = [...needed].map((name) => lock.packages[name].file_name).filter((file) => !existsSync(join(packages, file)));
if (missing.length) {
  // Node's fetch doesn't always go through a proxy, so these may have to be downloaded by hand
  console.log(`Pyodide will download these from https://cdn.jsdelivr.net/pyodide/v${version}/full/ into ${packages}:\n  ` +
              missing.join("\n  "));
}

const pyodide = await loadPyodide({ packageCacheDir: packages });
await pyodide.loadPackage([...needed]);

// Pyodide starts in /home/pyodide, which is on Python's path
pyodide.FS.mkdirTree("/home/pyodide/PedInterp");
for (const file of readdirSync(source).filter((file) => file.endsWith(".py"))) {
  pyodide.FS.writeFile(`/home/pyodide/PedInterp/${file}`, readFileSync(join(source, file)));
}
pyodide.FS.mkdirTree("/home/pyodide/work");
for (const file of readdirSync(work)) {
  pyodide.FS.writeFile(`/home/pyodide/work/${file}`, readFileSync(join(work, file)));
}
pyodide.globals.set("expected", pyodide.toPy(expected));
// the words for the OCR function come from JavaScript, as tesseract.js's would in a browser
pyodide.globals.set("words_from_javascript", pyodide.toPy(expected.read.three_generations.words));

const failures = await pyodide.runPythonAsync(`
import sys, time, warnings
import cv2, numpy, pandas, PIL
from PIL import Image
from PedInterp import pedigree_processing

print(f'Python {sys.version.split()[0]} on {sys.platform}, with OpenCV {cv2.__version__}, numpy {numpy.__version__}, '
      f'pandas {pandas.__version__} and Pillow {PIL.__version__}')
columns = ['IndividualID', 'PaternalID', 'MaternalID', 'Sex', 'Phenotype']
failures = 0

def check(name, description, want, warned=None, twins=None, **options):
    global failures
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        start = time.perf_counter()
        df = pedigree_processing(name, image_path=f'/home/pyodide/work/{name}.png', **options)
        seconds = time.perf_counter() - start
    rows = [[str(value) for value in row] for row in df[columns].values.tolist()]
    messages = [str(warning.message) for warning in caught]
    right = rows == want and (messages == [] if warned is None else len(messages) == 1 and warned in messages[0])
    right = right and (twins is None or df.attrs['twins'] == twins)
    failures += not right
    print(f'{name}, {description}: {"as expected" if right else "NOT AS EXPECTED"}, in {seconds:.1f} s')
    if not right or warned:
        print(df.to_string(index=False))
        print('warnings:', messages)
        if not right:
            print('expected:', want)

for name, want in expected['numbered'].items():
    check(name, 'numbered', want, ocr=None)

# the words' boxes are in the drawing's pixels, and are scaled to the enlarged image the function is given
width = Image.open('/home/pyodide/work/three_generations.png').width
def read_words(image):
    scale = image.shape[1] / width
    return [(text, left * scale, top * scale, w * scale, h * scale) for text, left, top, w, h in words_from_javascript]
check('three_generations', 'with labels from an OCR function', expected['read']['three_generations']['rows'], ocr=read_words)

check('two_generations', 'with the default ocr', expected['numbered']['two_generations'],
      warned="can't be read with Tesseract")

for name, case in expected['more'].items():
    check(name, 'hand-drawn, with twins' if case['hand_drawn'] else 'with twins', case['rows'], twins=case['twins'],
          ocr=None, hand_drawn=case['hand_drawn'])
failures
`);

const memory = pyodide._module?.HEAP8?.length;
if (memory) {
  console.log(`Pyodide's memory grew to ${Math.round(memory / 2 ** 20)} MB`);
}
console.log(failures ? `${failures} check(s) failed` : "Every check passed");
process.exitCode = failures ? 1 : 0;
