"""Direct downloads: official CBSE papers and this hub's own question banks.

Two kinds of download, kept honest about who owns the file:

  * Official CBSE material - previous-year board papers, sample papers with
    marking schemes, the CBSE question bank and its additional practice
    questions - is LINKED, never copied. site/content/downloads.json holds the
    exact file URLs, copied from CBSE's own listing pages on the date it
    records, so a button goes straight to the PDF/ZIP instead of to a listing.
    scripts/check_downloads.py re-checks every URL against the live servers.
  * This hub's own question bank is generated at build time from the chapter
    JSON: one plain-text file per subject and per chapter (written Q&A and
    MCQs, answers included). Pages that hold questions also save cleanly as a
    PDF through the browser's print dialog (see theme/js/print.js).

Why plain text and not PDF/ZIP/DOCX: .gitignore keeps *.pdf and *.zip out of
the repository (docs/ included); a stdlib-only PDF writer cannot shape
Devanagari; and a compressed .docx is not byte-stable across zlib builds,
which would break the docs/ drift check. Text is small, opens everywhere and
rebuilds byte-for-byte.

Pure standard library. No timestamps, no randomness, sorted iteration: a
rebuild of unchanged content is byte-identical.
"""
from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import layout
from layout import CREDIT, SESSION, SITE_URL, href_to

SITE = Path(__file__).resolve().parent
CONTENT = SITE / "content"

# The only places an official file may live. A typo or a hijacked link to any
# other host fails the build instead of reaching a student's phone.
ALLOWED_HOSTS = ("www.cbse.gov.in", "cbseacademic.nic.in")
FILE_TYPES = {".pdf": "PDF", ".zip": "ZIP"}
_SIZE_RE = re.compile(r"^\d+(\.\d+)? (KB|MB)$")

# Set by configure(): the parsed manifest and {relative path: byte size} of the
# generated text files, so every page can show real sizes.
_STATE: dict = {"data": None, "sizes": {}}


# --------------------------------------------------------------------------
# manifest: load, enumerate, validate
# --------------------------------------------------------------------------
def load(path=None):
    with open(path or CONTENT / "downloads.json", encoding="utf-8") as fh:
        return json.load(fh)


def configure(data, exports):
    """Publish the manifest and the generated files' sizes for this build."""
    _STATE["data"] = data
    _STATE["sizes"] = {rel: len(text.encode("utf-8")) for rel, text in exports.items()}


def _data():
    if _STATE["data"] is None:
        raise RuntimeError("downloads.configure() has not run; build.build() calls it")
    return _STATE["data"]


def file_urls(data):
    """Every official file the manifest names, as sorted (description, url)."""
    found = []
    for slug, entry in data["subjects"].items():
        for course in entry["courses"]:
            tag = f"{slug}/{course['id']}"
            for sitting, f in course["pyq"].items():
                found.append((f"{tag} pyq {sitting}", f["url"]))
            for session, f in course["sqp"].items():
                found.append((f"{tag} sqp {session}", f["sqp"]))
                found.append((f"{tag} ms {session}", f["ms"]))
        for q in entry.get("qb", []):
            found.append((f"{slug} question bank: {q['label']}", q["url"]))
        for a in entry.get("apq", []):
            found.append((f"{slug} practice questions {a['session']}: {a['label']}", a["pq"]))
            if a.get("ms"):   # the 2021-22 sets were published without a marking scheme
                found.append((f"{slug} practice questions MS {a['session']}: {a['label']}", a["ms"]))
    return sorted(found)


LIST_KEYS = ("pyq", "sqp", "skill_sqp", "skill_sqp_archive", "qb", "apq", "cbe")


def list_urls(data):
    """CBSE's own listing pages the file URLs were copied from."""
    lists = data["lists"]
    found = [(f"list {key}", lists[key]["url"]) for key in LIST_KEYS]
    found += [(f"list sqp {x['label']}", x["url"]) for x in lists["sqp_older"]]
    return sorted(found)


def _url_problem(url):
    """Why a URL may not be linked, or None."""
    if not isinstance(url, str) or not url:
        return "is empty"
    if re.search(r"[\s\"'<>\\]", url):
        return "contains whitespace, a quote or an angle bracket"
    parts = urlparse(url)
    if parts.scheme != "https":
        return "is not https"
    if parts.netloc not in ALLOWED_HOSTS:
        return f"host {parts.netloc!r} is not one of {ALLOWED_HOSTS}"
    return None


def validate(data, subject_slugs):
    """Return a list of problems with the manifest (empty list = fine)."""
    bad = []
    if data.get("version") != 1:
        bad.append("version must be 1")
    try:
        checked = date.fromisoformat(data.get("checked_on", ""))
    except ValueError:
        checked = None
        bad.append("checked_on must be an ISO date (YYYY-MM-DD)")
    if "first_checked_on" in data:
        try:
            first = date.fromisoformat(data["first_checked_on"])
            if checked and first > checked:
                bad.append("first_checked_on cannot be later than checked_on")
        except (TypeError, ValueError):
            bad.append("first_checked_on must be an ISO date (YYYY-MM-DD)")

    for key in LIST_KEYS:
        entry = data.get("lists", {}).get(key)
        if not entry or not entry.get("label"):
            bad.append(f"lists.{key} needs a label and a url")
        elif _url_problem(entry.get("url")):
            bad.append(f"lists.{key}.url {_url_problem(entry.get('url'))}")
    for item in data.get("lists", {}).get("sqp_older", []):
        if _url_problem(item.get("url")):
            bad.append(f"lists.sqp_older {item.get('label')}: {_url_problem(item.get('url'))}")

    sittings = [s["id"] for s in data.get("sittings", [])]
    sessions = [s["id"] for s in data.get("sessions", [])]
    for name, ids in (("sittings", sittings), ("sessions", sessions)):
        if not ids or len(ids) != len(set(ids)):
            bad.append(f"{name} must be non-empty with unique ids")

    subjects = data.get("subjects", {})
    for slug in sorted(set(subject_slugs) - set(subjects)):
        bad.append(f"subject {slug!r} has no entry in downloads.json")
    for slug in sorted(set(subjects) - set(subject_slugs)):
        bad.append(f"downloads.json names unknown subject {slug!r}")

    for slug, entry in subjects.items():
        courses = entry.get("courses") or []
        if not courses:
            bad.append(f"{slug}: needs at least one course")
        if len({c.get("id") for c in courses}) != len(courses):
            bad.append(f"{slug}: course ids must be unique")
        for course in courses:
            tag = f"{slug}/{course.get('id')}"
            if not course.get("label"):
                bad.append(f"{tag}: missing label")
            if not course.get("pyq"):
                bad.append(f"{tag}: no previous-year papers")
            for sitting, f in course.get("pyq", {}).items():
                if sitting not in sittings:
                    bad.append(f"{tag}: unknown sitting {sitting!r}")
                if _url_problem(f.get("url")):
                    bad.append(f"{tag} pyq {sitting}: {_url_problem(f.get('url'))}")
                if not str(f.get("url", "")).lower().endswith(tuple(FILE_TYPES)):
                    bad.append(f"{tag} pyq {sitting}: not a .pdf or .zip file")
                if f.get("size") and not _SIZE_RE.match(f["size"]):
                    bad.append(f"{tag} pyq {sitting}: size {f['size']!r} is not like '58.9 MB'")
            for session, f in course.get("sqp", {}).items():
                if session not in sessions:
                    bad.append(f"{tag}: unknown session {session!r}")
                for part in ("sqp", "ms"):
                    problem = _url_problem(f.get(part))
                    if problem:
                        bad.append(f"{tag} {part} {session}: {problem}")
                    elif not f[part].lower().endswith(".pdf"):
                        bad.append(f"{tag} {part} {session}: not a .pdf file")
        for q in entry.get("qb", []):
            if _url_problem(q.get("url")) or not q.get("label"):
                bad.append(f"{slug} qb {q.get('label')}: {_url_problem(q.get('url')) or 'no label'}")
        for a in entry.get("apq", []):
            if not a.get("session") or not a.get("label"):
                bad.append(f"{slug} apq {a.get('label')}: needs a session and a label")
            # the question file is required; the marking scheme only when CBSE published one
            for part in ("pq", "ms"):
                if part == "ms" and not a.get("ms"):
                    continue
                if _url_problem(a.get(part)):
                    bad.append(f"{slug} apq {a.get('label')} {part}: {_url_problem(a.get(part))}")
    return bad


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def _e(text):
    return html.escape(str(text), quote=True)


def _nice_date(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')} {d.year}"


def _checked(data):
    """When the addresses were copied: '3 Oct 2026', or '2\u20133 Oct 2026' when it took two days."""
    last = date.fromisoformat(data["checked_on"])
    first = date.fromisoformat(data.get("first_checked_on") or data["checked_on"])
    if first == last:
        return _nice_date(data["checked_on"])
    if (first.year, first.month) == (last.year, last.month):
        return f"{first.day}\u2013{last.day} {last.strftime('%b')} {last.year}"
    return f"{_nice_date(first.isoformat())} \u2013 {_nice_date(last.isoformat())}"


def _years(data):
    """'2024\u20132026' from the sittings the manifest actually lists."""
    years = sorted({sitting["id"][:4] for sitting in data["sittings"]})
    return years[0] if len(years) == 1 else f"{years[0]}\u2013{years[-1]}"


def _kind(url):
    suffix = Path(urlparse(url).path).suffix.lower()
    return FILE_TYPES.get(suffix, suffix.lstrip(".").upper() or "FILE")


def _file_link(url, label, name):
    """A button to an official file; `name` is read out by screen readers."""
    return (f'<a class="btn dl-btn" href="{_e(url)}" target="_blank" rel="noopener noreferrer">'
            f'<span class="sr-only">Download {_e(name)}: </span>{_e(label)}</a>')


def _text_link(url, label):
    return f'<a href="{_e(url)}" target="_blank" rel="noopener noreferrer">{_e(label)}</a>'


def _size(nbytes):
    kb = nbytes / 1024
    return f"{kb:.0f} KB" if kb < 1000 else f"{kb / 1024:.1f} MB"


# --------------------------------------------------------------------------
# official files: previous-year papers, sample papers, question banks
# --------------------------------------------------------------------------
def pyq_table(data, slug, title):
    """Rows = exam sittings, columns = the subject's courses."""
    courses = data["subjects"][slug]["courses"]
    head = "".join(f'<th scope="col">{_e(c["label"])}</th>' for c in courses)
    rows = []
    for sitting in data["sittings"]:
        cells, i = [], 0
        while i < len(courses):
            f = courses[i]["pyq"].get(sitting["id"])
            if f is None:
                cells.append('<td><span class="dl-none">Not listed by CBSE</span></td>')
                i += 1
                continue
            # Courses that share one file (Maths 2026: a single ZIP holds both
            # papers) get one merged cell instead of two identical buttons.
            span = 1
            while (i + span < len(courses)
                   and courses[i + span]["pyq"].get(sitting["id"], {}).get("url") == f["url"]):
                span += 1
            who = " + ".join(c["label"] for c in courses[i:i + span])
            label = _kind(f["url"]) + (f" \u00b7 {f['size']}" if f.get("size") else "")
            link = _file_link(f["url"], label, f"{title} {who}, {sitting['title']}")
            if span > 1:
                cells.append(f'<td colspan="{span}">{link} '
                             f'<span class="dl-meta">one file covers {_e(who)}</span></td>')
            else:
                cells.append(f"<td>{link}</td>")
            i += span
        rows.append(f'<tr><th scope="row">{_e(sitting["label"])} '
                    f'<span class="dl-sub">{_e(sitting["title"])}</span></th>{"".join(cells)}</tr>')
    return (f'<div class="tablewrap"><table class="dl-table">'
            f'<thead><tr><th scope="col">Exam</th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def sqp_table(data, slug, title):
    """Rows = sample-paper sessions, columns = courses, SQP + marking scheme."""
    courses = data["subjects"][slug]["courses"]
    head = "".join(f'<th scope="col">{_e(c["label"])}</th>' for c in courses)
    rows = []
    for session in data["sessions"]:
        if not any(session["id"] in c["sqp"] for c in courses):
            continue
        cells = []
        for c in courses:
            f = c["sqp"].get(session["id"])
            if f is None:
                cells.append('<td><span class="dl-none">Not listed by CBSE</span></td>')
                continue
            cells.append("<td>"
                         + _file_link(f["sqp"], "Sample paper", f"{title} {c['label']} sample paper {session['label']}")
                         + _file_link(f["ms"], "Marking scheme", f"{title} {c['label']} marking scheme {session['label']}")
                         + "</td>")
        rows.append(f'<tr><th scope="row">{_e(session["label"])} '
                    f'<span class="dl-sub">Class X session</span></th>{"".join(cells)}</tr>')
    return (f'<div class="tablewrap"><table class="dl-table">'
            f'<thead><tr><th scope="col">Session</th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def pyq_blocks(data, slug, title, h=3):
    """The board-paper and sample-paper tables for one subject."""
    lists = data["lists"]
    shown = {s["label"] for s in data["sessions"]}
    older = [x for x in lists["sqp_older"] if x["label"] not in shown]
    more = " \u00b7 ".join(_text_link(x["url"], x["label"]) for x in older)
    if slug == "information-technology":
        # a skill subject: CBSE lists its sample papers on a separate page and archive
        current = _text_link(lists["skill_sqp"]["url"], lists["skill_sqp"]["label"])
        archive = _text_link(lists["skill_sqp_archive"]["url"], "archive")
        sessions = f"Current list: {current}. Older sessions: the {archive}."
    else:
        current = _text_link(lists["sqp"]["url"], lists["sqp"]["label"])
        sessions = f"Current list: {current}. More sessions: {more}."
    return f"""
<h{h}>Board question papers</h{h}>
<p class="hint">Class X board papers {_years(data)}, as CBSE published them. A ZIP holds every
set of that paper; any unzip app opens it. Sizes are as listed by CBSE. Full list:
{_text_link(lists["pyq"]["url"], lists["pyq"]["label"])}.</p>
{pyq_table(data, slug, title)}
<h{h}>Sample papers &amp; marking schemes</h{h}>
<p class="hint">A sample paper (SQP) shows the paper design CBSE sets for the session; the marking scheme (MS) shows how
answers are marked. {sessions}</p>
{sqp_table(data, slug, title)}
"""


def pyq_panel(slug, title):
    """The 'Direct downloads' block that opens a subject's PYQ page."""
    data = _data()
    return f"""<section class="dl" id="downloads">
<h2>Direct downloads \u2014 official CBSE papers</h2>
<p class="hint">Every button opens the file on CBSE\u2019s own website ({" or ".join(ALLOWED_HOSTS)}). Nothing is
copied to this site, so you always get the official version. Every address was copied from
CBSE\u2019s own listing pages on {_checked(data)}; if a link ever fails, use the official list named beside it.</p>
{pyq_blocks(data, slug, title, 3)}</section>
"""


def official_bank_card(data, slug, title, h=3):
    """CBSE's own question bank / practice questions for this subject."""
    entry = data["subjects"][slug]
    lists = data["lists"]
    items = [f'<li>{_text_link(q["url"], q["label"])} <span class="dl-meta">PDF</span></li>'
             for q in entry.get("qb", [])]
    for a in entry.get("apq", []):
        session = a["session"].replace("-", "\u2013")
        links = _text_link(a["pq"], "questions")
        if a.get("ms"):
            links += " \u00b7 " + _text_link(a["ms"], "marking scheme")
        items.append(f'<li>Practice questions {_e(session)} \u00b7 {_e(a["label"])}: {links} '
                     f'<span class="dl-meta">PDF</span></li>')
    if items:
        body = f'<ul class="dl-list">{"".join(items)}</ul>'
    else:
        body = (f"<p>CBSE has not published a Class X question bank or practice-question PDF for "
                f"{_e(title)}. The sample papers above are its official practice material.</p>")
    return (f'<div class="dl-card"><h{h}>Official CBSE question bank</h{h}>{body}'
            f'<p class="hint">Official lists: {_text_link(lists["qb"]["url"], "question bank")} \u00b7 '
            f'{_text_link(lists["apq"]["url"], "additional practice questions")} \u00b7 '
            f'{_text_link(lists["cbe"]["url"], "competency-based items")}.</p></div>')


# --------------------------------------------------------------------------
# this hub's own question bank: text files + PDF through print
# --------------------------------------------------------------------------
def export_name(slug, chapter_id=None):
    """File name, descriptive on purpose: students save and share these."""
    if chapter_id:
        return f"class10-{slug}-{chapter_id}.txt"
    return f"class10-{slug}-question-bank.txt"


def export_href(root, slug, chapter_id=None):
    return href_to(root, f"downloads/{slug}/{export_name(slug, chapter_id)}")


def _export_size(slug, chapter_id=None):
    size = _STATE["sizes"].get(f"{slug}/{export_name(slug, chapter_id)}")
    return _size(size) if size else ""


def _pdf_buttons(scope=None):
    extra = f' data-scope="{_e(scope)}"' if scope else ""
    return (f'<button type="button" class="btn primary dl-btn" data-save-pdf="answers"{extra}>PDF \u00b7 with answers</button>'
            f'<button type="button" class="btn dl-btn" data-save-pdf="questions"{extra}>PDF \u00b7 questions only</button>')


def own_bank_card(slug, title, n_qa, n_mcq, n_chapters, root, on_page, h=3):
    """The hub's own bank. `on_page`: the page being shown IS the bank, so the
    PDF buttons can print it; elsewhere the card links to the pages that do."""
    txt = (f'<a class="btn dl-btn" href="{export_href(root, slug)}" download>'
           f'Text \u00b7 {_export_size(slug)}</a>')
    if on_page:
        buttons = _pdf_buttons() + txt
        tip = ('<p class="hint">PDF opens your browser\u2019s print dialog \u2014 choose <strong>Save as PDF</strong>. '
               "The filters below apply, so you can save just the Short or Long questions.</p>")
    else:
        buttons = (txt + f'<a class="btn" href="{href_to(root, f"{slug}/question-bank.html#downloads")}">'
                   "Written Q&amp;A \u2192 PDF</a>"
                   f'<a class="btn" href="{href_to(root, f"{slug}/drill.html#downloads")}">MCQs \u2192 PDF</a>')
        tip = ""
    return (f'<div class="dl-card"><h{h}>This hub\u2019s question bank</h{h}>'
            f"<p>{n_qa} written Q&amp;As and {n_mcq} MCQs across {n_chapters} chapters, answers included. "
            f"Original practice material \u2014 not official CBSE papers.</p>"
            f'<p class="btnrow">{buttons}</p>{tip}</div>')


def qbank_panel(subj, chapters, root=".."):
    """The 'Download this question bank' block at the top of the bank page."""
    data = _data()
    slug = subj["slug"]
    n_qa = sum(len(c.get("qa") or []) for c in chapters)
    n_mcq = sum(len(c.get("mcq") or []) for c in chapters)
    return f"""<section class="dl no-print" id="downloads">
<h2>Download this question bank</h2>
<div class="dl-grid">
{own_bank_card(slug, subj["title"], n_qa, n_mcq, len(chapters), root, on_page=True)}
{official_bank_card(data, slug, subj["title"])}
</div>
</section>
"""


def chapter_row(slug, chapter, root=".."):
    """Per-chapter links under each heading on the bank page."""
    name = _e(f"Ch {chapter['num']} \u00b7 {chapter['title']}")
    return (f'<p class="dl-row no-print">Save this chapter: '
            f'<a href="{export_href(root, slug, chapter["id"])}" download aria-label="Text (.txt) \u2014 {name}">Text (.txt)</a> \u00b7 '
            f'<button type="button" class="linkbtn" data-save-pdf="answers" '
            f'data-scope="{_e(chapter["id"])}" aria-label="PDF \u2014 {name}">PDF</button></p>')


def drill_row(slug, root=".."):
    return (f'<section class="dl no-print" id="downloads"><p class="dl-row">Save the MCQs: '
            f'<button type="button" class="linkbtn" data-save-pdf="answers">PDF with answers</button> \u00b7 '
            f'<button type="button" class="linkbtn" data-save-pdf="questions">PDF questions only</button> \u00b7 '
            f'<a href="{export_href(root, slug)}" download>Text (.txt) \u2014 written Q&amp;A + MCQs</a></p></section>')


def practice_row(slug, chapter, root="../.."):
    return (f'<p class="dl-row no-print">Save this chapter: '
            f'<button type="button" class="linkbtn" data-save-pdf="answers">PDF with answers</button> \u00b7 '
            f'<button type="button" class="linkbtn" data-save-pdf="questions">PDF questions only</button> \u00b7 '
            f'<a href="{export_href(root, slug, chapter["id"])}" download>Text (.txt)</a></p>')


# --------------------------------------------------------------------------
# plain-text export of the chapter question banks
# --------------------------------------------------------------------------
_BOLD = re.compile(r"\*\*(.+?)\*\*(?!\*)")
_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_CODE = re.compile(r"`(.+?)`")
RULE = "=" * 72
THIN = "-" * 72
BOM = "\ufeff"   # so old Windows Notepad reads the Devanagari files as UTF-8


def plain(text):
    """The site's inline markup as plain text - the same rules as build.inline()."""
    s = _BOLD.sub(r"\1", str(text))
    s = _ITALIC.sub(r"\1", s)
    return _CODE.sub(r"\1", s)


def _block_lines(items):
    """An answer (strings, bullet/numbered lines, tables) as text lines."""
    lines = []
    for item in items:
        if isinstance(item, dict) and item.get("table"):
            t = item["table"]
            head = [plain(c) for c in t.get("head", [])]
            if head:
                lines.append(" | ".join(head))
                lines.append(" | ".join("-" * max(3, len(h)) for h in head))
            for row in t.get("rows", []):
                lines.append(" | ".join(plain(c) for c in row))
            continue
        s = str(item).strip()
        if not s:
            continue
        if s.startswith("- "):
            lines.append("\u2022 " + plain(s[2:]))
        else:
            lines.append(plain(s))
    return lines


def _question_lines(prefix, text):
    first, *rest = plain(text).split("\n")
    # Keep blank lines between the prompt and its subquestions blank. Indenting an
    # empty line produces trailing spaces in the downloadable .txt export.
    return [prefix + first] + [("    " + line) if line else "" for line in rest]


def _answer_lines(answer):
    body = _block_lines(answer if isinstance(answer, list) else [answer])
    if len(body) == 1:
        return ["    Ans: " + body[0]]
    return ["    Ans:"] + ["      " + line for line in body]


def render_text(subj, chapters, type_label, whole):
    """One .txt file: a whole subject's bank (`whole`) or a single chapter's."""
    n_qa = sum(len(c.get("qa") or []) for c in chapters)
    n_mcq = sum(len(c.get("mcq") or []) for c in chapters)
    scope = ("Question bank" if whole
             else f"Chapter {chapters[0]['num']} \u00b7 {chapters[0]['title']}")
    lines = [
        f"CLASS 10 CBSE \u00b7 {subj['title'].upper()} (Subject Code {subj['code']})",
        f"{scope} \u00b7 session {SESSION}",
        "",
        f"{len(chapters)} chapter{'s' if len(chapters) != 1 else ''} \u00b7 {n_qa} written Q&A \u00b7 {n_mcq} MCQs. "
        "The answer follows each question.",
        "Original practice material for revision \u2014 not official CBSE papers.",
        f"Online: {SITE_URL}/{subj['slug']}/question-bank.html",
        f"Created by {CREDIT}",
        "",
    ]
    for ch in chapters:
        lines += [RULE, f"CHAPTER {ch['num']} \u00b7 {ch['title']}"]
        if ch.get("unit_name"):
            lines.append(f"Unit: {ch['unit_name']}")
        lines += [RULE, ""]
        qa = ch.get("qa") or []
        if qa:
            lines += [f"A. WRITTEN QUESTIONS ({len(qa)})", THIN, ""]
            for i, q in enumerate(qa, 1):
                marks = str(q.get("m", "2"))
                tag = f"[{type_label(q)} \u00b7 {marks} mark{'s' if marks != '1' else ''}] "
                lines += _question_lines(f"Q{i}. {tag}", q["q"]) + _answer_lines(q["a"]) + [""]
        mcq = ch.get("mcq") or []
        if mcq:
            lines += [f"B. MCQs ({len(mcq)})", THIN, ""]
            for i, q in enumerate(mcq, 1):
                lines += _question_lines(f"M{i}. ", q["q"]) + _answer_lines(q["a"]) + [""]
    return BOM + "\n".join(lines).rstrip("\n") + "\n"


def export_files(subjects, chapters_by_slug, type_label):
    """{path under downloads/: text} for every subject that has chapters."""
    files = {}
    for subj in subjects:
        chapters = chapters_by_slug.get(subj["slug"])
        if not chapters:
            continue
        slug = subj["slug"]
        files[f"{slug}/{export_name(slug)}"] = render_text(subj, chapters, type_label, True)
        for ch in chapters:
            files[f"{slug}/{export_name(slug, ch['id'])}"] = render_text(subj, [ch], type_label, False)
    return files


# --------------------------------------------------------------------------
# the Downloads page
# --------------------------------------------------------------------------
def hub_body(subjects, chapters_by_slug):
    data = _data()
    live = [s for s in subjects if chapters_by_slug.get(s["slug"])]
    chips = layout.chip_row(" ".join(layout.chip(f"#{s['slug']}", s["title"]) for s in live))
    sections = []
    for subj in live:
        slug, title = subj["slug"], subj["title"]
        chapters = chapters_by_slug[slug]
        n_qa = sum(len(c.get("qa") or []) for c in chapters)
        n_mcq = sum(len(c.get("mcq") or []) for c in chapters)
        sections.append(f"""<section class="dl" id="{_e(slug)}">
<h2>{_e(title)}</h2>
<p class="hint">Subject code {_e(subj["code"])} \u00b7 <a href="../{slug}/pyq.html">PYQ page &amp; chapter trends</a> \u00b7
<a href="../{slug}/question-bank.html">Question bank</a> \u00b7 <a href="../{slug}/drill.html">MCQ drill</a></p>
{pyq_blocks(data, slug, title, 3)}
<h3>Question banks</h3>
<div class="dl-grid">
{own_bank_card(slug, title, n_qa, n_mcq, len(chapters), "..", on_page=False, h=4)}
{official_bank_card(data, slug, title, 4)}
</div>
</section>""")
    note = layout.callout(
        "Official files stay on CBSE\u2019s servers: every button opens the file on cbse.gov.in or "
        "cbseacademic.nic.in, so you always get the current official copy. Addresses were copied from "
        "CBSE\u2019s own listing pages on " + _checked(data) + ". This hub\u2019s own questions are original practice "
        "material, <strong>not</strong> official CBSE papers.")
    body = f"""
<p class="kicker">DIRECT DOWNLOADS \u00b7 CLASS 10 CBSE \u00b7 SESSION {SESSION}</p>
<h1>Previous-year papers &amp; question banks</h1>
<p class="lede">One tap to the file. Pick a subject for CBSE\u2019s own board papers ({_years(data)}), sample papers with
marking schemes and the CBSE question bank \u2014 plus this hub\u2019s own question bank as a PDF or text file.</p>
{note}
{chips}
{"".join(sections)}
"""
    return [("Home", "../index.html"), ("Downloads", None)], body
