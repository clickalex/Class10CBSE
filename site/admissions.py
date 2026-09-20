"""Render the grouped after-Class-10 admissions directory and live HTML watch report."""
import html
import json
from pathlib import Path

GROUPS = (
    ('school', 'Class XI / intermediate schools', 'Entrance-test and merit/vacancy routes are labelled separately. Check eligibility before applying.'),
    ('diploma', 'Diploma / polytechnic colleges', 'An alternative to Class XI–XII, not a school stream. Verify course recognition, progression options, domicile and branch-specific eligibility.'),
    ('scholarship', 'Scholarship exams for Class 10 students', 'These are private coaching scholarship tests, not government cash scholarships or school admissions. Compare remaining fees, validity and award conditions; an “up to” award is not guaranteed.'),
)


def admissions_body(mock_ids=None):
    """mock_ids: {institution id: mock-test exam id} for the test-based routes
    that have a practice set in mock-test/; the build passes it, tests may not."""
    mock_ids = mock_ids or {}
    data = json.loads((Path(__file__).parent / 'content/admissions.json').read_text())
    esc = html.escape
    groups = {key: [] for key, _, _ in GROUPS}
    for inst in data['institutions']:
        links = ' · '.join(f'<a href="{esc(url, quote=True)}" target="_blank" rel="noopener">Official source {i}</a>'
                           for i, url in enumerate(inst['sources'], 1))
        category = inst.get('category', 'school')
        selection = inst.get('selection', 'test')
        mode = {'test': 'Test-based route', 'merit': 'Merit / vacancy route — no general entrance test',
                'verify': 'Selection process: verify current notice'}[selection]
        date = 'Not applicable: merit / vacancy route' if selection == 'merit' else 'Not confirmed here — verify the current cycle'
        extra = '<p><a href="../pw-nsat/index.html">PW NSAT detailed guide &amp; dated exam snapshot</a></p>' if inst['id'] == 'pw-nsat' else ''
        if inst['id'] in mock_ids:
            extra += (f'<p><a class="btn" href="../mock-test/{esc(mock_ids[inst["id"]], quote=True)}/index.html">'
                      'Practise a timed mock test &amp; check your score →</a></p>')
        groups[category].append(f'''<article class="admission-card" id="{esc(inst['id'])}">
<p class="kicker">{esc(inst['location'])}</p>
<h3>{esc(inst['name'])}</h3>
<p><strong>{esc(mode)}</strong></p><p>{esc(inst['route'])}</p>
<p><strong>Before applying:</strong> {esc(inst['eligibility'])}</p>
<dl class="admission-dates">
<dt>Cycle to check</dt><dd>{esc(inst.get('cycle', data['target_session']))}</dd>
<dt>Registration</dt><dd>Unverified — read the <a href="report.html">latest daily report</a> and official notice</dd>
<dt>Opening / last date</dt><dd>Not confirmed here — check the current official notice</dd>
<dt>Test date</dt><dd>{esc(date)}</dd>
<dt>When to check</dt><dd>{esc(inst['expected_window'])}</dd>
</dl><p>{links}</p>{extra}</article>''')
    sections = ''.join(f'<section id="{key}" aria-labelledby="{key}-heading"><h2 id="{key}-heading">{title} ({len(groups[key])})</h2><p>{intro}</p>{"".join(groups[key])}</section>' for key, title, intro in GROUPS)
    navigation = ' · '.join(f'<a href="#{key}">{title} ({len(groups[key])})</a>' for key, title, _ in GROUPS)
    return f'''
<p class="kicker">BEYOND CLASS 10 · ADMISSION TARGET {esc(data['target_session'])}</p>
<h1>After 10th: admissions &amp; scholarships</h1>
<p class="lede">Explore {len(data['institutions'])} options: Class XI schools, diploma colleges and scholarship exams.
School/college admissions and coaching scholarships are different decisions. Choose the route that fits your goals.</p>
<nav aria-label="Directory categories"><p>{navigation}</p></nav>
<div class="admission-watch">
<h2>Daily admission &amp; scholarship watch · 9 PM IST</h2>
<p>The checker is configured for <strong>21:00 Asia/Kolkata (15:30 UTC)</strong> every day.
All official sources listed below are included. It checks readable HTML notices and flags changed evidence and date mentions for review.
The live report is published directly on the website, so you can inspect notice changes, captured dates, and fetch health on the HTML report page without visiting GitHub.</p>
<p><a class="btn primary" href="report.html">Open latest daily report</a>
<a class="btn" href="https://github.com/clickalex/Class10CBSE/actions" target="_blank" rel="noopener">GitHub Actions &amp; run logs ↗</a></p>
<p><strong>Setup required:</strong> the workflow is configured in
<code>.github/workflows/admission-watch.yml</code> on the default branch. Enable GitHub Actions before scheduled checks run.
GitHub may delay a run. The daily run publishes updates to the live HTML report page; use its timestamp to check freshness.
Subscribe to the tracker issue on GitHub for email notice-change and fetch-health alerts.</p>
<p class="hint">This directory is not a live confirmation of registration. An unchanged page, failed fetch or missing notice does not mean applications have not started.
PDFs, scanned images, linked-page contents and JavaScript-only updates need manual review.
Old notices can remain online after deadlines. Never treat a login link as proof that registration is open.
Scholarship tests may happen during Class X for a later course year; do not confuse the test year with the admission session.</p>
</div>
{sections}
<h2>Make a practical shortlist</h2>
<ol>
<li>Choose Class XI or a diploma first. Compare marks requirements, age, fees, location, hostel and domicile rules in the current prospectus.</li>
<li>Keep 2–3 eligible admission options plus a local school backup. Check state eligibility before travelling or paying an application fee.</li>
<li>Try coaching scholarship tests only if the course suits you. Check total payable fees, award expiry, centre and online/offline restrictions.</li>
<li>Read the <a href="report.html">daily report</a>, then verify any application opening, closing date, extension or exam date on the official website.</li>
<li>Record verified deadlines in your calendar with reminders seven days and two days before them. Apply early and save receipts privately.</li>
</ol>
<h2>Documents &amp; preparation</h2>
<p>Prepare Class X marks/results when available, date-of-birth proof, photographs, signatures and applicable category/residence certificates.
Upload documents only on the official application portal. Check whether appearing candidates may apply before results.</p>
<p>Revise Class X subjects, then follow each test's own syllabus and official sample/past papers where available.
These options do not guarantee admission or an award. School, diploma and coaching fees are separate.</p>
<p><a href="https://github.com/clickalex/Class10CBSE/tree/main/09-After-10th">Open the after-10th folder &amp; tracker instructions</a></p>
'''


def report_body(state_path=None, mock_ids=None):
    """Render the full HTML body of the daily admission watch live report."""
    mock_ids = mock_ids or {}
    data = json.loads((Path(__file__).parent / 'content/admissions.json').read_text())
    esc = html.escape
    state = {}
    if state_path:
        p = Path(state_path)
        if p.exists():
            try:
                state = json.loads(p.read_text(encoding='utf-8'))
            except Exception:
                state = {}

    checked_at = state.get('checked_at', 'Scheduled daily at 9 PM IST (15:30 UTC)')
    session = state.get('session', data.get('target_session', '2027-28'))
    sources_data = state.get('sources', {})

    total_institutions = len(data['institutions'])
    total_sources = sum(len(inst['sources']) for inst in data['institutions'])
    changed_count = sum(1 for s in sources_data.values() if s.get('changed'))
    error_count = sum(1 for s in sources_data.values() if s.get('check_status') == 'error')
    unchanged_count = sum(1 for s in sources_data.values() if s.get('check_status') == 'unchanged')

    if sources_data:
        status_line = (f"{total_sources} sources monitored · {unchanged_count} unchanged · "
                       f"{changed_count} changed · {error_count} fetch errors")
    else:
        status_line = f"{total_sources} official portals monitored · Scheduled daily check"

    group_sections = []
    nav_links = []
    for gkey, gtitle, gintro in GROUPS:
        insts = [i for i in data['institutions'] if i.get('category', 'school') == gkey]
        if not insts:
            continue
        nav_links.append(f'<a href="#{gkey}">{esc(gtitle)} ({len(insts)})</a>')
        inst_cards = []
        for inst in insts:
            iid = inst['id']
            selection = inst.get('selection', 'test')
            mode = {'test': 'Entrance test route', 'merit': 'Merit / vacancy route',
                    'verify': 'Selection process: verify current notice'}[selection]
            date = 'Not applicable: merit / vacancy route' if selection == 'merit' else 'Not confirmed here — verify current cycle'

            source_blocks = []
            for sidx, url in enumerate(inst['sources'], 1):
                sinfo = sources_data.get(url, {})
                c_status = sinfo.get('check_status')
                if c_status == 'changed':
                    badge = '<span class="report-badge-change">Evidence Changed</span>'
                elif c_status == 'unchanged':
                    badge = '<span class="report-badge-ok">Unchanged</span>'
                elif c_status == 'error':
                    badge = '<span class="report-badge-err">Fetch Error</span>'
                elif c_status == 'first_check':
                    badge = '<span class="report-badge-base">First Check Recorded</span>'
                else:
                    badge = '<span class="report-badge-base">Monitored / Baseline</span>'

                last_succ = sinfo.get('last_success_at') or 'Pending scheduled run'
                err_html = f'<p class="hint"><strong>Fetch notice:</strong> {esc(sinfo.get("error", ""))} — open the portal directly.</p>' if sinfo.get('error') else ''

                evidence_items = []
                for ev in sinfo.get('evidence', [])[:8]:
                    ev_text = esc(ev.get('text', ''))
                    ev_url = esc(ev.get('url', url), quote=True)
                    tags = []
                    if ev.get('target_year_mentioned'):
                        tags.append(f'<span class="report-badge-ok">Target session {esc(session[:4])}</span>')
                    else:
                        tags.append('<span class="report-badge-base">Target year not established</span>')
                    for d in ev.get('date_mentions', []):
                        tags.append(f'<span class="report-badge-date">&#128197; {esc(d)}</span>')
                    for sig in ev.get('signals', []):
                        tags.append(f'<span class="report-badge-signal">{esc(sig)}</span>')
                    tag_str = ' '.join(tags)
                    evidence_items.append(
                        f'<div class="report-snippet">'
                        f'<div>{ev_text}</div>'
                        f'<div class="report-snippet-tags">{tag_str} &middot; <a href="{ev_url}" target="_blank" rel="noopener">Notice link &rarr;</a></div>'
                        f'</div>'
                    )

                if not evidence_items and not sinfo.get('error'):
                    evidence_items.append(
                        '<p class="hint">No matching admission or scholarship notice keywords found in the readable HTML. '
                        'Consult the official portal directly for PDF circulars and application bulletins.</p>'
                    )

                source_blocks.append(
                    f'<div class="report-source">'
                    f'<div class="report-source-top">'
                    f'<span class="report-source-url"><a href="{esc(url, quote=True)}" target="_blank" rel="noopener">{esc(url)}</a></span>'
                    f'{badge}'
                    f'</div>'
                    f'<p class="hint"><strong>Registration:</strong> Unknown — manual review required &middot; '
                    f'<strong>Last successful fetch:</strong> {esc(str(last_succ))}</p>'
                    f'{err_html}'
                    f'{"".join(evidence_items)}'
                    f'</div>'
                )

            extra_links = [f'<a href="index.html#{esc(iid)}">View {esc(inst["name"])} in directory &rarr;</a>']
            if iid in mock_ids:
                extra_links.append(f'<a class="btn" href="../mock-test/{esc(mock_ids[iid], quote=True)}/index.html">Practise timed mock test &rarr;</a>')
            links_html = ' &middot; '.join(extra_links)

            inst_cards.append(
                f'<article class="admission-card" id="report-{esc(iid)}">'
                f'<p class="kicker">{esc(inst["location"])}</p>'
                f'<h3>{esc(inst["name"])}</h3>'
                f'<p><strong>{esc(mode)}</strong> &middot; {esc(inst["route"])}</p>'
                f'<dl class="admission-dates">'
                f'<dt>Cycle</dt><dd>{esc(inst.get("cycle", session))}</dd>'
                f'<dt>Expected window</dt><dd>{esc(inst["expected_window"])}</dd>'
                f'<dt>Test date</dt><dd>{esc(date)}</dd>'
                f'</dl>'
                f'{"".join(source_blocks)}'
                f'<p>{links_html}</p>'
                f'</article>'
            )

        group_sections.append(
            f'<section id="{gkey}" aria-labelledby="{gkey}-heading">'
            f'<h2 id="{gkey}-heading">{esc(gtitle)} ({len(insts)})</h2>'
            f'<p>{esc(gintro)}</p>'
            f'{"".join(inst_cards)}'
            f'</section>'
        )

    nav_html = ' &middot; '.join(nav_links)
    return f'''
<p class="kicker">BEYOND CLASS 10 &middot; DAILY ADMISSION &amp; SCHOLARSHIP WATCH</p>
<h1>Daily admission &amp; scholarship watch report</h1>
<p class="lede">Daily automated checker monitoring {total_institutions} institutions and {total_sources} official web portals
for Class XI schools, polytechnic diplomas, and coaching scholarship tests. Scans for notice updates, application links, and date mentions.</p>

<div class="btnrow">
  <a class="btn primary" href="index.html">&larr; Back to admissions directory</a>
  <a class="btn" href="https://github.com/clickalex/Class10CBSE/actions" target="_blank" rel="noopener">GitHub Actions run logs &rarr;</a>
</div>

<nav aria-label="Report categories" style="margin: 16px 0 8px;"><p>{nav_html}</p></nav>

<div class="report-stat-grid">
  <div class="report-stat-card">
    <span class="report-stat-label">Target session</span>
    <span class="report-stat-val">{esc(session)}</span>
  </div>
  <div class="report-stat-card">
    <span class="report-stat-label">Institutions</span>
    <span class="report-stat-val">{total_institutions}</span>
  </div>
  <div class="report-stat-card">
    <span class="report-stat-label">Official portals</span>
    <span class="report-stat-val">{total_sources}</span>
  </div>
  <div class="report-stat-card">
    <span class="report-stat-label">Scheduled scan</span>
    <span class="report-stat-val">21:00 IST</span>
  </div>
</div>

<div class="admission-watch">
<h2>About this live monitor</h2>
<p>The daily checker runs at <strong>21:00 Asia/Kolkata (15:30 UTC)</strong> every day.
It scans the official HTML pages listed below for changes in notice headlines, application links, and date announcements.</p>
<p><strong>Conservative detection rules:</strong></p>
<ul>
<li><strong>Notice detector, not registration confirmation:</strong> This monitor flags changed evidence for manual review. It never automatically marks an exam or school as open or closed.</li>
<li><strong>Dates are unverified mentions:</strong> Any dates shown below are extracted from readable HTML text. They are evidence to inspect, not confirmed registration or exam deadlines.</li>
<li><strong>PDF and portal limits:</strong> Scanned circulars, PDFs, and JavaScript-based application portals cannot be parsed by the automated crawler. An unchanged page or fetch failure does not mean admissions have not started. Always inspect the linked official portal.</li>
</ul>
<p class="hint">Last report generated: <strong>{esc(checked_at)}</strong> &middot; {status_line}</p>
</div>

{"".join(group_sections)}

<div class="btnrow" style="margin: 32px 0;">
  <a class="btn primary" href="index.html">&larr; Return to admissions directory</a>
  <a class="btn" href="#main" onclick="scrollTo({{top:0,behavior:'smooth'}})">Top of report &uarr;</a>
</div>
'''
