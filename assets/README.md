# assets/ — brand imagery, authored once and published by the build

Everything in `assets/images/` is a source file for the site's identity. The
build copies this folder into `docs/assets/img/`, so **editing an image here and
rebuilding changes the favicon on all ~500 pages at once** — no page ever
references an image by hand.

| File | Used for | Maintained by |
|---|---|---|
| `favicon.svg` | the browser tab icon on every page (`<link rel="icon">`) | hand-edited SVG |
| `icon-192.png` | Android / PWA icon, and the PNG fallback favicon | `scripts/make_icons.py` |
| `icon-180.png` | iOS home-screen icon (`apple-touch-icon`) | `scripts/make_icons.py` |
| `icon-512.png` | store-sized master, and the Open Graph share image | `scripts/make_icons.py` |
| `logo.svg` | horizontal wordmark for READMEs and slides | hand-edited SVG |

The three PNGs are committed binaries, but they are *generated*: the brand mark
is drawn by `scripts/make_icons.py` with nothing but the standard library (a
5×7 bitmap "10" on a rounded, diagonally shaded tile, box-filtered down to each
size and written as a PNG by hand). That keeps the colours in step with
`--brand` / `--brand-dark` / `--accent` in `site/theme/css/style.css` and makes
the icons reproducible:

```bash
python3 scripts/make_icons.py            # rewrite the three PNGs
python3 scripts/make_icons.py --check    # fail if a committed PNG is stale
```

`scripts/check_all.sh` runs the `--check` form, and
`tests/test_site_structure.py` compares the committed bytes against a fresh
render, so a recoloured theme cannot leave the icons behind.

Nothing else belongs here: page-specific artwork would live with the content
that uses it, and the published copy under `docs/assets/img/` is build output —
never edit it directly.
