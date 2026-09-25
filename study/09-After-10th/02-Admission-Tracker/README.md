# Admission tracker — daily at 9 PM India time

## What runs

The active workflow is configured in
[`.github/workflows/admission-watch.yml`](../../../.github/workflows/admission-watch.yml).
It schedules `scripts/check_admissions.py` at **21:00 Asia/Kolkata**, using GitHub's UTC cron **`30 15 * * *`**.
The scheduler runs on GitHub; the website does not need to be open.

It fetches official HTML sources with a timeout, retry and size limit, isolates
school, diploma and scholarship notice text and links, compares them with the previous run,
and reports source timestamps, errors, relevant snippets and date mentions.
State is restored through GitHub Actions cache. Evicted cache means a new
baseline, not “registration closed”. Network failures preserve the last good
observations, explicitly labelled stale. All-source failure also fails the run.

After every check the workflow rebuilds the website with the results
(`site/build.py --admission-state`) and publishes it to GitHub Pages, so the
[live report](https://clickalex.github.io/Class10CBSE/after-10th/report.html)
shows when the check actually ran and, for each source, its last successful
fetch, status badge and captured notices. It publishes even when some sources
fail to load; those show the error next to their last good fetch. The reviewed
copy of the workflow is
[`.github/staged-workflows/admission-watch.yml`](../../../.github/staged-workflows/admission-watch.yml).

**This does not automatically verify open/closed status or exact deadlines.**
A notice can be outdated, refer to another class or category, or exist only in
a PDF, image, linked page or JavaScript portal. The checker does not parse those
contents. Check the linked prospectus manually; no match is still **unknown**.
Expected dates remain unverified rather than invented. Date mentions in a
snippet are evidence to inspect, not necessarily registration or exam dates.

## Enable it once

1. Set **Settings → Pages → Build and deployment → Source** to
   **GitHub Actions**, so the workflow can publish the report page. A push made
   by a workflow does not start a *Deploy from a branch* build; see
   [`.github/staged-workflows/README.md`](../../../.github/staged-workflows/README.md).
2. Ensure `.github/workflows/admission-watch.yml` on **main** matches the
   reviewed copy in `.github/staged-workflows/` (install `deploy-pages.yml`
   from there too, so content pushes keep the results on the page).
3. In GitHub **Settings → Actions**, allow Actions. Enable repository Issues.
   Repository/organisation policy must allow the workflow's `issues: write`,
   `pages: write` and `id-token: write` permissions. No personal token or
   third-party service is needed.
4. In **Actions → After Class 10 admission watch → Run workflow**, run once.
5. Open the automatically created **“After Class 10 — daily admission watch”**
   issue and click **Subscribe**. The body is refreshed every run. Changed
   matching notices or changed fetch health create a comment; unchanged runs do not spam comments.
   Fetch errors appear in the daily report, not as “not started”. GitHub's
   notification settings control email delivery; this is not an SMS service.
6. Follow the report from the website's **Open latest daily report** button
   ([live HTML report](https://clickalex.github.io/Class10CBSE/after-10th/report.html)).
   The live report opens directly on an HTML web page showing monitored institutions,
   sources, notice snippets, dates, and fetch health without requiring GitHub.
   It states when the check last ran (in IST, with “N hours ago”) and each
   source's last successful fetch.
   Full Markdown and JSON reports are also workflow artifacts (30-day retention).

GitHub can delay cron execution (a 21:00 run can start hours late), and may
disable scheduled workflows after 60 days of inactivity in a public repository.
The report page shows the actual check time and warns visitors when the last
check is more than 36 hours old; check the Actions page if you see that
warning. This is not an exact-to-the-minute or guaranteed alert.
If Issues permissions are blocked, the artifacts still contain the report.

## Run locally / test

```bash
python3 scripts/check_admissions.py
cat .admission-monitor/report.md
# preview the website report with those results (never build them into docs/)
python3 site/build.py --out /tmp/site --admission-state .admission-monitor/state.json
python3 -m unittest discover -s tests -v
```

Outputs under `.admission-monitor/` are ignored by Git, and the checker never
writes into `docs/`: a plain `python3 site/build.py` always renders the report
page without results, so `docs/` stays equal to a fresh build. No network
request runs as part of the site build. Use `--config`, `--state` and `--report` to override
paths. Changing the target session resets comparison baselines. Keep personal
application numbers, passwords, identity documents and payment details out of Git.

## Personal tracking sheet

Copy locally, and fill only after checking the official current-session notice.

| School / stream | Session | Registration starts | Last date / extension | Test date | Official notice URL | Verified on (IST) | Applied? |
|---|---|---|---|---|---|---|---|
| JMI | 2027–28 | Unverified | Unverified | Unverified | | | |
| AMU | 2027–28 | Unverified | Unverified | Unverified | | | |
| BHU / CHS | 2027–28 | Unverified | Unverified | Unverified | | | |
| JNV | 2027–28 | Unverified | Unverified | Unverified | | | |
| Local KV | 2027–28 | Unverified | Unverified | Not applicable | | | |

Set personal calendar reminders seven days and two days before each verified
closing date. Recheck for extensions and correction windows. Do not wait for
the monitor if you are close to a deadline.

## Expanded monitoring scope

All 15 directory entries (17 unique official URLs) are monitored, including
PW NSAT, TALLENTEX, ANTHE, iACST and VMC VIQ. The cron time is unchanged.
`monitor_terms` in `site/content/admissions.json` contains literal per-source
keywords for diploma/scholarship sources; school entries without custom terms
keep the Class XI scope. Shared URLs are fetched once with combined terms.
Changing terms resets the baseline to avoid a misleading change alert.

The target year is an admission-planning reference, not the universal exam year.
Scholarship tests can run during Class X for later coaching sessions. A source
may mention multiple courses or cycles: read its current terms and check the
correct course, class, mode and deadline manually. The report includes each
entry's cycle note, and never promotes an unverified date to confirmed status.

Add a row to your private tracking sheet for each new option you shortlist.
Record scholarship acceptance/expiry dates separately from test registration
deadlines and school admission deadlines.

## Reliability safeguards

The monitor compares **all matching notices and their full text**, while saving
up to 30 shortened evidence snippets per source. The issue displays up to 12
per source and labels omitted notices/shortened snippets; open the official
source to review changes outside that preview. Dates are extracted before text
is shortened. All date mentions still require manual interpretation.

Missing, corrupted or obsolete cached observations become a new baseline with
a warning, not a skipped check or a claim that registration is closed. Changing
monitor versions resets comparisons. Ordinal dates (such as 21st Sept. 2026)
are recognised as unverified date mentions.
