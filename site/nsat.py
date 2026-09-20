"""PW NSAT resource page; dated official-page snapshot, not a live status feed."""
import html
import json
from pathlib import Path


def nsat_body():
    data = json.loads((Path(__file__).parent / 'content/pw-nsat.json').read_text())
    esc = html.escape
    url = esc(data['official_url'], quote=True)
    rows = ''.join(f'<dt>{esc(label)}</dt><dd>{esc(value)}</dd>' for label, value in data['details'])
    return f'''
<p class="kicker">SCHOLARSHIP &amp; COACHING · {esc(data['exam_cycle'])}</p>
<h1>{esc(data['title'])}</h1>
<p class="lede">{esc(data['full_name'])}</p>
<p>{esc(data['summary'])}</p>
<p><a class="btn" href="{url}">Open official PW NSAT website / registration</a></p>
<div class="admission-watch">
<h2>Official-page snapshot</h2>
<p><strong>Checked on {esc(data['checked_on'])}.</strong> These details are a dated summary, not a live registration tracker.
Dates, available slots and terms may change. Recheck the official page before applying or making travel plans.</p>
<dl class="admission-dates">{rows}</dl>
<p>Source: <a href="{url}">PW NSAT official page and FAQ</a>.</p>
</div>
<h2>For a Class 10 student</h2>
<ol>
<li>Open the official page and select your <strong>current class: Class 10</strong>. Confirm the course and next-session eligibility.</li>
<li>Use <strong>View Syllabus</strong> on PW's page and select Class 10. Do not assume the NSAT syllabus is identical to the CBSE board syllabus.</li>
<li>Choose online or offline mode and confirm the date, centre and slot. Submit personal details only on the official portal.</li>
<li>Save your confirmation and instructions privately. Keep application details, passwords and identity documents safe and confidential.</li>
<li>Check scholarship conditions and the remaining course fees before accepting an offer. A coaching scholarship is not a school admission.</li>
</ol>
<h2>Preparation &amp; study resources</h2>
<p>Revise relevant topics using the <a href="../maths/index.html">Mathematics</a> and
<a href="../science/index.html">Science</a> hubs, guided by PW's Class 10 syllabus.
Practise timed questions, review mistakes and use official sample material where available.</p>
<p><a class="btn" href="../mock-test/pw-nsat/index.html">Take an NSAT-pattern mock test (40 questions, 60 minutes) and check your score →</a>
<br><span class="hint">Built from this site's own Physics, Chemistry, Mathematics, Biology and Mental Ability banks — not a PW paper.</span></p>
<p>Review syllabus notes, practice questions, and registration checklists before applying. Keep downloaded PDFs and personal records stored privately.</p>
<h2>Looking for Class XI school entrance exams?</h2>
<p>Visit <a href="../after-10th/index.html">After 10th admissions</a> for JMI, AMU, BHU/CHS and other options.
PW NSAT is also included in the daily 9 PM IST admission and scholarship checker; its report flags notices for manual verification.</p>
'''
