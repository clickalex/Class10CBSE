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
├── scripts/                  build_structure.sh · verify_structure.sh · check_all.sh · structure.conf
├── site/                     content/ + build.py that generate the study hub
└── docs/                     the generated study hub — this is what GitHub Pages serves
```

**Live site: <https://clickalex.github.io/Class10CBSE/>** — built from
`site/content/`, one hub per subject (including IT 402, in-built), 174 chapter
pages, **2,122 written Q&A and 1,394 MCQs**. Every subject uses the same design
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

- **Published at** <https://clickalex.github.io/Class10CBSE/> from
  `main` → `/docs` (**Settings → Pages → Deploy from a branch**).
- `docs/` is committed, not generated at deploy time, so a push that changes
  only `docs/` publishes exactly what was reviewed.
- To publish a change: edit `site/content/`, run `python3 site/build.py`, commit
  `site/content/` and `docs/` together, and push to `main`. Pages then rebuilds
  from `docs/` on its own.
- `docs/.nojekyll` tells Pages to serve the folder as-is instead of running
  Jekyll over it; `docs/404.html` is the not-found page for the live site.
- `.github/workflows/` carries two optional automations that keep the above from
  depending on anyone's memory — `checks.yml` (folder tree, content JSON, build
  and link check on every push and pull request) and `deploy-pages.yml` (rebuild
  and commit `docs/` on `main`, then ask Pages for a build, because a push made
  with the default `GITHUB_TOKEN` does not start other workflows). Add them from
  an account or token allowed to manage workflow files; until they are in, run
  `scripts/check_all.sh` and rebuild `docs/` yourself.

If you ever switch Pages to **Settings → Pages → Source: GitHub Actions**, the
same `docs/` folder keeps working from the branch, so the switch is optional.

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
