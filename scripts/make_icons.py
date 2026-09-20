#!/usr/bin/env python3
"""Regenerate the raster icons in assets/images/ from source, with no dependencies.

The published site uses assets/images/favicon.svg (vector, every browser that
matters) plus raster icons for the cases that still ask for a PNG: iOS home
screen (180), Android/PWA (192) and the store-sized master (512). Those PNGs
are committed because the build only copies files — it never draws them — but
they are generated, so this script is their source of truth.

    python3 scripts/make_icons.py            # rewrite the three PNGs
    python3 scripts/make_icons.py --check    # exit 1 if a committed PNG is stale

Pure standard library: the glyphs are a 5x7 bitmap drawn into a rounded,
diagonally shaded tile, then box-filtered down to each target size and written
as a PNG by hand (IHDR / IDAT / IEND with CRC32).
"""
from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IMAGES = REPO / "assets" / "images"

# Brand colours, kept in step with the --brand / --accent variables in
# site/theme/css/style.css.
TOP_LEFT = (0x1F, 0x6F, 0xEB)      # --brand
BOTTOM_RIGHT = (0x17, 0x50, 0x9F)  # --brand-dark
ACCENT = (0x0F, 0x9D, 0x76)        # --accent
WHITE = (0xFF, 0xFF, 0xFF)
CORNER = 0.2734                    # corner radius as a fraction of the tile

MASTER = 512                       # draw big, then box-filter down
TARGETS = {"icon-512.png": 512, "icon-192.png": 192, "icon-180.png": 180}

# "10" as 5x7 bitmaps, with a slashed zero so it never reads as the letter O.
GLYPHS = {
    "1": (
        "..X..",
        ".XX..",
        "..X..",
        "..X..",
        "..X..",
        "..X..",
        ".XXX.",
    ),
    "0": (
        ".XXX.",
        "X...X",
        "X..XX",
        "X.X.X",
        "XX..X",
        "X...X",
        ".XXX.",
    ),
}
TEXT = "10"
GLYPH_GAP = 1                      # blank cells between glyphs


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _inside_rounded(x, y, size):
    """True when (x, y) falls inside a rounded square of `size`."""
    r = size * CORNER
    if not (0 <= x < size and 0 <= y < size):
        return False
    cx = r if x < r else (size - r - 1 if x >= size - r else None)
    cy = r if y < r else (size - r - 1 if y >= size - r else None)
    if cx is None or cy is None:
        return True
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _text_cells():
    """The '10' as a set of (col, row) cells on a grid GLYPH_GAP apart."""
    cells, col = set(), 0
    for ch in TEXT:
        for row, line in enumerate(GLYPHS[ch]):
            for c, mark in enumerate(line):
                if mark == "X":
                    cells.add((col + c, row))
        col += len(GLYPHS[ch][0]) + GLYPH_GAP
    width = col - GLYPH_GAP
    return cells, width, len(GLYPHS[TEXT[0]])


def _master_pixels():
    """Render the MASTER x MASTER tile as a flat list of (r, g, b)."""
    size = MASTER
    cells, gw, gh = _text_cells()

    # Scale the text so it fills a predictable share of the tile, then centre it.
    cell = int(size * 34 / 512)
    tw, th = gw * cell, gh * cell
    tx, ty = (size - tw) // 2, int(size * 0.234)

    # Accent bar under the digits, same proportions as favicon.svg.
    bar_w, bar_h = int(size * 0.469), max(2, int(size * 0.0625))
    bar_x, bar_y = (size - bar_w) // 2, ty + th + int(size * 0.078)
    bar_r = bar_h / 2

    px = []
    for y in range(size):
        for x in range(size):
            if not _inside_rounded(x, y, size):
                px.append((0, 0, 0, 0))
                continue
            t = (x + y) / (2 * (size - 1))
            rgb = _lerp(TOP_LEFT, BOTTOM_RIGHT, t)
            alpha = 255
            # digit cells
            gc, gr = (x - tx) // cell, (y - ty) // cell
            if 0 <= x - tx < tw and 0 <= y - ty < th and (gc, gr) in cells:
                rgb = WHITE
            # accent bar (rounded ends)
            elif bar_y <= y < bar_y + bar_h and bar_x <= x < bar_x + bar_w:
                bx = min(x - bar_x, bar_x + bar_w - 1 - x)
                cy = bar_y + bar_r
                if bx >= bar_r or (x - (bar_x + bar_r)) ** 2 + (y - cy) ** 2 <= bar_r * bar_r:
                    rgb = ACCENT
            px.append(rgb + (alpha,))
    return px


def _resample(px, src, dst):
    """Box-filter a flat RGBA list from src x src down to dst x dst."""
    if dst == src:
        return list(px)
    out, scale = [], src / dst
    for oy in range(dst):
        y0, y1 = int(oy * scale), max(int(oy * scale) + 1, int((oy + 1) * scale))
        y1 = min(y1, src)
        for ox in range(dst):
            x0, x1 = int(ox * scale), max(int(ox * scale) + 1, int((ox + 1) * scale))
            x1 = min(x1, src)
            r = g = b = a = n = 0
            for y in range(y0, y1):
                row = y * src
                for x in range(x0, x1):
                    pr, pg, pb, pa = px[row + x]
                    # average straight (not premultiplied): the only transparent
                    # pixels are fully transparent corners
                    r += pr; g += pg; b += pb; a += pa; n += 1
            out.append((r // n, g // n, b // n, a // n))
    return out


def _png(pixels, size):
    """Encode a flat RGBA list as a PNG byte string."""
    raw = bytearray()
    for y in range(size):
        raw.append(0)                                    # filter: none
        row = y * size
        for x in range(size):
            raw.extend(pixels[row + x])
    body = bytes(raw)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(body, 9)) + chunk(b"IEND", b""))


def render_all():
    """{filename: png bytes} for every target size."""
    master = _master_pixels()
    return {name: _png(_resample(master, MASTER, size), size)
            for name, size in TARGETS.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="fail when a committed icon differs from a fresh render")
    args = ap.parse_args()

    IMAGES.mkdir(parents=True, exist_ok=True)
    stale = []
    for name, data in sorted(render_all().items()):
        path = IMAGES / name
        if args.check:
            if not path.is_file():
                stale.append(f"{name}: missing")
            elif path.read_bytes() != data:
                stale.append(f"{name}: differs from scripts/make_icons.py output")
            continue
        path.write_bytes(data)
        print(f"  wrote {path.relative_to(REPO)} ({len(data)} bytes)")

    if stale:
        for line in stale:
            print(f"STALE ICON {line}")
        print("run: python3 scripts/make_icons.py")
        sys.exit(1)
    if args.check:
        print(f"icons up to date: {', '.join(sorted(TARGETS))}")


if __name__ == "__main__":
    main()
