# staged-workflows — reviewed GitHub Actions, installed by hand when wanted

The files here are complete, ready-to-run workflows. They are the **reviewed
copies**: edits land here first, and the live files in `../workflows/` are
updated from them.

| File here | Install as | What it does once installed |
|---|---|---|
| `checks.yml` | `.github/workflows/checks.yml` | On every push and pull request: folder tree, content JSON, site build + link check, unit tests, docs/-drift check and icon reproducibility (`scripts/check_all.sh` plus the two publishing checks). |
| `admission-watch.yml` | `.github/workflows/admission-watch.yml` | Daily at 21:00 IST (and on **Run workflow**): checks the official admission / scholarship pages, updates the daily-watch issue, then rebuilds the website with the results and **publishes it to GitHub Pages**, so [the watch report](https://clickalex.github.io/Class10CBSE/after-10th/report.html) shows when the check ran and when each source was last fetched. |
| `deploy-pages.yml` | `.github/workflows/deploy-pages.yml` | On pushes to `main` that touch `site/`, `assets/` or `scripts/` (and on **Run workflow**): rebuild `docs/`, commit it if anything drifted, then publish a fresh build to GitHub Pages that keeps the latest watch results on the report page. |

## Publishing the site: one-time Pages setting

`admission-watch.yml` and `deploy-pages.yml` publish the site themselves with
the official `actions/upload-pages-artifact` + `actions/deploy-pages` actions.
For that, set **Settings → Pages → Build and deployment → Source** to
**GitHub Actions** (it is currently *Deploy from a branch*, `main` → `/docs`).
The site stays online while you switch; the next workflow run republishes it.

Why the switch is needed: the daily check runs on GitHub's servers, and its
results were never reaching the live site. The workflow only read the
repository, and even a commit made by a workflow's default `GITHUB_TOKEN`
**does not start a "Deploy from a branch" Pages build** (GitHub documents this;
it is also why the old `requestPagesBuild` step failed). Deploying from the
workflow avoids that limitation without any personal token, and avoids daily
bot commits to `docs/` that would clash with every pull request.

If the source is left on *Deploy from a branch*, both workflows print a
warning with this instruction. The daily run still tries to publish, but the
next push to `main` republishes `docs/`, whose report page has no check
results.

**Alternative (not implemented):** keep *Deploy from a branch* and give the
watch workflow a fine-grained personal access token (`contents: write`) as a
secret, so it commits the rebuilt report. That works, but the token expires,
and daily commits to `docs/` would conflict with pull requests.

## Why these are staged instead of edited live

GitHub treats files under `.github/workflows/` specially: a push that adds or
changes one is rejected unless the credential used has workflow-write
permission. This repository is maintained through a connection that does not
carry that permission, so keeping reviewed copies here means ordinary commits
always succeed, and installing one is a deliberate one-time act by the
repository owner.

## Installing

1. Switch the Pages source to **GitHub Actions** (above) *before* installing
   the two publishing workflows.
2. Copy each file into place, e.g.
   `cp .github/staged-workflows/admission-watch.yml .github/workflows/admission-watch.yml`
   (on github.com: open the file here, copy its contents, then **Add file →
   Create new file** / edit the file under `.github/workflows/` and paste).
3. Commit and push **from an account or token allowed to manage workflow
   files** (your own login, or a fine-grained PAT with *Workflows: write*).
   Installing `deploy-pages.yml` publishes the site straight away, with the
   latest watch results already on the report page.
4. To refresh the report immediately instead of waiting for 21:00 IST, open
   **Actions → After Class 10 admission watch → Run workflow**.

Delete nothing from this folder after installing: the copies here stay as the
reviewed source of truth, and `tests/test_site_structure.py` checks they still
describe a real, installable workflow that publishes the watch results.

Until a workflow is installed, run the same checks locally before pushing:

```bash
scripts/check_all.sh          # tree + JSON + build/links + tests
python3 site/build.py         # rebuild docs/, then commit site/ and docs/ together
python3 scripts/make_icons.py --check
```
