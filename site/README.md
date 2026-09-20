# Study-hub site

A static study hub: a portal, one hub per subject (including Information
Technology 402, built in), a chapter index per subject, unit overviews, and one
deep page per chapter with a marks lens, concepts, formulas, memory tricks,
mistakes to avoid and exam Q&A in four tones — Short, Long, Application and
Competency — with click-to-reveal answers.

## Navigation

Every page carries the same left sidebar instead of a top bar, so the place you
are in is always visible:

- **Brand + progress** — "Class 10 CBSE", the session, and a per-subject
  *Chapters done* bar.
- **All subjects** — one entry per subject with its board code as a badge;
  subjects whose chapter content is not written yet are plain text marked
  *in progress*.
- **This subject** — only when you are inside a subject: its eight pages
  (Overview, Chapters, Syllabus, Question bank, PYQ, Revision, Drill,
  Practical).
- **Chapters** — grouped by unit, each chapter numbered; the page you are on is
  highlighted and scrolled into view automatically.
- **Foot** — "Created by Mohammad Umair" on every page, including the 404 page.

On screens 900 px and narrower the sidebar becomes an off-canvas drawer opened
with the `☰` button and closed with ×, the backdrop or Escape. Chapter and
practice pages also carry a Previous / All chapters / Next strip at the bottom.

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
├── mocktest.py               assembles and renders the mock tests (called by build.py)
├── admissions.py, nsat.py    the after-10th and PW NSAT hub pages
├── theme/                    style.css + app.js + mock.js, copied into docs/assets
├── content/
│   ├── subjects.json         one entry per subject: units, marks, study order
│   ├── chapters/<slug>/      chapter content, split into small JSON files
│   ├── mock-tests.json       one blueprint per exam: sets, time, marking, sections → pools
│   └── banks/                extra MCQ banks used only by mock tests (mental-ability.json)
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
subjects — **175 chapters** in total:

| Subject | Chapters | Q&A | MCQ |
|---|---|---|---|
| Maths | 14 | 170 | 112 |
| Science | 13 | 179 | 128 |
| Social Science | 20 | 247 | 160 |
| English | 32 | 384 | 256 |
| Hindi | 44 | 528 | 352 |
| Computer Applications | 13 | 156 | 104 |
| Sanskrit | 19 | 229 | 152 |
| Information Technology (402) | 20 | 240 | 162 |
| **Total** | **175** | **2,133** | **1,426** |

IT 402 is built in this site (same design as the others). Question banks
on every subject use Short / Long / Application / Competency cards with
hidden answers. Every chapter carries both written Q&A and MCQs, so the
practice page for a chapter always has something to attempt.

### What every chapter contains

An audit of all 174 chapters (2026-09) found gaps in the optional sections
and uneven ordering, and closed them:

| Section | Coverage |
|---|---|
| Marks lens, Deep concepts, Memory tricks, Mistakes, Exam Q&A, Hands-on task | 174 / 174 |
| Method, step by step | 174 / 174 |
| Formulas to memorise | 74 / 174 — every maths, science, IT and computer-applications chapter, the five economics chapters and the three Sanskrit grammar chapters; literature chapters do not carry one |
| Concepts per chapter | maths 5, science 6, social science 7, IT 7, computer-applications 4, english 3, hindi 5, sanskrit 5 |

Median content per chapter now runs from 7,308 characters (hindi poems and
grammar) to 18,419 (social science). Written Q&A are ordered by marks
ascending in every chapter, and MCQ options use one label style per chapter
— Devanagari (क ख ग घ) throughout hindi and sanskrit, Latin elsewhere.

A useful sanity check before committing, because `build.py` does not name the
file when a JSON file fails to parse:

```bash
for f in site/content/chapters/*/*.json; do python3 -c "
import json
try: json.load(open('$f', encoding='utf-8'))
except Exception as e: print('FAIL', '$f', e)
"; done
```

## Mock tests

`mocktest.py` builds `mock-test/` — a centre page, one page per exam and, per
set, four files:

| File | What it is |
|---|---|
| `mock-test/<exam>/set-N.html` | the online test screen: intro → timed test → one-page score report → answer review |
| `mock-test/<exam>/set-N-paper.html` | printable paper with an OMR grid and an optional answer-key page (print → *Save as PDF*) |
| `mock-test/<exam>/set-N.txt`, `set-N-key.txt` | plain-text paper and key with explanations |

Blueprints live in `content/mock-tests.json`. Each exam has `sets`,
`questions`, `minutes`, `marks_correct`, `marks_wrong`, a `pattern_note` and a
list of `sections`; a section has a `count` and one or more `pools`, each either
`{"subject": slug, "units": [...]}` (chapter banks) or `{"bank": name}` (a file
in `content/banks/`). Board exams carry `subject`; entrance exams carry
`admission_id`, which must match an id in `admissions.json`. Routes without a
written test go in `no_test` with a one-line reason, and the tests insist that
every institution in `admissions.json` is in one list or the other.

Assembly is deterministic (seeded per exam and section) so a rebuild never
silently changes a published set. Questions are drawn round-robin across the
chapters of a pool so every set covers the syllabus evenly; the templated
study-habit MCQs in the chapter banks are excluded; a question is never used
twice in one set, and blueprints are sized so that no question repeats across
the sets of an exam either (`tests/test_mocktest.py` enforces both). If a
section cannot be filled the build fails with the exam, set and section named.

The set page embeds its questions as JSON; `theme/mock.js` runs the test
entirely in the browser — timer, palette, resume after reload
(sessionStorage), auto-submit, scoring with negative marks, the report,
review, `.txt` download and print. Attempt history is kept in localStorage
under `c10cbse-mock-*` keys; nothing is sent anywhere. The scoring helpers are
exported for Node, and the test-suite runs them when `node` is available.

## After-Class-10 hub

`admissions.py` renders `content/admissions.json` at `after-10th/index.html`
using the same sidebar and theme. The portal and every page link to it.
Rebuild `docs/` after editing either file. Network checks are separate from
the deterministic build: `scripts/check_admissions.py` and the admission-watch
workflow template in `../temporary-workflows/` publish a daily GitHub issue
report linked from the hub once the workflow is installed manually. See
[tracker setup](../09-After-10th/02-Admission-Tracker/README.md).

## PW NSAT hub

`nsat.py` renders `content/pw-nsat.json` at `pw-nsat/index.html` using the same
sidebar and theme. The home page and sidebar link to it. The official-page
summary has an explicit checked-on date and is not a live status feed. Its source is also included
in the expanded admission and scholarship monitor. Update the JSON, then rebuild `docs/` when
the official exam cycle changes. The corresponding study folder is
[`10-PW-NSAT/`](../10-PW-NSAT/README.md).

The after-10th page groups entries by `category` (`school`, `diploma`,
`scholarship`) and labels `selection` (`test`, `merit`, `verify`). `cycle` notes
prevent school admission years being mistaken for coaching test years.
Per-source `monitor_terms` extends the checker beyond Class XI text.
