# Manual workflow setup

This folder is temporary storage for a **ready-to-copy, inactive** GitHub Actions
workflow. Files here do not run, and merging this folder does not enable the
9 PM scheduler.

## Enable the daily admission and scholarship checker

After this feature is merged:

1. Open [`admission-watch.yml`](admission-watch.yml) and copy its **entire raw
   contents** (not Markdown code fences).
2. On GitHub, open `clickalex/Class10CBSE` on `main`, then choose
   **Add file → Create new file**.
3. Use this exact filename:

   ```text
   .github/workflows/admission-watch.yml
   ```

4. Paste the YAML unchanged. Commit it to `main`, or create and merge a PR if
   branch protection requires one. Use your own authorised GitHub account.
5. Make sure GitHub Actions and repository Issues are enabled. Organisation
   policy must allow the workflow's `issues: write` permission.
6. Go to **Actions → After Class 10 admission watch → Run workflow**, select
   `main`, and run once. Inspect the logs and report artifacts.
7. Open the automatically created **After Class 10 — daily admission watch**
   issue and **Subscribe** for notice-change/fetch-health alerts.

The workflow runs daily at **9 PM India time (Asia/Kolkata)** using
`30 15 * * *` UTC. GitHub can delay scheduled runs. The first successful manual
run is needed to verify real source access; no live success is claimed here.

The template uses `GITHUB_TOKEN` automatically; no personal token, password or
new secret is required. It reports unverified notice changes and fetch errors,
not guaranteed registration status. See the
[tracker instructions](../09-After-10th/02-Admission-Tracker/README.md).

You can remove this temporary folder after installing the active workflow.
Tests accept either location, preferring the active workflow when present.
