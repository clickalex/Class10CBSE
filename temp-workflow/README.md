# temp-workflow — staged GitHub Actions, installed by hand when wanted

The two files here are complete, ready-to-run workflows that are **not**
installed in `.github/workflows/` on purpose:

| File here | Install as | What it does once installed |
|---|---|---|
| `checks.yml` | `.github/workflows/checks.yml` | On every push and pull request: folder tree, content JSON, site build + link check, unit tests, docs/-drift check and icon reproducibility (`scripts/check_all.sh` plus the two publishing checks). |
| `deploy-pages.yml` | `.github/workflows/deploy-pages.yml` | On pushes to `main` that touch `site/`, `assets/` or `scripts/`: rebuild `docs/`, commit it if anything changed, then request a GitHub Pages build. |

The workflow that **is** live today is
[`.github/workflows/admission-watch.yml`](../.github/workflows/admission-watch.yml)
(the daily 9 PM IST admission notice checker); it needs no manual install.

## Why these are staged instead of committed to `.github/workflows/`

GitHub treats files under `.github/workflows/` specially: a push that adds or
changes one is rejected unless the credential used has workflow-write
permission. This repository is maintained through a connection that does not
carry that permission, so keeping the workflows here means ordinary commits
always succeed, and installing one is a deliberate one-time act by the
repository owner.

## Installing one

1. Copy the file into place, e.g.
   `cp temp-workflow/checks.yml .github/workflows/checks.yml`.
2. Commit and push **from an account or token allowed to manage workflow
   files** (your own login, or a fine-grained PAT with *Actions: write* /
   *Workflows: write*). GitHub will show the new workflow under
   **Settings → Actions** the moment it lands on the default branch.
3. `deploy-pages.yml` optionally uses a `PAGES_TOKEN` secret
   (**Settings → Secrets and variables → Actions**) so the commit it makes can
   trigger follow-up workflows; without the secret it falls back to the
   default token and still publishes, it just cannot start other workflows.

Delete nothing from this folder after installing: the copies here stay as the
reviewed source of truth, and `tests/test_site_structure.py` checks they still
describe a real, installable workflow.

Until a workflow is installed, run the same checks locally before pushing:

```bash
scripts/check_all.sh          # tree + JSON + build/links + tests
python3 site/build.py         # rebuild docs/, then commit site/ and docs/ together
python3 scripts/make_icons.py --check
```
