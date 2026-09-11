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
└── scripts/                  build_structure.sh · verify_structure.sh · structure.conf
```

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
```

`build_structure.sh` is safe to re-run — it never deletes or overwrites, and it
drops a `.gitkeep` into empty folders so Git keeps them. To add a chapter or a
subject, add its line to `scripts/structure.conf` and re-run the build.

## Note on Git

`.gitignore` excludes `*.pdf`, videos, archives and other large binaries. The
intention is that **the structure** is version-controlled while your study
material stays on your machine. If you do want to commit PDFs, delete the
`*.pdf` lines from `.gitignore`.

## Sources

- CBSE Academic — curriculum, sample papers, marking schemes: <https://cbseacademic.nic.in/>
- CBSE Class X Mathematics curriculum (codes 041 & 241): <https://cbseacademic.nic.in/web_material/CurriculumMain26/Sec/Maths_Sec_2025-26.pdf>
- CBSE Class X Information Technology (code 402): <https://cbseacademic.nic.in/web_material/Curriculum26/sec/402-IT-X.pdf>
- NCERT textbooks: <https://ncert.nic.in/textbook.php>

CBSE revises the curriculum every session and the revised list is usually
published mid-year, so confirm each subject against the current session's
syllabus PDF before you rely on a chapter list — the per-subject READMEs note
where lists were last verified.
