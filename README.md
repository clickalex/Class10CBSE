# Class 10 CBSE — Subject-wise Study Folder

A ready-to-use folder structure for CBSE **Class 10** (India) board preparation.
One top-level folder per subject, and inside each subject the same set of
places to keep syllabus, notes, NCERT solutions, practice work and past papers.

```
Class10CBSE/
├── 00-Common/                syllabus PDFs, date sheet, marking scheme, all-subject papers
├── 01-English/               First Flight + Footprints Without Feet  (code 184)
├── 02-Hindi/                 Course A (002) and Course B (085)
├── 03-Mathematics/           Standard 041 / Basic 241
├── 04-Science/               code 086
├── 05-Social-Science/        History · Geography · Political Science · Economics (087)
├── 06-Information-Technology/  skill subject, code 402   ┐
├── 07-Computer-Applications/   elective, code 165        ├ keep only the ones you study
├── 08-Sanskrit/                language II, code 122     ┘
├── 09-After-10th/            Class XI admissions, official links, 9 PM IST tracker
├── 10-PW-NSAT/               PW scholarship test: syllabus, practice, registration
├── assets/                   brand imagery: favicon.svg, logo.svg, generated icon-*.png
├── scripts/                  build_structure.sh · verify_structure.sh · check_all.sh · make_icons.py
├── site/                     the site's source: content/, partials/, theme/, generators
├── tests/                    offline unit tests (run all via scripts/check_all.sh)
├── project-info/             notes about the repo itself (whole-repo audit)
└── docs/                     the generated study hub — this is what GitHub Pages serves
```

Two folders hold the same site on purpose and must never be confused:
**`site/` is the source** (content JSON, HTML partials, CSS/JS, generators) and
**`docs/` is the build output** that GitHub Pages publishes. Never edit `docs/`
by hand — `scripts/check_all.sh` diffs a fresh build against the committed
`docs/` and fails if they differ, so a stale or hand-edited publish folder
cannot be committed by accident.

**Live site: <https://clickalex.github.io/Class10CBSE/>** — built from
`site/content/`, one hub per subject (including IT 402, in-built), 175 chapter
pages, **2,133 written Q&A and 1,426 MCQs**. Every subject uses the same design
and the same Q&A tone: Short, Long, Application and Competency, with
click-to-reveal answers.

The site uses one persistent left sidebar on every page — brand and
*Chapters done* progress, all subjects with their board codes, the current
subject's pages, and every chapter grouped by unit with the page you are on
highlighted; it collapses to a `☰` drawer on small screens. Each subject also
has a chapter index page (`/chapters.html`) and every chapter has a
Previous / All chapters / Next strip. The credit line **"Created by Mohammad
Umair"** appears in the sidebar foot and page footer of every page.

Every chapter page now carries the same sections — a marks lens, deep
concepts, a step-by-step method, memory tricks, mistakes that cost marks,
exam Q&A with click-to-reveal answers ordered by marks, and a hands-on task —
plus a formula list in the subjects that have formulas. See
[What every chapter contains](site/README.md#what-every-chapter-contains).

See [Deploying the site](#deploying-the-site) below.

## Mock tests — check your own score online

The [mock test centre](https://clickalex.github.io/Class10CBSE/mock-test/)
has a timed MCQ mock test for **every exam listed in this repository**: the nine
board subjects (Maths, Science, Social Science, English, Hindi A, Hindi B, IT
402, Computer Applications, Sanskrit) and the eleven test-based entrance and
scholarship exams in the after-10th directory (JNV Class XI, JMI, AMU, BHU/CHS
SET, UP and Bihar polytechnic, PW NSAT, TALLENTEX, ANTHE, iACST, VMC VIQ) —
20 exams × 10 mocks each, plus 187 chapter-wise mocks. Routes that select on
merit or document verification (KV, RKM Narendrapur, Chandigarh XI, Haryana
polytechnic) are listed on the same page with a note instead of a test.

- **A live question generator** — every mock is generated in the browser when
  you click it: each section draws its questions at random from the exam's
  pool (1,197 MCQs across the banks) and avoids the questions you were already
  served on that device, so **every attempt is a different paper** until the
  pool cycles. Ten numbered mocks per exam, and a chapter-wise mock for every
  chapter that has MCQs (from that chapter's practice page or the exam page).
- **Online screen** — timer, question palette, mark-for-review, keyboard
  shortcuts, auto-submit at zero; the generated paper and your answers survive
  an accidental reload. A *New questions* button reshuffles before you start.
- **Instant score and one-page report** — marks, percentage, accuracy,
  negative-marking loss, section-wise table, the topics to revise first (linked
  to the chapter and its practice page) and a question map. *Download report*
  prints it as a single A4 page / PDF; there is also a `.txt` download. Full
  answer review with explanations follows.
- **Downloads** — the same generated paper opens as a printable paper with an
  OMR grid and an optional answer-key page (print → *Save as PDF*), plus
  plain-text paper and key files generated on the fly.
- Scores are stored only in the browser (localStorage) — nothing is uploaded.

`site/mocktest.py` embeds each exam's question pool and blueprint (from
`site/content/mock-tests.json`) into one engine page per exam
(`mock-test/<exam>/test.html`); `site/theme/js/mock.js` generates the paper, runs
the test, scores it and builds the downloads in the browser. Questions come
from the chapter question banks plus an original Mental Ability bank
(`site/content/banks/`). Board mocks are objective practice across the whole
syllabus; entrance patterns are approximations of the published pattern and
say so on every page — these are not official papers.

## After Class 10 admissions

The new [after-10th folder](09-After-10th/README.md) and
[website hub](https://clickalex.github.io/Class10CBSE/after-10th/) cover 15 options across Class XI schools, diploma colleges and scholarship
exams: JMI, AMU, BHU/CHS, JNV, KV, RKM Narendrapur, Chandigarh schools,
Haryana/UP/Bihar polytechnics, PW NSAT, TALLENTEX, ANTHE, iACST and VMC VIQ. The hub appears alongside the
subjects on the home page and in every page's sidebar.

A GitHub Actions checker is configured for **9 PM IST daily**. It flags changed
school, diploma and scholarship notices, includes date evidence, and updates a report issue.
It then publishes the results to the website's
[daily watch report](https://clickalex.github.io/Class10CBSE/after-10th/report.html),
which shows when the check ran and when each official source was last fetched.
It does not guess whether registration is open or reuse old deadlines.
The workflow is configured in [`.github/workflows/admission-watch.yml`](.github/workflows/admission-watch.yml)
(reviewed copy: [`.github/staged-workflows/admission-watch.yml`](.github/staged-workflows/admission-watch.yml)).
Set **Settings → Pages → Source** to **GitHub Actions**, enable Actions/Issues and run it once.
See [setup and limitations](09-After-10th/02-Admission-Tracker/README.md).

## PW NSAT scholarship test

The [PW NSAT folder](10-PW-NSAT/README.md) and
[website hub](https://clickalex.github.io/Class10CBSE/pw-nsat/) link to the
[official PW NSAT website](https://www.pw.live/scholarship/vidyapeeth/nsat).
Find it on the home page and in the sidebar, alongside the study hubs.
It contains a dated official-page summary, Class 10 syllabus guidance,
practice planning and a registration checklist. This coaching scholarship test
is labelled separately from school entrance tests and is now also included
in the directory’s daily checker.

## Inside every subject

| Folder | What goes in it |
|---|---|
| `01-Syllabus/` | The official CBSE syllabus PDF + your own "what is deleted" list |
| `02-NCERT-Textbook/` | NCERT textbook PDFs / chapter scans |
| `03-Notes/` | Your notes, one sub-folder per chapter (or per unit for skill subjects) |
| `04-NCERT-Solutions/` | Solved NCERT exercise questions, same chapter split |
| `05-Important-Questions/` | Chapter-wise / unit-wise high-weightage question banks |
| `06-Practice-Worksheets/` | Worksheets, MCQs, case-study and source-based questions |
| `07-Previous-Year-Questions/` | Past board papers, split by chapter or by year |
| `08-Sample-Papers/` | CBSE sample papers + your own timed attempts |
| `09-Revision-Sheets/` | Formula sheets, one-pagers, mind maps, last-day revision |
| `10-Practical-File/` | *(Science, IT, Computer Applications only)* lab records, diagrams |
| `10-Map-Work/` | *(Social Science only)* map pointing items for History + Geography |

Numbering keeps the folders in study order — syllabus first, revision last.

## Subject snapshot

| Subject | Code | Theory | Internal | Notes |
|---|---|---|---|---|
| English Language & Literature | 184 | 80 | 20 | First Flight, Footprints Without Feet, Words and Expressions II |
| Hindi Course A | 002 | 80 | 20 | क्षितिज भाग-2, कृतिका भाग-2 |
| Hindi Course B | 085 | 80 | 20 | स्पर्श भाग-2, संचयन भाग-2 |
| Mathematics (Standard / Basic) | 041 / 241 | 80 | 20 | Same syllabus, different difficulty |
| Science | 086 | 80 | 20 | 13 NCERT chapters |
| Social Science | 087 | 80 | 20 | 20 marks each: History, Geography, Political Science, Economics |
| Information Technology | 402 | 50 | 50 | Skill subject (LibreOffice Writer/Calc/Base) |
| Computer Applications | 165 | 50 | 50 | Elective |
| Sanskrit | 122 | 80 | 20 | शेमुषी भाग-2, अभ्यासवान् भव |

Each subject folder has its own `README.md` with the chapter list and unit-wise
marks for that subject — read those before you start filling folders.

## Naming conventions used

- `NN-Name` — two-digit prefix so folders sort in the order you use them.
- `chNN-Name` — chapter folders, numbered exactly as in the NCERT textbook, so
  `03-Mathematics/03-Notes/ch04-Quadratic-Equations/` is Chapter 4 of the book.
- `unitN-Name` — unit folders for the skill/elective subjects, which are
  organised by unit rather than chapter.
- Folder names are plain ASCII, hyphen-separated. Hindi and Sanskrit chapter
  folders use romanised titles (e.g. `ch01-Sur-ke-Pad` for सूर के पद); the
  Devanagari titles are in that subject's README.

## Rebuilding or extending the tree

The folder list lives in one place: `scripts/structure.conf` (one directory per
line, `#` for comments).

```bash
scripts/build_structure.sh              # create everything in the manifest
scripts/build_structure.sh --dry-run    # show what would be created
scripts/verify_structure.sh             # check the tree is complete (exit 1 if not)
scripts/check_all.sh                    # tree + content + site, all checks at once
```

`build_structure.sh` is safe to re-run — it never deletes or overwrites, and it
drops a `.gitkeep` into empty folders so Git keeps them. To add a chapter or a
subject, add its line to `scripts/structure.conf` and re-run the build.

## Deploying the site

`site/` turns `site/content/` into a static study hub; `docs/` is the built
output and the folder GitHub Pages publishes. Nothing else is needed — no
dependencies, no build service, no branch switching.

```bash
python3 site/build.py           # rebuild docs/ from site/content/ and check the links
python3 site/build.py --check   # same thing (the flag is kept for compatibility)
python3 site/build.py --out /tmp/preview
scripts/check_all.sh            # every check in the repo, site built to a scratch dir
```

- **Published at** <https://clickalex.github.io/Class10CBSE/> by GitHub
  Actions (**Settings → Pages → Source: GitHub Actions**): `deploy-pages.yml`
  on pushes to `main`, and `admission-watch.yml` after every daily check.
- `docs/` is the committed, reviewable build. What gets published is a fresh
  build of the same sources, byte-identical to `docs/` (the drift check
  enforces it) except that `after-10th/report.html` also carries the latest
  daily watch results (`site/build.py --admission-state`).
- To publish a change: edit `site/content/`, run `python3 site/build.py`, commit
  `site/content/` and `docs/` together, and push to `main`. The deploy workflow
  then publishes it.
- `docs/.nojekyll` tells Pages to serve the folder as-is instead of running
  Jekyll over it; `docs/404.html` is the not-found page for the live site.
- The published folder is organised by type, like any static site:
  `docs/assets/css/` (stylesheet), `docs/assets/js/` (drawer + mock engine),
  `docs/assets/img/` (favicon and icons copied from `assets/images/`), plus
  `sitemap.xml` and `robots.txt`, which the build writes from the page list so
  search engines can crawl all ~500 pages. Every page also carries its
  canonical URL, Open Graph tags and the favicon from one shared partial.
- `scripts/check_all.sh` runs six gates: folder tree, content JSON, build +
  link check, **docs/ drift** (committed output equals a fresh build), icon
  reproducibility and the offline unit tests.
- `.github/staged-workflows/` holds the reviewed copies of the automations
  that keep the above from depending on anyone's memory — `checks.yml` (all six
  gates on every push and pull request), `deploy-pages.yml` (rebuild and
  commit `docs/` on `main`, then deploy the site to Pages) and
  `admission-watch.yml` (the daily check, which also deploys the site with its
  results). They deploy with `actions/deploy-pages` because a commit made with
  the default `GITHUB_TOKEN` does not start a *Deploy from a branch* Pages
  build. Files under `.github/workflows/` need a credential with
  workflow-write permission to update, so edits land in the staged copies
  first; copy one into `.github/workflows/` and push it from an account that
  has it. See `.github/staged-workflows/README.md`.

The Pages source must be **GitHub Actions** for the daily watch results to
reach the live report page reliably. With *Deploy from a branch*, `main` →
`/docs` still serves the site, but every push republishes the report page
without check results.

## Note on Git

`.gitignore` excludes `*.pdf`, videos, archives and other large binaries. The
intention is that **the structure** is version-controlled while your study
material stays on your machine. If you do want to commit PDFs, delete the
`*.pdf` lines from `.gitignore`.

The one exception is `docs/`, the generated site: it is tracked on purpose,
because that folder is what the live site is served from. It is build output,
so edit `site/content/` and rebuild rather than editing it by hand.

## Sources

- CBSE Academic — curriculum, sample papers, marking schemes: <https://cbseacademic.nic.in/>
- **Curriculum 2026–27, Secondary (Class X)** — every subject's syllabus PDF for
  this session: <https://cbseacademic.nic.in/curriculum_2027.html>
  - Mathematics, codes 041 & 241: <https://cbseacademic.nic.in/web_material/CurriculumMain27/SecPart1/Maths_SecP1X_2026-27.pdf>
  - Information Technology, code 402: <https://cbseacademic.nic.in/web_material/Curriculum27/sec/402-IT-X.pdf>
- NCERT textbooks: <https://ncert.nic.in/textbook.php>

Session **2026–27**, chapter lists and marks tables checked against those PDFs on
**12 Sep 2026**: the seven-unit Mathematics split (6 + 20 + 6 + 15 + 12 + 10 + 11)
and the IT 402 unit and practical split (10 + 40 + 50) are unchanged from
2025–26. CBSE still publishes mid-session changes and the date sheet separately,
so re-open the curriculum page before you rely on any list.
