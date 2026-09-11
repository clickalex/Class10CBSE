# 07 · Computer Applications — Elective (Code 165)

**Only if Computer Applications is your elective.** If not, delete this folder.

- **Total:** 100 marks, split 50 theory + 50 practical, usually as two 2-hour papers

## Why there are no unit folders here yet

Unlike the other subjects, this folder has **no chapter or unit sub-folders
created yet** — on purpose. CBSE has revised the Computer Applications
curriculum more than once, and I did not want to bake in a unit list I could not
confirm from an official source.

Do this once, then the folder is as useful as the others:

1. Download the current session's Class X Computer Applications (165) curriculum
   from CBSE Academic → <https://cbseacademic.nic.in/> (Curriculum → Secondary).
2. Add one line per unit to `scripts/structure.conf`, for example:
   ```
   07-Computer-Applications/03-Notes/unit1-Name-Of-Unit
   ```
3. Run `scripts/build_structure.sh`.

The generic scaffolding below is already in place and does not depend on the
unit list:

| Folder | Purpose |
|---|---|
| `01-Syllabus/` | The official curriculum PDF |
| `02-NCERT-Textbook/` | Textbook / lab manual |
| `03-Notes/` | Your notes — add unit sub-folders as above |
| `04-Practical-File/` | Practical records and the portfolio for the lab exam |
| `05-Important-Questions/` | High-weightage questions |
| `06-Practice-Worksheets/` | Worksheets and MCQs |
| `07-Previous-Year-Questions/` | Past papers |
| `08-Sample-Papers/` | CBSE sample papers + your attempts |
| `09-Revision-Sheets/` | Syntax sheets, one-pagers |

Half the marks are practical, so `04-Practical-File/` is the folder to keep
current rather than filling up at the end of the year.
