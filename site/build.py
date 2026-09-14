#!/usr/bin/env python3
"""Build the Class 10 CBSE study-hub site.

Reads JSON content from site/content/ and writes a complete static site into
docs/, mirroring the architecture of the IT-402 hub: a portal page, one hub per
subject, unit overviews, deep chapter pages, syllabus, revision, question bank
and PYQ pages.

docs/ is the GitHub Pages publishing folder (Settings -> Pages -> main /docs),
so the build writes straight into the directory the live site is served from.

    python3 site/build.py                 # build into docs/
    python3 site/build.py --check         # build, then validate links + content
    python3 site/build.py --out /tmp/x    # build somewhere else (CI)
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
REPO = SITE.parent
CONTENT = SITE / "content"
THEME = SITE / "theme"

# GitHub Pages for this repository publishes github.com/clickalex/Class10CBSE
# from the /docs folder of the default branch, so that is where the build goes.
DIST = REPO / "docs"

# Absolute path the site is served under, used only by the 404 page (GitHub
# Pages serves that one file for every unknown URL, so its links cannot be
# relative to the requested path).
BASE = "/Class10CBSE"

SESSION = "2026\u201327"


# --------------------------------------------------------------------------
# tiny markup renderer (bold / italic / code / lists / tables)
# --------------------------------------------------------------------------
def inline(text: str) -> str:
    text = html.escape(str(text), quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def blocks(items) -> str:
    """Render a list of strings/tables/dicts into HTML blocks."""
    out, para, ul, ol = [], [], [], []

    def flush():
        if para:
            out.append("<p>" + "<br>".join(inline(p) for p in para) + "</p>")
            para.clear()
        if ul:
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in ul) + "</ul>")
            ul.clear()
        if ol:
            out.append("<ol>" + "".join(f"<li>{inline(i)}</li>" for i in ol) + "</ol>")
            ol.clear()

    for item in items or []:
        if isinstance(item, dict) and item.get("table"):
            flush()
            t = item["table"]
            head = "".join(f"<th>{inline(c)}</th>" for c in t.get("head", []))
            rows = "".join(
                "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                for r in t.get("rows", [])
            )
            cls = f' class="{html.escape(item["class"])}"' if item.get("class") else ""
            out.append(
                f'<div class="tablewrap"><table{cls}>'
                f"<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>"
            )
            continue
        s = str(item).strip()
        if not s:
            flush()
            continue
        if s.startswith("- "):
            ul.append(s[2:])
        elif re.match(r"^\d+[.)] ", s):
            ol.append(re.sub(r"^\d+[.)] ", "", s))
        else:
            para.append(s)
    flush()
    return "\n".join(out)


# --------------------------------------------------------------------------
# page shell: sidebar navigation (drawer) + credit footer
# --------------------------------------------------------------------------
# The pages every subject hub owns, in the order they are meant to be used.
# `key` is what a page passes as `active=` so the sidebar can show where you are.
SECTIONS = (
    ("hub", "Hub", "index.html"),
    ("chapters", "Chapters", "chapters.html"),
    ("syllabus", "Syllabus", "syllabus.html"),
    ("bank", "Q&A bank", "question-bank.html"),
    ("drill", "MCQ drill", "drill.html"),
    ("revision", "Revision", "revision.html"),
    ("pyq", "PYQ", "pyq.html"),
    ("practical", "Practical", "practical.html"),
)

CREDIT = "Mohammad Umair"

# Filled in by build() so every page can render the same subject switcher.
NAV_SUBJECTS: list = []
NAV_PENDING: set = set()


def href_to(root, path):
    """A link that works from any page depth."""
    return path if root == "." else f"{root}/{path}"


def sidebar(root, subject=None, active=None, chapters=None, chapter_id=None):
    """The navigation drawer: all subjects, then this subject's pages and chapters.

    Modelled on the AI-Course book sidebar - a grouped table of contents that
    is always on screen on a desktop and slides in behind a ☰ button on a phone.
    """
    home = href_to(root, "index.html")
    bits = [
        '<div class="side-head">'
        f'<a class="brand" href="{home}">Class&nbsp;10&nbsp;<span>CBSE</span></a>'
        f'<p class="side-sub">Session {SESSION}</p>'
        '<button class="side-close" onclick="closeMenu()" aria-label="Close navigation">&times;</button>'
        "</div>"
    ]

    if subject and chapters is not None:
        bits.append(
            '<div class="progress-wrap">'
            '<div class="progress-label"><span>Chapters done</span>'
            f'<span data-subject-text="{html.escape(subject)}" data-total="{len(chapters)}">'
            f"0 of {len(chapters)}</span></div>"
            '<div class="bar"><span class="fill" '
            f'data-subject="{html.escape(subject)}" data-total="{len(chapters)}"></span></div>'
            "</div>"
        )

    bits.append('<div class="toc-group">All subjects</div>')
    for s in NAV_SUBJECTS:
        if s["slug"] in NAV_PENDING:
            bits.append(
                f'<span class="toc-item is-off"><span class="toc-num">&middot;</span>'
                f'{html.escape(s["title"])} <em>in progress</em></span>'
            )
            continue
        on = " is-on" if s["slug"] == subject else ""
        code = html.escape(str(s.get("code", "")).split("/")[0].strip())
        bits.append(
            f'<a class="toc-item{on}" href="{href_to(root, s["slug"] + "/index.html")}">'
            f'<span class="toc-num">{code}</span>{html.escape(s["title"])}</a>'
        )

    if subject:
        subj = next((s for s in NAV_SUBJECTS if s["slug"] == subject), None)
        title = subj["title"] if subj else subject.title()
        bits.append(f'<div class="toc-group">{html.escape(title)}</div>')
        for key, label, fn in SECTIONS:
            on = " is-on" if active == key else ""
            cur = ' aria-current="page"' if active == key else ""
            bits.append(
                f'<a class="toc-item{on}" href="{href_to(root, f"{subject}/{fn}")}"{cur}>'
                f'<span class="toc-num">&bull;</span>{html.escape(label)}</a>'
            )

        if chapters is not None and subj:
            bits.append('<div class="toc-group">Chapters</div>')
            for unit in subj["units"]:
                chs = [c for c in chapters if c.get("unit") == unit["id"]]
                if not chs:
                    continue
                bits.append(
                    f'<div class="toc-sub">{html.escape(unit["title"])}</div>'
                )
                for c in chs:
                    on = " is-on" if c["id"] == chapter_id else ""
                    cur = ' aria-current="page"' if c["id"] == chapter_id else ""
                    url = href_to(root, subject + "/chapters/" + c["id"] + ".html")
                    bits.append(
                        f'<a class="toc-item toc-ch{on}" href="{url}"{cur}>'
                        f'<span class="toc-num">{c["num"]}</span>'
                        f'{html.escape(c["title"])}</a>'
                    )

    bits.append(
        '<div class="sidebar-foot">Progress is saved in this browser.<br>'
        f'Created by <strong>{html.escape(CREDIT)}</strong></div>'
    )
    return "\n".join(bits)


def footer(root):
    subj_links = " ".join(
        f'<a href="{href_to(root, s["slug"] + "/index.html")}">{html.escape(s["title"])}</a>'
        if s["slug"] not in NAV_PENDING
        else f'<span class="foot-off">{html.escape(s["title"])}</span>'
        for s in NAV_SUBJECTS
    )
    return (
        '<div class="foot-main">'
        f"<p>Built for CBSE Class 10 &middot; session {SESSION} &middot; content is original study material,\n"
        "  not official CBSE papers. Always confirm the syllabus against\n"
        '  <a href="https://cbseacademic.nic.in/">cbseacademic.nic.in</a>.</p>'
        + (
            f'<nav class="foot-subj" aria-label="All subjects">{subj_links}</nav>'
            if subj_links
            else ""
        )
        + f'<p class="credit">Created by <strong>{html.escape(CREDIT)}</strong></p>'
        + "</div>"
    )


def page(title, crumbs, body, root="..", subject=None, active=None,
         chapters=None, chapter_id=None):
    crumb_html = ' <span class="sep">/</span> '.join(
        f'<a href="{url}">{html.escape(label)}</a>' if url else html.escape(label)
        for label, url in crumbs
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} \u00b7 Class 10 CBSE</title>
<meta name="description" content="CBSE Class 10 {html.escape(title)} \u2014 chapter notes, formulas, exam Q&amp;A and revision.">
<link rel="stylesheet" href="{root}/assets/style.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<button class="menu-btn" onclick="openMenu()" aria-label="Open navigation">&#9776;</button>
<div class="backdrop" id="backdrop" onclick="closeMenu()"></div>
<div class="app">
  <aside class="sidebar" id="sidebar" aria-label="Site navigation">
{sidebar(root, subject, active, chapters, chapter_id)}
  </aside>
  <main id="main" class="wrap">
    <nav class="crumbs" aria-label="Breadcrumb">{crumb_html}</nav>
{body}
  </main>
</div>
<footer class="wrap foot">
  {footer(root)}
  <button class="totop" onclick="scrollTo({{top:0,behavior:'smooth'}})">\u2191 Top</button>
</footer>
<script src="{root}/assets/app.js"></script>
</body>
</html>
"""


def card_grid(cards, cls="cards"):
    return f'<div class="{cls}">' + "".join(cards) + "</div>"


# --------------------------------------------------------------------------
# IT-style Q&A cards (Short / Long / Application / Competency + MCQ)
# --------------------------------------------------------------------------
TYPE_META = {
    "S": ("SHORT", "Short"),
    "L": ("LONG", "Long"),
    "A": ("APPLICATION", "Application"),
    "C": ("COMPETENCY", "Competency"),
    "M": ("MCQ", "MCQ"),
}


def infer_qa_type(q) -> str:
    t = str(q.get("t") or "").upper()[:1]
    if t in TYPE_META and t != "M":
        return t
    text = str(q.get("q", "")).lower()
    if any(
        k in text
        for k in (
            "read the following",
            "read and answer",
            "case-stud",
            "competency",
            "निम्नलिखित",
            "पढ़कर उत्तर",
        )
    ):
        return "C"
    if any(
        k in text
        for k in (
            "apply ",
            "situation",
            "rewrite",
            "a student",
            "identify the violated",
            "स्थिति",
        )
    ):
        return "A"
    try:
        n = int(re.match(r"\d+", str(q.get("m", "3"))).group(0))
    except Exception:
        n = 3
    return "S" if n <= 3 else "L"


def render_qcard(q, idx, kind="qa"):
    """One click-to-reveal card. kind='qa' or 'mcq'."""
    t = "M" if kind == "mcq" else infer_qa_type(q)
    badge, _label = TYPE_META[t]
    marks = html.escape(str(q.get("m", "1" if t == "M" else "2")))
    qhtml = inline(q["q"])
    ans = q["a"]
    ans_html = blocks(ans if isinstance(ans, list) else [ans])
    code = f"{t}{idx}"
    return (
        f'<article class="qcard" data-type="{t}">'
        f'<div class="qmeta">'
        f'<span class="qbadge qbadge-{t.lower()}">{badge}</span>'
        f'<span class="qcode">{html.escape(code)}</span>'
        f'<span class="marks">{marks} mark{"s" if marks != "1" else ""}</span>'
        f"</div>"
        f'<p class="qtext"><strong>{idx}.</strong> {qhtml}</p>'
        f'<details class="qans"><summary>Show Answer</summary>'
        f'<div class="ans"><p><strong>Ans:</strong></p>{ans_html}</div>'
        f"</details></article>"
    )


def render_qbank(items, kind="qa", heading=None):
    if not items:
        return '<p class="hint">No questions filed yet.</p>'
    cards = "".join(render_qcard(q, i, kind) for i, q in enumerate(items, 1))
    head = f"<h2>{html.escape(heading)}</h2>" if heading else ""
    return f'{head}<div class="qstack">{cards}</div>'


def qbar_html(n_s, n_l, n_a, n_c, n_m=0):
    total = n_s + n_l + n_a + n_c + n_m
    btns = [("all", f"All types ({total})")]
    if n_s:
        btns.append(("S", f"Short ({n_s})"))
    if n_l:
        btns.append(("L", f"Long ({n_l})"))
    if n_a:
        btns.append(("A", f"Application ({n_a})"))
    if n_c:
        btns.append(("C", f"Competency ({n_c})"))
    if n_m:
        btns.append(("M", f"MCQ ({n_m})"))
    filters = "".join(
        f'<button type="button" class="qfilter{" is-on" if key == "all" else ""}" data-filter="{key}">{html.escape(label)}</button>'
        for key, label in btns
    )
    return (
        '<div class="qbar" data-qbar>'
        f'<p class="qcount"><span data-revealed>0</span> / {total} revealed'
        f'<span class="qshown"> · <span data-shown>{total}</span> shown</span></p>'
        f'<div class="qfilters">{filters}</div>'
        '<div class="qbar-actions">'
        '<button type="button" class="btn" data-show-all>Show all</button>'
        '<button type="button" class="btn" data-hide-all>Hide all</button>'
        "</div>"
        '<p class="hint">Write each answer in a notebook <strong>without seeing</strong>, then reveal and self-mark. '
        "Original practice — not official CBSE papers.</p>"
        "</div>"
    )


def count_types(qa, mcq=None):
    n = {k: 0 for k in "SLACM"}
    for q in qa or []:
        n[infer_qa_type(q)] += 1
    n["M"] = len(mcq or [])
    return n


def chapter_nav(chapters, ch, href_of, index_href, index_label="All chapters"):
    """Previous / index / next links so a chapter is never a dead end."""
    i = next((k for k, c in enumerate(chapters) if c["id"] == ch["id"]), None)
    if i is None:
        return ""

    def side(offset, cls, tag):
        j = i + offset
        if not (0 <= j < len(chapters)):
            return f'<span class="chapnav-b is-off">{html.escape(tag)}</span>'
        c = chapters[j]
        return (
            f'<a class="{cls}" href="{href_of(c)}"><span>{html.escape(tag)}</span>'
            f'Ch {c["num"]} \u00b7 {html.escape(c["title"])}</a>'
        )

    return (
        '<nav class="chapnav" aria-label="Chapter navigation">'
        + side(-1, "chapnav-prev", "\u2190 Previous")
        + f'<a class="chapnav-index" href="{index_href}">{html.escape(index_label)}</a>'
        + side(1, "chapnav-next", "Next \u2192")
        + "</nav>"
    )


# --------------------------------------------------------------------------
# loaders
# --------------------------------------------------------------------------
def load(name):
    with open(CONTENT / name, encoding="utf-8") as fh:
        return json.load(fh)


def load_chapters(sid):
    """Chapters come either from chapters/<sid>.json (a list) or from any number
    of JSON files in chapters/<sid>/, so content can be split into small files."""
    single = CONTENT / "chapters" / f"{sid}.json"
    if single.exists():
        with open(single, encoding="utf-8") as fh:
            return json.load(fh)

    folder = CONTENT / "chapters" / sid
    if not folder.is_dir():
        raise FileNotFoundError(f"no chapter content for subject '{sid}'")

    chapters = []
    for path in sorted(folder.glob("*.json")):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        chapters.extend(data if isinstance(data, list) else [data])

    chapters.sort(key=lambda c: c["num"])
    seen = {}
    for c in chapters:
        if c["id"] in seen:
            raise ValueError(f"duplicate chapter id '{c['id']}' in {sid}")
        seen[c["id"]] = True
    return chapters


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------
# chapter page
# --------------------------------------------------------------------------
def chapters_body(subj, chapters):
    """One page listing every chapter, so there is a single obvious index."""
    total_qa = sum(len(c.get("qa") or []) for c in chapters)
    total_mcq = sum(len(c.get("mcq") or []) for c in chapters)
    dot = "\u00b7"
    chips = " ".join(
        '<a class="chip" href="#{}">{}</a>'.format(
            u["slug"], html.escape(u["title"].split(dot)[-1].strip()))
        for u in subj["units"]
        if any(c.get("unit") == u["id"] for c in chapters)
    )
    secs = []
    for unit in subj["units"]:
        chs = [c for c in chapters if c.get("unit") == unit["id"]]
        if not chs:
            continue
        rows = "".join(
            f'<tr><td>{c["num"]}</td>'
            f'<td><a href="chapters/{c["id"]}.html">{html.escape(c["title"])}</a>'
            f'<span class="rowsub">{inline(c.get("short", ""))}</span></td>'
            f'<td>{html.escape(c.get("weight", ""))}</td>'
            f'<td>{len(c.get("qa") or [])}</td>'
            f'<td>{len(c.get("mcq") or [])}</td>'
            f'<td><a class="more" href="practice/{c["id"]}.html">Practise \u2192</a></td></tr>'
            for c in chs
        )
        star = ' <span class="star">\u2b50</span>' if unit.get("priority") else ""
        secs.append(
            f'<section id="{unit["slug"]}">'
            f'<h3>{html.escape(unit["title"])}{star}'
            f'<span class="unitmarks">{html.escape(unit.get("marks", ""))}</span></h3>'
            f'<div class="tablewrap"><table><thead><tr><th>#</th><th>Chapter</th>'
            f"<th>Weightage</th><th>Q&amp;A</th><th>MCQs</th><th>Practise</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div></section>"
        )
    body = f"""
<p class="kicker">{html.escape(subj["kicker"])}</p>
<h1>{html.escape(subj["title"])} \u2014 all chapters</h1>
<p class="lede">{len(chapters)} chapters in study order, with <strong>{total_qa} written Q&amp;As</strong>
and <strong>{total_mcq} MCQs</strong>. Open a chapter to read it, or go straight to
<em>Practise</em> for its questions with hidden answers.</p>
<p class="chips">{chips}</p>
{"".join(secs)}
<p class="hint">Looking for unit-wise marks instead? See the
<a href="syllabus.html">syllabus page</a>, or the
<a href="index.html">subject hub</a> for the study cycle.</p>
"""
    return [("Home", "../index.html"), (subj["title"], "index.html"), ("Chapters", None)], body


def chapter_body(subj, ch, idx, total, chapters):
    sid = subj["slug"]
    unit = next((u for u in subj["units"] if u["id"] == ch.get("unit")), None)
    unit_label = unit["title"] if unit else subj["title"]
    unit_slug = unit["slug"] if unit else "index"
    unit_href = (
        f"../units/{unit_slug}.html" if unit else f"../index.html"
    )

    chips = [
        ("#marks-lens", "\U0001f3af Marks lens"),
        ("#deep-concepts", "\U0001f4d6 Deep concepts"),
    ]
    if ch.get("formulas"):
        chips.append(("#formulas", "\U0001f9ee Formulas"))
    if ch.get("steps"):
        chips.append(("#steps", "\U0001f6e0\ufe0f Steps"))
    if ch.get("tricks"):
        chips.append(("#tricks", "\U0001f9e0 Tricks"))
    if ch.get("mistakes"):
        chips.append(("#mistakes", "\u26a0\ufe0f Mistakes"))
    chips.append(("#exam-qa", "\u2753 Exam Q&A"))
    if ch.get("task"):
        chips.append(("#task", "\u270d\ufe0f Task"))

    default_lede = (
        "Deep study page: concepts, worked method, memory tricks, "
        "mistakes to avoid and exam Q&A. Finish it and tick the box at the bottom."
    )
    lede_html = inline(ch.get("lede", default_lede))
    practice_href = f"../practice/{ch['id']}.html"
    chip_html = " ".join(f'<a class="chip" href="{h}">{t}</a>' for h, t in chips)

    parts = []
    parts.append(
        f'<p class="kicker">{html.escape(subj["kicker"])}</p>'
        f'<h1>Chapter {ch["num"]} \u00b7 {html.escape(ch["title"])}</h1>'
        f'<p class="lede"><strong>Chapter {idx} of {total}.</strong> {lede_html}</p>'
        f'<p><a class="btn" href="{practice_href}">'
        f'Open this chapter\u2019s questions + MCQs \u2192</a></p>'
        f'<p class="chips">{chip_html}</p>'
    )

    if ch.get("visual"):
        parts.append('<h2 id="visual">\U0001f5bc\ufe0f Visual summary</h2>')
        parts.append('<div class="visual">' + "".join(
            f'<div class="vbox"><strong>{inline(v["t"])}</strong>'
            f'<span>{inline(v.get("s", ""))}</span></div>' for v in ch["visual"]
        ) + "</div>")

    parts.append(
        f'<h2 id="marks-lens">\U0001f3af Marks lens</h2>'
        f'<div class="callout">{blocks(ch["lens"])}</div>'
    )

    parts.append('<h2 id="deep-concepts">\U0001f4d6 Deep concepts</h2>')
    parts.append(blocks(ch.get("concepts", [])))

    if ch.get("formulas"):
        parts.append('<h2 id="formulas">\U0001f9ee Formulas to memorise</h2>')
        parts.append('<ul class="formula">' + "".join(
            f"<li>{inline(f)}</li>" for f in ch["formulas"]) + "</ul>")

    if ch.get("steps"):
        parts.append('<h2 id="steps">\U0001f6e0\ufe0f Method, step by step</h2>')
        parts.append(blocks(ch["steps"]))

    if ch.get("tricks"):
        parts.append('<h2 id="tricks">\U0001f9e0 Memory tricks</h2>')
        parts.append(blocks(ch["tricks"]))

    if ch.get("mistakes"):
        parts.append('<h2 id="mistakes">\u26a0\ufe0f Mistakes that cost marks</h2>')
        parts.append(blocks(ch["mistakes"]))

    parts.append('<h2 id="exam-qa">\u2753 Exam Q&A</h2>')
    parts.append(
        '<p class="hint">Short · Long · Application · Competency — write first, then Show Answer.</p>'
    )
    qa_items = ch.get("qa") or []
    n = count_types(qa_items)
    parts.append(qbar_html(n["S"], n["L"], n["A"], n["C"]))
    parts.append(render_qbank(qa_items))

    if ch.get("task"):
        parts.append('<h2 id="task">\u270d\ufe0f Hands-on task</h2>')
        parts.append(f'<div class="callout alt">{blocks(ch["task"])}</div>')

    key = f"{sid}::{(unit['id'] if unit else 'general')}##{ch['id']}"
    parts.append(
        '<div class="done">'
        '<label><input type="checkbox" class="mark-complete" '
        f'data-key="{html.escape(key)}" data-subject="{sid}"> '
        f'Mark \u201cCh {ch["num"]} \u00b7 {html.escape(ch["title"])}\u201d complete</label>'
        f'<p><a href="../practice/{ch["id"]}.html">Practise this chapter\u2019s MCQs and '
        "written questions \u2192</a></p>"
        "</div>"
    )
    parts.append(
        chapter_nav(
            chapters,
            ch,
            lambda c: f"{c['id']}.html",
            "../chapters.html",
            f"All {subj['title']} chapters",
        )
    )

    crumbs = [
        ("Home", "../../index.html"),
        (subj["title"], f"../index.html"),
        (unit_label, unit_href),
        (f'Ch {ch["num"]} \u00b7 {ch["title"]}', None),
    ]
    return crumbs, "\n".join(parts)


# --------------------------------------------------------------------------
# subject hub
# --------------------------------------------------------------------------
def hub_body(subj, chapters):
    sid = subj["slug"]
    total = len(chapters)
    by_unit = {}
    for ch in chapters:
        by_unit.setdefault(ch.get("unit"), []).append(ch)

    cards = []
    for unit in subj["units"]:
        chs = by_unit.get(unit["id"], [])
        links = "".join(
            f'<li><a href="chapters/{c["id"]}.html">Ch {c["num"]} \u00b7 {html.escape(c["title"])}</a></li>'
            for c in chs
        )
        star = ' <span class="star">\u2b50</span>' if unit.get("priority") else ""
        cards.append(
            f'<article class="unit-card"><h3>{html.escape(unit["title"])}{star}'
            f'<span class="unitmarks">{html.escape(unit.get("marks", ""))}</span></h3>'
            f'<p class="unitdesc">{inline(unit.get("desc", ""))}</p>'
            f'<ul class="chlinks">{links}</ul>'
            f'<p class="unitfoot"><span class="prog" data-unit="{sid}::{unit["id"]}" '
            f'data-total="{len(chs)}">0/{len(chs)} chapters</span>'
            f'<a class="more" href="units/{unit["slug"]}.html">Unit overview \u2192</a></p>'
            "</article>"
        )

    assess = "".join(
        f"<tr><td>{inline(r[0])}</td><td><strong>{html.escape(str(r[1]))}</strong></td>"
        f"<td>{inline(r[2])}</td></tr>"
        for r in subj["assessment"]
    )
    order = "".join(f"<li>{inline(o)}</li>" for o in subj["study_order"])

    first = chapters[0]
    cards_meta = subj.get("cards", {})
    n_qa = sum(len(c.get("qa") or []) for c in chapters)
    n_mcq = sum(len(c.get("mcq") or []) for c in chapters)
    jump_items = [
        ("practical.html", "\U0001f9ea", cards_meta.get("practical", "Practical lab"),
         "Activities, diagrams, viva questions."),
        ("question-bank.html", "\u2753", cards_meta.get("questions", "Question bank"),
         f"{n_qa} written Q&As — Short, Long, Application, Competency. Click to reveal."),
        ("drill.html", "\U0001f3af", "Drill MCQs",
         f"{n_mcq} MCQs. Attempt first, then Show Answer."),
        ("pyq.html", "\U0001f4dd", cards_meta.get("pyq", "PYQ practice"),
         "Past-paper trends by chapter."),
        ("revision.html", "\U0001f9e0", cards_meta.get("revision", "Exam morning"),
         "Formulas, definitions and answer frames."),
    ]
    jump_cards = card_grid([
        f'<a class="jump" href="{href}"><strong>{icon} {html.escape(label)}</strong>'
        f'<span>{html.escape(desc)}</span></a>'
        for href, icon, label, desc in jump_items
    ])
    body = f"""
<p class="kicker">{html.escape(subj["kicker"])}</p>
<h1>{html.escape(subj["title"])} <span class="code">Subject Code {html.escape(subj["code"])}</span></h1>
<p class="lede">{inline(subj["blurb"])}</p>
<p class="btnrow">
  <a class="btn" href="syllabus.html">View syllabus</a>
  <a class="btn primary" href="chapters/{first["id"]}.html">Start Ch {first["num"]} \u00b7 {html.escape(first["title"])} \u2192</a>
  <a class="btn" href="revision.html">Quick revision</a>
</p>

<section class="dash">
  <h2>Study dashboard</h2>
  <p class="dashsub"><strong>Your {total}-chapter progress</strong></p>
  <div class="bar"><span class="fill" data-subject="{sid}" data-total="{total}"></span></div>
  <p class="dashtxt" data-subject-text="{sid}" data-total="{total}">0 of {total} chapters marked complete</p>
  <p class="hint">Saved on this device with localStorage. Tick \u201cMark complete\u201d at the bottom of each chapter.</p>
</section>

<h2>{html.escape(subj.get("areas_heading", "Study areas"))} \u00b7 {total} chapters</h2>
{card_grid(cards, "units")}

<h2>Assessment at a glance</h2>
<div class="tablewrap"><table><thead><tr><th>Component</th><th>Marks</th><th>Preparation</th></tr></thead>
<tbody>{assess}</tbody></table></div>

<h2>Topper\u2019s study order</h2>
<ol class="order">{order}</ol>
<p class="hint">{inline(subj.get("countdown", ""))}</p>

<h2>Follow the cycle, in order</h2>
<div class="cycle">
  <a class="cycle-card" href="chapters/{first["id"]}.html"><span class="cycle-n">1</span><strong>Learn</strong><span>Chapter notes, concepts, tricks.</span></a>
  <a class="cycle-card" href="practice/{first["id"]}.html"><span class="cycle-n">2</span><strong>Write</strong><span>Short · Long · Application · Competency. Cover, write, compare.</span></a>
  <a class="cycle-card" href="drill.html"><span class="cycle-n">3</span><strong>Drill</strong><span>MCQs for the whole subject. Show Answer when ready.</span></a>
  <a class="cycle-card" href="revision.html"><span class="cycle-n">4</span><strong>Revise</strong><span>One-page sheet per chapter.</span></a>
  <a class="cycle-card" href="question-bank.html"><span class="cycle-n">5</span><strong>Bank</strong><span>Every written Q&amp;A, answers hidden.</span></a>
</div>

<h2>Jump in</h2>
{jump_cards}
"""
    crumbs = [("Home", "../index.html"), (subj["title"], None)]
    return crumbs, body


# --------------------------------------------------------------------------
# secondary pages
# --------------------------------------------------------------------------
def syllabus_body(subj, chapters):
    rows = "".join(
        f'<tr><td>{ch["num"]}</td><td><a href="chapters/{ch["id"]}.html">'
        f'{html.escape(ch["title"])}</a></td>'
        f'<td>{inline(ch.get("unit_name", ""))}</td>'
        f'<td>{inline(ch.get("weight", ""))}</td></tr>'
        for ch in chapters
    )
    body = f"""
<p class="kicker">{html.escape(subj["kicker"])}</p>
<h1>{html.escape(subj["title"])} \u2014 Syllabus</h1>
<p class="lede">{inline(subj.get("syllabus_note", "The full chapter list with unit and exam weightage."))}</p>
<div class="tablewrap"><table><thead><tr><th>#</th><th>Chapter</th><th>Unit</th><th>Weightage</th></tr></thead>
<tbody>{rows}</tbody></table></div>
{("<h2>Removed from the syllabus</h2>" + blocks(subj["removed"])) if subj.get("removed") else ""}
{("<h2>Prescribed books</h2>" + blocks(subj["books"])) if subj.get("books") else ""}
<p class="hint">Confirm against the current session\u2019s PDF on
<a href="https://cbseacademic.nic.in/">cbseacademic.nic.in</a>.</p>
"""
    return [("Home", "../index.html"), (subj["title"], "index.html"), ("Syllabus", None)], body


def revision_body(subj, chapters):
    secs = []
    for ch in chapters:
        items = []
        if ch.get("formulas"):
            items.append(
                '<p class="rhead">Formulas</p><ul class="formula">'
                + "".join(f"<li>{inline(f)}</li>" for f in ch["formulas"])
                + "</ul>"
            )
        if ch.get("onepager"):
            items.append(blocks(ch["onepager"]))
        if not items:
            items.append('<p class="hint">Revision points for this chapter are not written yet.</p>')
        secs.append(
            f'<details class="rev" {"open" if ch["num"] <= 2 else ""}>'
            f'<summary><span>Ch {ch["num"]}</span> {html.escape(ch["title"])}</summary>'
            + "".join(items) + "</details>"
        )
    body = f"""
<p class="kicker">{html.escape(subj["kicker"])}</p>
<h1>{html.escape(subj["title"])} \u2014 Quick revision</h1>
<p class="lede">One screen per chapter: formulas and the points that actually get asked.
Expand what you need, skip what you know.</p>
{"".join(secs)}
"""
    return [("Home", "../index.html"), (subj["title"], "index.html"), ("Revision", None)], body


def question_bank_body(subj, chapters):
    all_qa = []
    secs = []
    for ch in chapters:
        items = ch.get("qa") or []
        all_qa.extend(items)
        cards = "".join(render_qcard(q, i) for i, q in enumerate(items, 1))
        secs.append(
            f'<section class="qblock" id="{ch["id"]}">'
            f'<h3>Ch {ch["num"]} \u00b7 {html.escape(ch["title"])} '
            f'<span class="hint">({len(items)})</span></h3>'
            f'<div class="qstack">{cards or "<p class=hint>No questions filed yet.</p>"}</div>'
            f'<p><a class="btn" href="practice/{ch["id"]}.html">Chapter practice (MCQs + written) \u2192</a></p>'
            "</section>"
        )
    n = count_types(all_qa)
    toc = " ".join(
        f'<a class="chip" href="#{ch["id"]}">Ch {ch["num"]}</a>' for ch in chapters
    )
    body = f"""
<p class="kicker">{html.escape(subj["kicker"])}</p>
<h1>{html.escape(subj["title"])} \u2014 Question bank</h1>
<p class="lede">Book-style Q&amp;As: Short + Long + Application + Competency.
Answers stay hidden until you click <strong>Show Answer</strong>. Write 15–20 a day in a notebook, then self-mark.</p>
{qbar_html(n["S"], n["L"], n["A"], n["C"])}
<p class="chips">{toc}</p>
{"".join(secs)}
"""
    return [("Home", "../index.html"), (subj["title"], "index.html"), ("Question bank", None)], body


def pyq_body(subj, chapters):
    rows = []
    for ch in chapters:
        trend = ch.get("trend", "Not yet mapped")
        rows.append(
            f'<tr id="C-{ch["id"]}"><td>Ch {ch["num"]}</td>'
            f'<td><a href="chapters/{ch["id"]}.html">{html.escape(ch["title"])}</a></td>'
            f"<td>{inline(trend)}</td></tr>"
        )
    body = f"""
<p class="kicker">{html.escape(subj["kicker"])}</p>
<h1>{html.escape(subj["title"])} \u2014 PYQ trends</h1>
<p class="lede">Where past papers keep returning, chapter by chapter. Use it to decide
revision order \u2014 not to guess the paper.</p>
<div class="callout"><p>Trend notes below are an original reading of publicly available past
papers and sample papers. They are <strong>not</strong> official CBSE predictions.</p></div>
<div class="tablewrap"><table><thead><tr><th>Chapter</th><th>Title</th><th>What past papers ask</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
"""
    return [("Home", "../index.html"), (subj["title"], "index.html"), ("PYQ", None)], body


def practical_body(subj):
    body = f"""
<p class="kicker">{html.escape(subj["kicker"])}</p>
<h1>{html.escape(subj["title"])} \u2014 Practical &amp; internal assessment</h1>
<p class="lede">{inline(subj.get("practical_note", "What the internal assessment expects and how to prepare it."))}</p>
{blocks(subj.get("practical", []))}
"""
    return [("Home", "../index.html"), (subj["title"], "index.html"), ("Practical", None)], body


def unit_body(subj, unit, chapters):
    chs = [c for c in chapters if c.get("unit") == unit["id"]]
    links = "".join(
        f'<li><a href="../chapters/{c["id"]}.html"><strong>Ch {c["num"]} \u00b7 {html.escape(c["title"])}</strong>'
        f'<span>{inline(c.get("short", ""))}</span></a></li>'
        for c in chs
    )
    body = f"""
<p class="kicker">{html.escape(subj["kicker"])}</p>
<h1>{html.escape(unit["title"])}</h1>
<p class="lede"><strong>{html.escape(unit.get("marks", ""))}.</strong> {inline(unit.get("desc", ""))}</p>
{blocks(unit.get("intro", []))}
<ul class="biglinks">{links}</ul>
{blocks(unit.get("tips", []))}
"""
    return [("Home", "../../index.html"), (subj["title"], "../index.html"), (unit["title"], None)], body


def practice_body(subj, ch, chapters):
    qa_items = ch.get("qa") or []
    mcq_items = ch.get("mcq") or []
    n = count_types(qa_items, mcq_items)
    mcq_html = "".join(render_qcard(m, i, "mcq") for i, m in enumerate(mcq_items, 1))
    body = f"""
<p class="kicker">{html.escape(subj["kicker"])}</p>
<h1>Ch {ch["num"]} \u00b7 {html.escape(ch["title"])} \u2014 Write &amp; Drill</h1>
<p class="lede">Cover the grey answer box, write in a notebook, then <strong>Show Answer</strong>.
Short · Long · Application · Competency plus MCQs — the same tone as the IT bank.</p>
{qbar_html(n["S"], n["L"], n["A"], n["C"], n["M"])}
<h2>MCQs · Drill</h2>
<div class="qstack">{mcq_html or '<p class="hint">MCQs for this chapter are not written yet.</p>'}</div>
<h2>Written questions · Write</h2>
{render_qbank(qa_items)}
<p><a class="btn" href="../chapters/{ch["id"]}.html">\u2190 Back to the chapter</a></p>
{chapter_nav(chapters, ch, lambda c: c["id"] + ".html", "../chapters.html",
               "All " + subj["title"] + " chapters")}
"""
    return [("Home", "../../index.html"), (subj["title"], "../index.html"),
            (f'Ch {ch["num"]} \u00b7 {ch["title"]}', f"../chapters/{ch['id']}.html"),
            ("Practice", None)], body


def drill_body(subj, chapters):
    cards = []
    n_mcq = 0
    for ch in chapters:
        items = ch.get("mcq") or []
        n_mcq += len(items)
        inner = "".join(render_qcard(m, i, "mcq") for i, m in enumerate(items, 1))
        cards.append(
            f'<section class="qblock" id="{ch["id"]}">'
            f'<h3>Ch {ch["num"]} \u00b7 {html.escape(ch["title"])} '
            f'<span class="hint">({len(items)})</span></h3>'
            f'<div class="qstack">{inner or "<p class=hint>No MCQs yet.</p>"}</div>'
            "</section>"
        )
    toc = " ".join(
        f'<a class="chip" href="#{ch["id"]}">Ch {ch["num"]}</a>' for ch in chapters
    )
    body = f"""
<p class="kicker">{html.escape(subj["kicker"])}</p>
<h1>{html.escape(subj["title"])} \u2014 Drill</h1>
<p class="lede">{n_mcq} MCQs across {len(chapters)} chapters. Pick an option in your head,
then Show Answer. Filter does not score you — this is self-check, not a test.</p>
{qbar_html(0, 0, 0, 0, n_mcq)}
<p class="chips">{toc}</p>
{"".join(cards)}
"""
    return [("Home", "../index.html"), (subj["title"], "index.html"), ("Drill", None)], body


# --------------------------------------------------------------------------
# portal
# --------------------------------------------------------------------------
def portal_body(subjects, counts, pending=()):
    cards = []
    for s in subjects:
        if s["slug"] in pending:
            cards.append(
                f'<span class="subject-card pending">'
                f'<span class="sc-code">{html.escape(s["code"])} \u00b7 in progress</span>'
                f'<strong>{html.escape(s["title"])}</strong>'
                f'<span class="sc-desc">{inline(s.get("short", ""))}</span>'
                f'<span class="sc-meta">Hub opens once its chapter content is written.</span></span>'
            )
            continue
        n = counts[s["slug"]]
        cards.append(
            f'<a class="subject-card" href="{s["slug"]}/index.html">'
            f'<span class="sc-code">{html.escape(s["code"])}</span>'
            f'<strong>{html.escape(s["title"])}</strong>'
            f'<span class="sc-desc">{inline(s.get("short", ""))}</span>'
            f'<span class="sc-meta">{n} chapters \u00b7 {html.escape(s.get("marks", ""))}</span></a>'
        )
    body = f"""
<p class="kicker">CBSE \u2022 CLASS 10 \u2022 SESSION {SESSION}</p>
<h1>Class 10 CBSE \u2014 every subject, one hub each</h1>
<p class="lede">The same study hub for every subject — including <strong>Information Technology (402)</strong>,
built in here, not on a separate site. Each chapter has concepts, formulas, tricks, mistakes to avoid,
and exam Q&amp;A in four tones: <strong>Short, Long, Application, Competency</strong>. Answers stay hidden
until you click Show Answer.</p>
{card_grid(cards, "subjects")}
<h2>How to use these</h2>
<ol class="order">
<li><strong>Learn</strong> — pick a subject, read the Marks lens, then the Deep concepts.</li>
<li><strong>Write</strong> — cover the answer, write Short / Long / Application / Competency in a notebook, then Show Answer.</li>
<li><strong>Drill</strong> — MCQs for the whole subject. Attempt first, then reveal.</li>
<li><strong>Revise</strong> — the one-page sheet, then tick Mark complete. Progress stays on this device.</li>
<li><strong>Bank</strong> — every written Q&amp;A, filtered by type, 15–20 a day.</li>
</ol>
"""
    return [("Home", None)], body


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------
def not_found(base=BASE):
    """A self-contained 404 page.

    GitHub Pages answers every unknown path with this file, so the stylesheet
    and the links have to be absolute under the published base path.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page not found \u00b7 Class 10 CBSE</title>
<style>
  body {{ margin: 0; font: 16px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif;
         background: #0f172a; color: #e2e8f0; display: grid; place-items: center;
         min-height: 100vh; padding: 2rem; }}
  .box {{ max-width: 34rem; }}
  h1 {{ font-size: 2.6rem; margin: 0 0 .5rem; }}
  p {{ color: #94a3b8; }}
  a {{ color: #7dd3fc; }}
</style>
</head>
<body>
  <div class="box">
    <h1>404</h1>
    <p>That page is not part of the Class 10 CBSE study hub. The chapter lists,
    revision sheets and question banks all start from the portal.</p>
    <p><a href="{base}/index.html">\u2190 Back to all subjects</a></p>
    <p class="credit">Created by <strong>{CREDIT}</strong></p>
  </div>
</body>
</html>
"""


def chapters_exist(sid) -> bool:
    """True when chapter content has been authored for this subject."""
    if (CONTENT / "chapters" / f"{sid}.json").exists():
        return True
    folder = CONTENT / "chapters" / sid
    return folder.is_dir() and any(folder.glob("*.json"))


def build(check_only=False):
    if DIST.resolve() == REPO.resolve():
        raise SystemExit("refusing to build: output directory is the repo root")
    subjects = load("subjects.json")

    # Every page renders the same sidebar, so share the subject list and work
    # out up front which subjects still have no content.
    global NAV_SUBJECTS, NAV_PENDING
    NAV_SUBJECTS = subjects
    NAV_PENDING = {s["slug"] for s in subjects if not chapters_exist(s["slug"])}

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    (DIST / "assets").mkdir()
    shutil.copy(THEME / "style.css", DIST / "assets" / "style.css")
    shutil.copy(THEME / "app.js", DIST / "assets" / "app.js")

    # GitHub Pages runs Jekyll on a branch-served folder unless this marker is
    # present; the site is plain static HTML, so skip it.
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    write(DIST / "404.html", not_found())

    counts, written, pending = {}, [], []

    for subj in subjects:
        sid = subj["slug"]
        if sid in NAV_PENDING:
            # No chapter content authored for this subject yet: keep the portal
            # honest instead of failing the whole build.
            counts[sid] = 0
            pending.append(sid)
            print(f"  skipped {sid}: no chapter content yet")
            continue

        chapters = load_chapters(sid)
        counts[sid] = len(chapters)

        # Content sanity checks, so a typo cannot silently produce a broken hub.
        unit_ids = {u["id"] for u in subj["units"]}
        for i, ch in enumerate(chapters, 1):
            if ch["num"] != i:
                raise ValueError(
                    f"{sid}: chapter numbering gap \u2014 expected {i}, got {ch['num']} ({ch['id']})"
                )
            if ch.get("unit") not in unit_ids:
                raise ValueError(
                    f"{sid}/{ch['id']}: unknown unit '{ch.get('unit')}' "
                    f"(known: {sorted(unit_ids)})"
                )
            if not ch.get("lens"):
                raise ValueError(f"{sid}/{ch['id']}: missing 'lens'")
            if not ch.get("concepts"):
                raise ValueError(f"{sid}/{ch['id']}: missing 'concepts'")

        def out(path, title, crumbs, body, root, active=None, chapter_id=None):
            write(path, page(title, crumbs, body, root, sid, active, chapters, chapter_id))

        crumbs, body = hub_body(subj, chapters)
        out(DIST / sid / "index.html", f"{subj['title']} hub", crumbs, body, "..", "hub")
        written.append(f"{sid}/index.html")

        for fn, fn_body, title, active in (
            ("chapters.html", chapters_body, "All chapters", "chapters"),
            ("syllabus.html", syllabus_body, "Syllabus", "syllabus"),
            ("question-bank.html", question_bank_body, "Question bank", "bank"),
            ("drill.html", drill_body, "MCQ drill", "drill"),
            ("revision.html", revision_body, "Revision", "revision"),
            ("pyq.html", pyq_body, "PYQ trends", "pyq"),
        ):
            crumbs, body = fn_body(subj, chapters)
            out(DIST / sid / fn, f"{subj['title']} \u2014 {title}", crumbs, body, "..", active)
            written.append(f"{sid}/{fn}")

        crumbs, body = practical_body(subj)
        out(DIST / sid / "practical.html", "Practical &amp; internal assessment",
            crumbs, body, "..", "practical")
        written.append(f"{sid}/practical.html")

        for unit in subj["units"]:
            crumbs, body = unit_body(subj, unit, chapters)
            out(DIST / sid / "units" / f"{unit['slug']}.html", unit["title"],
                crumbs, body, "../..", "chapters")
            written.append(f"{sid}/units/{unit['slug']}.html")

        for i, ch in enumerate(chapters, 1):
            crumbs, body = chapter_body(subj, ch, i, len(chapters), chapters)
            out(DIST / sid / "chapters" / f"{ch['id']}.html",
                f"Ch {ch['num']} \u00b7 {ch['title']}", crumbs, body, "../..", "chapters",
                chapter_id=ch["id"])
            crumbs, body = practice_body(subj, ch, chapters)
            out(DIST / sid / "practice" / f"{ch['id']}.html",
                f"Ch {ch['num']} \u00b7 {ch['title']} \u2014 practice", crumbs, body, "../..",
                "chapters", chapter_id=ch["id"])
            written.append(f"{sid}/chapters/{ch['id']}.html")
            written.append(f"{sid}/practice/{ch['id']}.html")

    crumbs, body = portal_body(subjects, counts, pending)
    write(DIST / "index.html", page("Home", crumbs, body, ".", None, "home"))
    written.append("index.html")
    return written, pending


def validate():
    """Every internal href must resolve to a file that was written."""
    broken = 0
    files = list(DIST.rglob("*.html"))
    for f in files:
        text = f.read_text(encoding="utf-8")
        for href in re.findall(r'href="([^"#]+?)(?:#[^"]*)?"', text):
            if href.startswith(("http", "mailto:", "/")):
                continue
            target = (f.parent / href).resolve()
            if not target.exists():
                print(f"BROKEN LINK {f.relative_to(DIST)} -> {href}")
                broken += 1
    return broken, len(files)


def main():
    global DIST
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="build then validate links")
    ap.add_argument(
        "--out",
        metavar="DIR",
        help=f"write the site here instead of {DIST.relative_to(REPO)} "
        "(relative paths are taken from the repository root)",
    )
    args = ap.parse_args()

    if args.out:
        out = Path(args.out)
        DIST = out if out.is_absolute() else (REPO / out)

    written, pending = build()
    try:
        shown = DIST.relative_to(REPO)
    except ValueError:
        shown = DIST
    print(f"built {len(written)} pages into {shown}")
    if pending:
        print(f"subjects awaiting chapter content: {', '.join(pending)}")
    broken, n = validate()
    print(f"validated {n} html files, {broken} broken links")
    if broken:
        sys.exit(1)


if __name__ == "__main__":
    main()
