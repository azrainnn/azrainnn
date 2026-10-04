#!/usr/bin/env python3
"""Turn a photo into ascii_art.txt.   Usage: python make_ascii.py photo.jpg [cols] [rows]

Tips: crop tightly to your head/shoulders first, use a plain background,
and boost contrast. 36-38 columns by ~22 rows fits the card best."""
import sys
from PIL import Image, ImageOps

RAMP = " .:-=+*#%@"   # light -> dark

def convert(path, cols=36, rows=22, invert=False):
    im = ImageOps.autocontrast(ImageOps.grayscale(Image.open(path)))
    im = im.resize((cols, rows), Image.LANCZOS)
    if invert:
        im = ImageOps.invert(im)
    px = im.load()
    return ["".join(RAMP[int((255 - px[x, y]) / 256 * len(RAMP))] for x in range(cols)).rstrip()
            for y in range(rows)]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 36
    rows = int(sys.argv[3]) if len(sys.argv) > 3 else 22
    art = convert(sys.argv[1], cols, rows)
    open("ascii_art.txt", "w").write("\n".join(art) + "\n")
    print("\n".join(art))
