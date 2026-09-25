# Whole-repository audit — 21 September 2026

Scope: everything in the repository on branch `arena/01a0c05e-class10cbse`
(commit `52f8897`), i.e. the folder scaffold, the site generator and its
content, the published `docs/`, the scripts, the tests, the workflow and the
documentation. The admission monitor's own feature audit from 20 September 2026
remains at
[`study/09-After-10th/02-Admission-Tracker/AUDIT.md`](../study/09-After-10th/02-Admission-Tracker/AUDIT.md);
this file covers the rest and the structure work that followed.

## Method

1. Ran every gate the repository already had: `scripts/check_all.sh`
   (folder tree, content JSON, site build + internal link check, offline
   tests) — all passed at the start, 69 tests.
2. Rebuilt the site into a scratch directory and diffed it against the
   committed `docs/` — identical, so the published folder was not stale.
3. Traversed all 496 published HTML files with an independent checker for:
   head metadata, favicon, canonical/OG, language attribute, heading outline,
   duplicate element ids, leaked template internals, placeholder links.
4. Re-derived every number the README claims from `site/content/` and from the
   built site.
5. Audited content integrity: schema consistency across all 175 chapters,
   duplicate ids, duplicate question stems, empty questions/answers.
6. Re-checked the publishing plumbing: Pages folder, `.nojekyll`, 404, gitignore
   coverage, icon reproducibility, workflow permissions.

## Found and fixed in this change

| # | Finding | Fix |
|---|---|---|
| 1 | No favicon or touch icon on any page; browsers 404'd on `/favicon.ico` | `assets/images/` brand set (SVG favicon + generated PNGs), linked from the shared head partial |
| 2 | No `sitemap.xml` / `robots.txt`; ~500 pages undiscoverable by crawlers | build writes both from the page list; tests pin the sitemap to the page set |
| 3 | No canonical or Open Graph metadata on any page | head partial emits canonical, OG and Twitter tags per page |
| 4 | Heading outline jumped `h1 → h3` on 24 pages (chapter index, Q&A bank, drill of every subject) | those section headings are now `<h2 class="sect">` with a compact style |
| 5 | 404 page had no meta description and was indexable | `notfound.html` partial: description + `robots: noindex` + favicon |
| 6 | Hindi and Sanskrit pages declared `lang="en"` over Devanagari content | per-subject `lang` (`hi`, `sa`) on `<html>` |
| 7 | The shared shell (head, header, sidebar, footer, buttons) existed only as Python f-strings inside `build.py` | `site/partials/` component files + `site/layout.py` renderer; button/chip/callout/chapter-nav markup now lives once in `partials/buttons.html` |
| 8 | Nothing guaranteed `docs/` matched the sources; a hand edit or a missed rebuild would publish silently | drift gate in `scripts/check_all.sh` step 4, `tests/test_site_structure.py`, and the staged `checks.yml` |
| 9 | Committed PNG icons had no source and could silently disagree with the theme | `scripts/make_icons.py` (stdlib-only) regenerates them; `--check` is a gate |
| 10 | The two optional workflows had no home because pushing `.github/workflows/` needs workflow-write permission | `temp-workflow/` staging folder with install instructions |
| 11 | Theme sources and published assets were flat single folders | typed folders: `site/theme/{css,js}`, published `docs/assets/{css,js,img}` |

## Verified clean — no action needed

- Internal links: 0 broken across 496 files; duplicate ids: none after fix #4/#7.
- README statistics reproduce exactly: 175 chapter pages, 2,133 written Q&A,
  1,426 MCQs, 20 exams × 10 mocks + 187 chapter mocks, 1,197 pooled MCQs,
  15 after-10th options (7 school, 3 diploma, 5 scholarship).
- Content integrity: one schema across all 175 chapters (formulas only where
  the subject has them), no duplicate chapter ids, no duplicate MCQ stems
  within a subject, no empty question or answer. Repeated Hindi stems such as
  "कहानी का संदेश क्या है?" belong to different chapters and are intended.
- No TODO/FIXME/lorem placeholders; the `XXX` strings in Hindi letter-writing
  samples are deliberate privacy placeholders taught in the chapter.
- Folder scaffold complete: 320 directories from `structure.conf`, every
  subject README present; no trailing whitespace; `git diff --check` clean.
- Admission watch: cron `30 15 * * *` UTC is 21:00 Asia/Kolkata; target session
  2027-28; permissions least-privileged (`contents: read`, `issues: write`).
- `.gitignore` excludes study binaries (PDF/video/archive) while the generated
  icons are intentionally tracked.

## Not verifiable in this environment

- Official external URLs (cbseacademic.nic.in and the 17 monitored sources) are
  unreachable from the sandbox (TLS handshake refused); only internal links are
  checked here. The daily monitor remains the external-change detector and
  labels all dates as unverified.
- Social-crawler rendering of the OG tags, and real-browser behaviour of the
  new favicon links, need the live Pages deployment to confirm visually.
- The staged workflows parse and describe real jobs but have never run on
  GitHub Actions; installing them is a manual, permission-gated step.

## Reproduce

```bash
scripts/check_all.sh                 # six gates, 84 offline tests
python3 site/build.py --out /tmp/x && diff -r /tmp/x docs   # publish drift
python3 scripts/make_icons.py --check                       # icon reproducibility
```
