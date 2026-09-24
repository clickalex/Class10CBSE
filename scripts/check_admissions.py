#!/usr/bin/env python3
"""Conservative official-page monitor. No automatic open/closed/date claims.

Standard library only; bounded HTML fetches, no login, PDF parsing or JS execution.
Run --help for output paths. Network failures remain unknown, never 'not open'.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 2_000_000
MONITOR_VERSION = 2
SCOPE = re.compile(r'\b(?:class[\s-]*(?:xi|11)(?![\w])|senior\s+secondary|school\s+(?:admission|entrance)|SET\s+bulletin|LEST)\b', re.I)
NOTICE = re.compile(r'admission|application|registration|prospectus|bulletin|entrance|deadline|last\s+date|counselling', re.I)
DATE = re.compile(r'\b(?:\d{1,2}[-/.]\d{1,2}[-/.]20\d{2}|20\d{2}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan\w*|Feb\w*|Mar\w*|Apr\w*|May|Jun\w*|Jul\w*|Aug\w*|Sep\w*|Oct\w*|Nov\w*|Dec\w*)\.?\s*,?\s*20\d{2})\b', re.I)


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.links, self.parts = [], [], []
        self.hidden = 0
        self.anchor = None
        self.anchor_parts = []

    def flush(self):
        text = ' '.join(' '.join(self.parts).split())
        if text:
            self.lines.append(text)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1
        if self.hidden:
            return
        if tag in ('p', 'div', 'li', 'br', 'tr', 'h1', 'h2', 'h3', 'h4', 'a'):
            self.flush()
        if tag == 'a':
            self.anchor = dict(attrs).get('href', '')
            self.anchor_parts = []

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.hidden = max(0, self.hidden - 1)
            return
        if self.hidden:
            return
        if tag == 'a' and self.anchor is not None:
            self.links.append((' '.join(' '.join(self.anchor_parts).split()), self.anchor))
            self.anchor = None
        if tag in ('p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'a'):
            self.flush()

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
            if self.anchor is not None:
                self.anchor_parts.append(data)


def analyse(text, url, session, terms=()):
    # Literal, source-specific terms; never execute regex supplied by a content file.
    patterns = [re.escape(t) + (r'(?!\w)' if re.search(r'class\s+(?:xi|11)$', t, re.I) else '')
                for t in terms]
    scope = re.compile('|'.join(patterns), re.I) if terms else SCOPE
    parser = PageText()
    parser.feed(text)
    parser.flush()
    visible = ' '.join(parser.lines)
    if len(visible) < 80 or re.search(r'just a moment|verify you are human|access denied|enable javascript and cookies|requested URL was not found', visible, re.I):
        raise ValueError('Empty, blocked or JavaScript-only page; manual check required')
    candidates = []
    for label, href in parser.links:
        # Link labels/paths can identify a PDF even when its contents are not readable.
        if scope.search(label + ' ' + href):
            absolute = urljoin(url, href)
            if urlsplit(absolute).scheme in ('http', 'https'):
                candidates.append({'text': label, 'url': absolute})
    linked_text = {item["text"] for item in candidates}
    for line in parser.lines:
        if line not in linked_text and scope.search(line) and (NOTICE.search(line) or terms):
            candidates.append({'text': line, 'url': url})
    unique = {(c['text'], c['url']): c for c in candidates}
    all_evidence = sorted(unique.values(), key=lambda c: (c['text'], c['url']))
    # Fingerprint ALL full notices before limiting the saved/displayed snippets.
    # A new deadline late in a long page must not silently look unchanged.
    digest = hashlib.sha256(json.dumps(all_evidence, sort_keys=True).encode()).hexdigest()
    evidence = [dict(item) for item in all_evidence[:30]]
    for item in evidence:
        item['target_year_mentioned'] = bool(re.search(r'(?<!\d)' + session[:4] + r'(?!\d)', item['text'] + ' ' + item['url']))
        item['date_mentions'] = DATE.findall(item['text'])
        signals = []
        for label, pattern in (
            ('registration opening / application notice', r'registration|apply|application|forms?'),
            ('closing date / extension notice', r'last\s+date|deadline|clos|extend|extension'),
            ('test schedule / exam notice', r'entrance|test|exam|schedule'),
        ):
            if re.search(pattern, item['text'], re.I):
                signals.append(label)
        item['signals'] = signals  # Never promoted to confirmed admission status.
        item['text_truncated'] = len(item['text']) > 700
        item['text'] = item['text'][:700]
    return {'fingerprint': digest, 'evidence': evidence, 'evidence_count': len(all_evidence)}


def fetch(url):
    for attempt in range(2):
        try:
            req = Request(url, headers={'User-Agent': 'Class10CBSE-AdmissionMonitor/1.0', 'Accept': 'text/html'})
            with urlopen(req, timeout=20) as response:
                if 'html' not in response.headers.get('Content-Type', '').lower():
                    raise ValueError('Not an HTML page; open the official document manually')
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError('Page exceeds the 2 MB limit')
                return raw.decode(response.headers.get_content_charset() or 'utf-8', errors='replace'), response.geturl()
        except Exception:
            if attempt:
                raise
            time.sleep(1)


def check_source(url, previous, session, now, fetcher=fetch, terms=()):
    terms = sorted(set(terms))
    old = previous if (previous.get('session') == session
                       and previous.get('monitor_terms', []) == terms
                       and previous.get('monitor_version') == MONITOR_VERSION) else {}
    result = {'monitor_version': MONITOR_VERSION, 'url': url, 'session': session, 'monitor_terms': terms, 'checked_at': now, 'registration_status': 'Unknown — manual verification required'}
    try:
        text, final_url = fetcher(url)
        result.update(analyse(text, final_url, session, terms))
        result['last_success_at'] = now
        result['changed'] = bool(old.get('fingerprint') and old['fingerprint'] != result['fingerprint'])
        result['check_status'] = 'changed' if result['changed'] else ('unchanged' if old.get('fingerprint') else 'first_check')
        result['final_url'] = final_url
    except Exception as exc:
        result.update(check_status='error', changed=False, error=f'{type(exc).__name__}: {exc}'[:300],
                      fingerprint=old.get('fingerprint'), last_success_at=old.get('last_success_at'),
                      evidence=old.get('evidence', []), evidence_count=old.get('evidence_count', 0))
    result['health_changed'] = bool(old.get('check_status') and
                                    (old['check_status'] == 'error') != (result['check_status'] == 'error'))
    return result


def safe_md(text):
    # Remote snippets are quoted as text, never executable markup or mentions.
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('@', '&#64;').replace('`', "'").replace('[', '&#91;').replace(']', '&#93;').replace('\n', ' ')


def report_markdown(config, report):
    lines = ['# After Class 10 — daily admission watch', '',
             f"Target session: **{config['target_session']}** · Checked: **{report['checked_at']}**", '',
             'Scheduled for **9 PM Asia/Kolkata (15:30 UTC)**; GitHub may delay scheduled runs.', '',
             '**[Open the live HTML report on the website](https://clickalex.github.io/Class10CBSE/after-10th/report.html)**', '',
             '**This is a notice/change detector, not confirmation that registration is open or closed.**',
             'Dates in snippets are unverified mentions, not deadlines. Read the current prospectus or scholarship terms; the test cycle may differ from the admission year.',
             'PDF/image contents and JavaScript-only notices are not read. An error or no match does NOT mean applications have not started.', '']
    for institution in config['institutions']:
        lines += [f"## {institution['name']}", institution['route'], '',
                  f"Cycle: {institution.get('cycle', config['target_session'])}", '',
                  f"Expected dates: {institution['expected_window']}", '']
        for url in institution['sources']:
            item = report['sources'][url]
            lines += [f"- Official source: <{url}>", f"- Check: **{item['check_status']}**; registration: **unknown**.",
                      f"- Last successful fetch: {item.get('last_success_at') or 'Never'}"]
            if item.get('error'):
                lines.append(f"- Fetch failed: {safe_md(item['error'])}. Any evidence below is from an older successful check.")
            if not item['evidence']:
                lines.append('- No readable evidence available. Check the official portal manually.' if item['check_status'] == 'error'
                             else '- No matching admission/scholarship notice in the readable HTML. Check the official portal manually.')
            count = item.get('evidence_count', len(item['evidence']))
            if count > 12:
                lines.append(f'- Showing up to 12 of {count} matching notices. All notices are compared; open the source to review any omitted items.')
            for evidence in item['evidence'][:12]:
                year = 'target year mentioned, verify scope' if evidence['target_year_mentioned'] else 'target year not established'
                lines += [f"  - {safe_md(evidence['text'])} ({year})", f"    <{evidence['url']}>"]
                if evidence.get('text_truncated'):
                    lines.append('    Snippet shortened; date mentions below may come from the full notice text.')
                if evidence.get('signals'):
                    lines.append('    Possible notice types (unverified): ' + '; '.join(evidence['signals']))
                if evidence['date_mentions']:
                    lines.append('    Unverified date mentions: ' + ', '.join(evidence['date_mentions']))
            lines.append('')
    return '\n'.join(lines) + '\n'


def source_scopes(config):
    scopes = {}
    for inst in config['institutions']:
        for url in inst['sources']:
            scopes.setdefault(url, set()).update(inst.get('monitor_terms', ()))
    # If a source also serves a default school entry, retain school coverage.
    for inst in config['institutions']:
        if not inst.get('monitor_terms'):
            for url in inst['sources']:
                if scopes[url]:
                    scopes[url].update(('class xi', 'class 11', 'senior secondary', 'school admission', 'school entrance', 'set bulletin', 'lest'))
    return {url: sorted(terms) for url, terms in scopes.items()}


def load_state(path):
    """A missing/invalid cache is a new baseline, never a reason to skip today's check."""
    if not path.exists():
        return {}
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(state, dict) or not isinstance(state.get('sources'), dict):
            raise ValueError('invalid state structure')
        for item in state['sources'].values():
            if not isinstance(item, dict) or not isinstance(item.get('evidence'), list):
                raise ValueError('invalid source structure')
            for evidence in item['evidence']:
                if (not isinstance(evidence, dict)
                        or not isinstance(evidence.get('text'), str)
                        or not isinstance(evidence.get('url'), str)
                        or not isinstance(evidence.get('date_mentions'), list)
                        or not isinstance(evidence.get('target_year_mentioned'), bool)):
                    raise ValueError('invalid cached evidence')
        return state
    except (OSError, ValueError) as exc:
        print(f'Warning: ignoring unreadable/invalid admission cache: {exc}', file=sys.stderr)
        return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', type=Path, default=ROOT / 'site/content/admissions.json')
    ap.add_argument('--state', type=Path, default=ROOT / '.admission-monitor/state.json')
    ap.add_argument('--report', type=Path, default=ROOT / '.admission-monitor/report.md')
    args = ap.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    old = load_state(args.state)
    now = datetime.now(ZoneInfo(config['timezone'])).isoformat(timespec='seconds')
    scopes = source_scopes(config)
    urls = sorted(scopes)
    def run(url):
        return url, check_source(url, old.get('sources', {}).get(url, {}), config['target_session'], now, terms=scopes[url])
    with ThreadPoolExecutor(max_workers=4) as pool:
        sources = dict(pool.map(run, urls))
    report = {'checked_at': now, 'session': config['target_session'], 'sources': sources}
    args.state.parent.mkdir(parents=True, exist_ok=True)
    temp = args.state.with_suffix('.tmp')
    temp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temp.replace(args.state)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report_markdown(config, report), encoding='utf-8')
    # The HTML page is rendered only by site/build.py (--admission-state), the
    # same renderer the publishing workflows use, so docs/ is never touched here.
    print(f"Checked {len(urls)} sources; {sum(s['check_status'] == 'error' for s in sources.values())} errors. Report: {args.report}")
    print(f"Preview the website report: python3 site/build.py --out /tmp/site --admission-state {args.state}")
    # Partial failures must still publish their report. Fail the run if ALL fail.
    return 1 if all(s['check_status'] == 'error' for s in sources.values()) else 0


if __name__ == '__main__':
    raise SystemExit(main())
