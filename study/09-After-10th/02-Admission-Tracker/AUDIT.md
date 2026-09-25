# Pre-merge audit — 20 September 2026

## Scope

Reviewed this feature change: the 15-entry admission/scholarship directory,
PW NSAT hub, folder/README integration, generated navigation, monitor, tests
and daily GitHub Actions workflow. Existing subject teaching material was not
re-fact-checked chapter by chapter.

## Findings fixed

- **Missed late-page changes:** fingerprinting was limited to 30 shortened
  notices. It now compares every matching notice's full text before limiting
  stored/displayed previews. Reports disclose omitted items and shortened text.
- **Lost dates in long notices:** date extraction now happens before snippet
  shortening, and recognises ordinal dates/month abbreviations.
- **Class XII false matches:** custom Class XI / Class 11 filters now reject
  Class XII / Class 110 rather than treating them as Class XI notices.
- **Cache failure:** malformed or unreadable cached state now warns and starts
  a new baseline instead of stopping the run. Monitor-version changes also
  reset the baseline; workflow cache namespace advanced to v2.

## Validation results

- `bash scripts/check_all.sh --quiet`: passed, including **37 offline tests**.
- **454 HTML files**: no broken internal links, missing local assets,
  broken local fragment references or duplicate IDs in the audit traversal.
- Scratch build matched committed `docs/` byte-for-byte; no generated drift.
- Python compilation, shell syntax, theme JavaScript syntax and
  `git diff --check`: passed.
- Workflow YAML parsed; daily `30 15 * * *` UTC was verified as 21:00
  Asia/Kolkata. Read-only content permission and issue-write permission checked.
- Workflow report JavaScript syntax and mocked create/update/notice-change/
  health-change paths passed without writing to GitHub.
- Directory validation: 7 school routes, 3 diploma routes, 5 scholarship tests;
  all **17 unique configured official URLs** are included in monitoring scopes.
- HTTP success, retries, timeout, oversized response and non-HTML rejection
  are covered with offline test doubles.

## Unverified / operational limitations

- The live monitor attempted all 17 sources from this sandbox; every request
  ended in a TLS/SSL EOF error. It produced an error report and a nonzero exit
  rather than claiming applications were closed. Successful live monitoring
  must be verified with a manual GitHub Actions run after deployment.
- Full `actionlint` could not be installed because its release download failed
  with EOF. Workflow parsing and mocked JavaScript checks are not a substitute
  for a successful production Actions run.
- This is a conservative notice-change detector, **not automatic confirmation
  of open/closed registrations or deadlines**. PDFs, scanned notices,
  linked-page contents and JavaScript-only updates still require manual review.
- The site distinguishes admission years from scholarship exam years and labels
  unverified dates. The PW NSAT date snapshot is explicitly dated, not live.
- Scheduling requires the workflow on the default branch, Actions and Issues
  enabled, and permission to update issues. GitHub may delay/disable schedules;
  users must inspect report timestamps and retain personal deadline reminders.

GitHub push/merge permissions are a separate release gate: a previous push was
rejected because the connected GitHub App lacked workflow-write permission.
No token or credentials are stored in this repository.

## Manual-install packaging

The audited workflow is configured in
`.github/workflows/admission-watch.yml`.
The cron regression test verifies the active path.
