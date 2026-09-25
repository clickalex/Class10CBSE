# study — subject folders

One folder per subject, in the order you use them. The repository root keeps
this tree in one place so it is not mixed with the website (`site/`, `docs/`,
`assets/`, `scripts/`, `tests/`).

| Folder | What it is |
|---|---|
| [`00-Common/`](00-Common/README.md) | Syllabus PDFs, date sheet, marking scheme, papers that cover every subject |
| [`01-English/`](01-English/README.md) | Language & Literature, code 184 |
| [`02-Hindi/`](02-Hindi/README.md) | Course A (002) and Course B (085) |
| [`03-Mathematics/`](03-Mathematics/README.md) | Standard 041 / Basic 241 |
| [`04-Science/`](04-Science/README.md) | Code 086 |
| [`05-Social-Science/`](05-Social-Science/README.md) | History, Geography, Political Science, Economics (087) |
| [`06-Information-Technology/`](06-Information-Technology/README.md) | Skill subject, code 402 |
| [`07-Computer-Applications/`](07-Computer-Applications/README.md) | Elective, code 165 |
| [`08-Sanskrit/`](08-Sanskrit/README.md) | Language II, code 122 |
| [`09-After-10th/`](09-After-10th/README.md) | Class XI admissions, official links, 9 PM IST tracker |
| [`10-PW-NSAT/`](10-PW-NSAT/README.md) | PW scholarship test: syllabus, practice, registration |

Inside each subject the numbered folders are the same set of places: syllabus,
textbook, notes, solutions, practice, past papers, revision. Drop PDFs into the
folder they belong in. The list of folders is `scripts/structure.conf` at the
repository root; `scripts/build_structure.sh` creates any that are missing.
