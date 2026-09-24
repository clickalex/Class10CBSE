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
python3 site/build.py           # writes ../docs/  (the committed build)
python3 site/build.py --check   # same, and exits non-zero if anything is broken
python3 site/build.py --out /tmp/preview
# what the publishing workflows run: the same site plus the latest daily
# admission-watch results on after-10th/report.html (never used for docs/)
python3 site/build.py --out _site --admission-state .admission-monitor/state.json
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
├── build.py                  generator: reads content/, writes docs/
├── layout.py                 the page shell + reusable components; renders partials/
├── mocktest.py               builds the mock-test pools and pages (called by build.py)
├── admissions.py, nsat.py    the after-10th and PW NSAT hub pages
├── partials/                 the shared HTML, one file per component
│   ├── page.html             document shell: doctype, <html>, sidebar/main grid
│   ├── head.html             charset, title, description, favicon, canonical, OG
│   ├── header.html           skip link, ☰ drawer button, backdrop
│   ├── navigation.html       sidebar skeleton: brand, progress bar, groups, foot
│   ├── footer.html           footer skeleton + back-to-top button
│   ├── buttons.html          the button / chip / callout / chapter-nav components
│   └── notfound.html         the self-contained 404 page
├── theme/
│   ├── css/style.css         the whole design, one stylesheet
│   └── js/app.js, mock.js    drawer + progress bar; the mock-test engine
├── content/
│   ├── subjects.json         one entry per subject: units, marks, study order
│   ├── chapters/<slug>/      chapter content, split into small JSON files
│   ├── mock-tests.json       one blueprint per exam: mocks, time, marking, sections → pools
│   └── banks/                extra MCQ banks used only by mock tests (mental-ability.json)
docs/                         generated site — GitHub Pages serves this folder
assets/images/  (repo root)   favicon.svg, logo.svg + generated icon-*.png → docs/assets/img/
```

### Reusable components (partials)

Everything repeated on all ~500 pages is markup in `site/partials/`, not Python
strings: `layout.py` reads a partial, fills its `{{TOKEN}}` placeholders with
data and assembles the page. A partial that asks for a token the caller forgot
fails the build, and the explanatory comment at the top of each partial is
stripped from the published HTML. Buttons, chips, callouts and the
previous/next chapter strip come from `partials/buttons.html` through
`layout.button()`, `layout.chip()`, `layout.callout()` and
`layout.component("chapter-nav", …)`, so their markup exists exactly once and
stays in step with `theme/css/style.css`.

`docs/` is committed on purpose: it is the reviewable build of the site, and
the publishing workflows (Pages source: *GitHub Actions*) deploy a fresh build
that must equal it. Rebuild and commit `docs/` whenever `site/content/` changes — `scripts/check_all.sh`
runs the build into a scratch directory first and then diffs it against the
committed `docs/`, so a stale or hand-edited published folder fails the check.
A plain build never reads live data; only `--admission-state` adds the daily
watch results, and the workflows pass it when they publish.
`.github/staged-workflows/` holds the reviewed copies of the workflows that
automate checks, rebuilds and publishing; see the root README for how to install them.

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

`mocktest.py` builds `mock-test/` — a centre page, one page per exam and one
**engine page** per exam that generates every paper live in the browser:

| File | What it is |
|---|---|
| `mock-test/index.html` | the centre: every exam, best scores, recent attempts |
| `mock-test/<exam>/index.html` | pattern card, the 10 mock cards, chapter mocks, attempts |
| `mock-test/<exam>/test.html?n=K` | the engine page for mock K: generates a fresh paper, runs the timed test, scores it, prints the one-page report, renders the printable paper and builds the `.txt` downloads |
| `mock-test/<exam>/test.html?chapter=<id>` | a chapter-wise mock: every MCQ of that chapter, +1 / no negative, about a minute per question |

Blueprints live in `content/mock-tests.json`. Each exam has `tests` (10),
`questions`, `minutes`, `marks_correct`, `marks_wrong`, a `pattern_note` and a
list of `sections`; a section has a `count` and one or more `pools`, each either
`{"subject": slug, "units": [...]}` (chapter banks) or `{"bank": name}` (a file
in `content/banks/`). Board exams carry `subject`; entrance exams carry
`admission_id`, which must match an id in `admissions.json`. Routes without a
written test go in `no_test` with a one-line reason, and the tests insist that
every institution in `admissions.json` is in one list or the other.

The engine page embeds the exam's whole pool (the union of its section pools)
as JSON plus the chapter list. `theme/js/mock.js` generates a paper on every
attempt: each section shuffles its pool preferring questions the device has
never been served (tracked in localStorage per exam), then questions from
older batches, and only then the immediately previous batch — so two attempts
never show the same paper while the pool allows it, and cycle back evenly when
it does not. The templated study-habit MCQs in the chapter banks are excluded
from pools; a question is never used twice in one paper (also enforced across
sections). If a section pool cannot cover its count the build fails with the
exam and section named.

The same script runs the test entirely in the browser — timer, palette,
resume of the *same generated paper* after reload (sessionStorage),
auto-submit, scoring with negative marks, the report, review, the printable
paper with OMR grid and key toggle, and the paper / key / report `.txt`
downloads (Blob). Attempt history is kept in localStorage under `c10cbse-mock-*`
keys; nothing is sent anywhere. The generator and scoring helpers are exported
for Node, and the test-suite runs them when `node` is available.

## After-Class-10 hub

`admissions.py` renders `content/admissions.json` at `after-10th/index.html`
using the same sidebar and theme. The portal and every page link to it.
Rebuild `docs/` after editing either file. Network checks are separate from
the deterministic build: `scripts/check_admissions.py` and the admission-watch
workflow in `.github/workflows/admission-watch.yml` publish a daily GitHub issue
report and, through `build.py --admission-state`, the `after-10th/report.html`
page linked from the hub (check time, per-source last fetch, notices). See
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
