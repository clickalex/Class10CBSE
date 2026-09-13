# Study-hub site

A static study hub: a portal, one hub per subject (including Information
Technology 402, built in), unit overviews, and one deep page per chapter with a
marks lens, concepts, formulas, memory tricks, mistakes to avoid and exam Q&A
in four tones — Short, Long, Application and Competency — with click-to-reveal
answers.

## Build

```bash
python3 site/build.py           # writes ../docs/  (the published folder)
python3 site/build.py --check   # same, and exits non-zero if anything is broken
python3 site/build.py --out /tmp/preview
```

No dependencies beyond the Python 3 standard library.

## Preview locally

```bash
python3 -m http.server 8000 --bind 0.0.0.0 --directory docs
# then open http://localhost:8000
```

## Layout

```
site/
├── build.py                  generator
├── theme/                    style.css + app.js, copied into docs/assets
├── content/
│   ├── subjects.json         one entry per subject: units, marks, study order
│   └── chapters/<slug>/      chapter content, split into small JSON files
docs/                         generated site — GitHub Pages serves this folder
```

`docs/` is committed on purpose: the repository's Pages setting is
*Deploy from a branch → main → /docs*, so the built site has to be in the tree.
Rebuild and commit `docs/` whenever `site/content/` changes — `scripts/check_all.sh`
runs the build into a scratch directory first, so the published folder is only
ever written on purpose. `.github/workflows/` has two workflows that automate
that and the checks; see the root README for how to add them.

## Adding a chapter

Create `site/content/chapters/<slug>/<anything>.json` containing either one
chapter object or a list of them, then rebuild. A chapter object looks like:

```json
{
  "id": "ch01-real-numbers",
  "num": 1,
  "title": "Real Numbers",
  "unit": "u1",
  "unit_name": "I · Number Systems",
  "weight": "6 marks",
  "short": "One-line summary for the unit card.",
  "lede": "Sentence shown under the chapter title.",
  "lens": ["What this chapter is worth and how it is asked."],
  "concepts": ["Numbered concept paragraphs.", {"table": {"head": ["A", "B"], "rows": [["1", "2"]]}}],
  "formulas": ["Optional: rendered as a formula list."],
  "steps": ["Optional: a worked method."],
  "tricks": ["Optional: memory tricks."],
  "mistakes": ["Optional: what costs marks."],
  "qa": [{"m": "3", "q": "Question", "a": "Answer, or a list of lines."}],
  "mcq": [{"q": "Question with (a) (b) (c) (d)", "a": "Answer with reasoning."}],
  "trend": "What past papers keep asking from this chapter.",
  "onepager": ["Bullet points for the Quick revision page."],
  "task": ["A hands-on task."]
}
```

Inline markup in any string: `**bold**`, `*italic*`, `` `code` ``. Start a string
with `- ` for a bullet or `1. ` for a numbered item.

## Checks the build runs

`build.py` fails loudly rather than publishing something broken:

- chapter numbering must run 1..N with no gaps;
- every chapter's `unit` must exist in `subjects.json`;
- every chapter must have `lens` and `concepts`;
- duplicate chapter ids are rejected;
- after writing, every internal link is checked against the files on disk.

Subjects with no chapter content yet are skipped and shown on the portal as
*in progress* — the build reports them instead of failing.

## Coverage

Every Class 10 subject has a hub. Chapter content is authored for all eight
subjects — **174 chapters** in total:

| Subject | Chapters |
|---|---|
| Maths | 14 |
| Science | 13 |
| Social Science | 21 |
| English | 33 |
| Hindi | 40 |
| Computer Applications | 14 |
| Sanskrit | 19 |
| Information Technology (402) | 20 |

IT 402 is built in this site (same design as the others). It is not an
external redirect. Question banks on every subject use Short / Long /
Application / Competency cards with hidden answers.

A useful sanity check before committing, because `build.py` does not name the
file when a JSON file fails to parse:

```bash
for f in site/content/chapters/*/*.json; do python3 -c "
import json
try: json.load(open('$f', encoding='utf-8'))
except Exception as e: print('FAIL', '$f', e)
"; done
```
