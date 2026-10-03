#!/usr/bin/env python3
"""Check that every official CBSE file the site links to still answers.

site/content/downloads.json names the exact URL of every previous-year paper,
sample paper, marking scheme and question bank the site offers. CBSE moves and
renames files without notice, so run this now and then (it needs the internet;
the build itself never does):

    python3 scripts/check_downloads.py                 # probe every URL
    python3 scripts/check_downloads.py --offline       # validate the manifest only
    python3 scripts/check_downloads.py --subject maths # one subject (plus the list pages)
    python3 scripts/check_downloads.py --timeout 40 --workers 4

Each URL gets a HEAD request, then a one-byte GET if the server refuses HEAD.
A file is "ok" when the server answers 2xx with something that is not an HTML
page (CBSE answers a missing file with a 200 HTML error page or a placeholder
error.pdf, so the content type is checked too).

Exit status:  0  every link answered
              1  a link is broken, or the manifest is invalid
              2  the servers could not be reached at all (nothing was verified)
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

import downloads  # noqa: E402  (needs the sys.path entry above)

USER_AGENT = "Mozilla/5.0 (compatible; class10cbse-link-check/1.0; +https://github.com/clickalex/Class10CBSE)"
OK, BROKEN, UNREACHABLE = "ok", "broken", "unreachable"


def probe(url, timeout=20):
    """Return (status, detail) for one URL. status: ok | broken | unreachable."""

    def open_url(method):
        headers = {"User-Agent": USER_AGENT}
        if method == "GET":
            headers["Range"] = "bytes=0-0"
        request = urllib.request.Request(url, method=method, headers=headers)
        return urllib.request.urlopen(request, timeout=timeout)

    last = None
    for method in ("HEAD", "GET"):
        try:
            with open_url(method) as response:
                kind = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if kind == "text/html" and url.lower().endswith((".pdf", ".zip")):
                    return BROKEN, f"HTTP {response.status} but an HTML page ({kind}), not a file"
                return OK, f"HTTP {response.status} {kind or 'no content type'}"
        except urllib.error.HTTPError as err:
            last = (BROKEN, f"HTTP {err.code}")
            if err.code in (403, 405, 501) and method == "HEAD":
                continue          # some servers refuse HEAD but serve GET
            return last
        except (urllib.error.URLError, OSError, ValueError) as err:
            reason = getattr(err, "reason", err)
            return UNREACHABLE, str(reason)
    return last or (UNREACHABLE, "no answer")


def collect(data, subject=None):
    """(description, url) pairs to check; --subject keeps one subject's files."""
    files = downloads.file_urls(data)
    if subject:
        files = [(d, u) for d, u in files if d.startswith(subject)]
    return files + downloads.list_urls(data)


def check(pairs, timeout=20, workers=6, probe_fn=probe):
    """Probe every pair; returns [(description, url, status, detail)]."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda pair: probe_fn(pair[1], timeout), pairs))
    return [(d, u, s, detail) for (d, u), (s, detail) in zip(pairs, results)]


def summarise(results):
    """Exit status for a list of check() results."""
    broken = [r for r in results if r[2] == BROKEN]
    unreachable = [r for r in results if r[2] == UNREACHABLE]
    if broken:
        return 1
    if results and len(unreachable) == len(results):
        return 2
    return 1 if unreachable else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--offline", action="store_true", help="validate the manifest only; no network")
    ap.add_argument("--subject", metavar="SLUG", help="check one subject's files (e.g. maths)")
    ap.add_argument("--timeout", type=float, default=20, help="seconds per request (default 20)")
    ap.add_argument("--workers", type=int, default=6, help="parallel requests (default 6)")
    args = ap.parse_args(argv)

    data = downloads.load()
    slugs = [s["slug"] for s in json.loads(
        (ROOT / "site" / "content" / "subjects.json").read_text(encoding="utf-8"))]
    problems = downloads.validate(data, slugs)
    for problem in problems:
        print(f"MANIFEST  {problem}")
    if problems:
        print(f"check_downloads: manifest invalid ({len(problems)} problem(s))")
        return 1
    pairs = collect(data, args.subject)
    if args.subject and len(pairs) == len(downloads.list_urls(data)):
        print(f"check_downloads: no files for subject {args.subject!r}")
        return 1
    if args.offline:
        print(f"check_downloads: manifest valid, {len(pairs)} URL(s) not probed (--offline)")
        return 0

    results = check(pairs, args.timeout, args.workers)
    width = max(len(r[0]) for r in results)
    nothing_answered = all(r[2] == UNREACHABLE for r in results)
    for description, url, status, detail in results:
        mark = {"ok": "ok       ", "broken": "BROKEN   ", "unreachable": "NO ANSWER"}[status]
        # when no server answered at all one line below says so; 30 identical errors would hide it
        if status == BROKEN or (status == UNREACHABLE and not nothing_answered):
            print(f"{mark} {description:<{width}}  {detail}  {url}")
    counts = {s: sum(1 for r in results if r[2] == s) for s in (OK, BROKEN, UNREACHABLE)}
    print(f"check_downloads: {counts[OK]} ok, {counts[BROKEN]} broken, "
          f"{counts[UNREACHABLE]} unreachable (of {len(results)}), checked against the manifest dated "
          f"{data['checked_on']}")
    code = summarise(results)
    if code == 2:
        print(f"check_downloads: could not reach any server - nothing was verified (offline?). "
              f"First error: {results[0][3]}")
    return code


if __name__ == "__main__":
    sys.exit(main())
