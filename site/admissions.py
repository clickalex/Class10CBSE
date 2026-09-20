"""Render the grouped after-Class-10 admissions and scholarship directory."""
import html
import json
from pathlib import Path

GROUPS = (
    ('school', 'Class XI / intermediate schools', 'Entrance-test and merit/vacancy routes are labelled separately. Check eligibility before applying.'),
    ('diploma', 'Diploma / polytechnic colleges', 'An alternative to Class XI–XII, not a school stream. Verify course recognition, progression options, domicile and branch-specific eligibility.'),
    ('scholarship', 'Scholarship exams for Class 10 students', 'These are private coaching scholarship tests, not government cash scholarships or school admissions. Compare remaining fees, validity and award conditions; an “up to” award is not guaranteed.'),
)


def admissions_body():
    data = json.loads((Path(__file__).parent / 'content/admissions.json').read_text())
    esc = html.escape
    groups = {key: [] for key, _, _ in GROUPS}
    for inst in data['institutions']:
        links = ' · '.join(f'<a href="{esc(url, quote=True)}">Official source {i}</a>'
                           for i, url in enumerate(inst['sources'], 1))
        category = inst.get('category', 'school')
        selection = inst.get('selection', 'test')
        mode = {'test': 'Test-based route', 'merit': 'Merit / vacancy route — no general entrance test',
                'verify': 'Selection process: verify current notice'}[selection]
        date = 'Not applicable: merit / vacancy route' if selection == 'merit' else 'Not confirmed here — verify the current cycle'
        extra = '<p><a href="../pw-nsat/index.html">PW NSAT detailed guide &amp; dated exam snapshot</a></p>' if inst['id'] == 'pw-nsat' else ''
        groups[category].append(f'''<article class="admission-card" id="{esc(inst['id'])}">
<p class="kicker">{esc(inst['location'])}</p>
<h3>{esc(inst['name'])}</h3>
<p><strong>{esc(mode)}</strong></p><p>{esc(inst['route'])}</p>
<p><strong>Before applying:</strong> {esc(inst['eligibility'])}</p>
<dl class="admission-dates">
<dt>Cycle to check</dt><dd>{esc(inst.get('cycle', data['target_session']))}</dd>
<dt>Registration</dt><dd>Unverified — read the latest daily report and official notice</dd>
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
The live report lives on GitHub, so you do not need to keep this page open.</p>
<p><a class="btn" href="https://github.com/clickalex/Class10CBSE/issues?q=is%3Aissue+is%3Aopen+in%3Atitle+%22daily+admission+watch%22">Open latest daily report</a>
<a class="btn" href="https://github.com/clickalex/Class10CBSE/actions">Check runs &amp; download reports</a></p>
<p><strong>Setup required:</strong> the workflow is currently an inactive template in
<a href="https://github.com/clickalex/Class10CBSE/tree/main/temporary-workflows">temporary-workflows</a>.
Manually copy it to <code>.github/workflows/admission-watch.yml</code> on the default branch and enable GitHub Actions before scheduled checks run.
Merging the template alone does not activate the scheduler.
GitHub may delay a run. The first completed run creates the report issue; use its timestamp to check freshness.
Subscribe to that issue for notice-change and fetch-health alerts, subject to your GitHub notification settings.</p>
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
<li>Read the daily report, then verify any application opening, closing date, extension or exam date on the official website.</li>
<li>Record verified deadlines in your calendar with reminders seven days and two days before them. Apply early and save receipts privately.</li>
</ol>
<h2>Documents &amp; preparation</h2>
<p>Prepare Class X marks/results when available, date-of-birth proof, photographs, signatures and applicable category/residence certificates.
Upload documents only on the official application portal. Check whether appearing candidates may apply before results.</p>
<p>Revise Class X subjects, then follow each test's own syllabus and official sample/past papers where available.
These options do not guarantee admission or an award. School, diploma and coaching fees are separate.</p>
<p><a href="https://github.com/clickalex/Class10CBSE/tree/main/09-After-10th">Open the after-10th folder &amp; tracker instructions</a></p>
'''
