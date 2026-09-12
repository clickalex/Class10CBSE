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
# page shell
# --------------------------------------------------------------------------
def page(title, crumbs, body, root="..", subject=None):
    crumb_html = ' <span class="sep">/</span> '.join(
        f'<a href="{url}">{html.escape(label)}</a>' if url else html.escape(label)
        for label, url in crumbs
    )
    home_url = f"{root}/index.html" if root != "." else "index.html"
    nav_extra = ""
    if subject:
        nav_extra = (
            f'<a href="{root}/index.html">All subjects</a>'
            f'<a href="{root}/{subject}/index.html">Hub</a>'
            f'<a href="{root}/{subject}/syllabus.html">Syllabus</a>'
            f'<a href="{root}/{subject}/revision.html">Revision</a>'
            f'<a href="{root}/{subject}/question-bank.html">Questions</a>'
            f'<a href="{root}/{subject}/pyq.html">PYQ</a>'
        )
    else:
        nav_extra = '<a href="index.html">All subjects</a>'
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
<header class="topbar">
  <div class="wrap topbar-in">
    <a class="brand" href="{home_url}">Class&nbsp;10&nbsp;<span>CBSE</span></a>
    <nav class="topnav">{nav_extra}</nav>
  </div>
</header>
<main id="main" class="wrap">
  <nav class="crumbs">{crumb_html}</nav>
{body}
</main>
<footer class="wrap foot">
  <p>Built for CBSE Class 10 \u00b7 session {SESSION} \u00b7 content is original study material,
  not official CBSE papers. Always confirm the syllabus against
  <a href="https://cbseacademic.nic.in/">cbseacademic.nic.in</a>.</p>
  <button class="totop" onclick="scrollTo({{top:0,behavior:'smooth'}})">\u2191 Top</button>
</footer>
<script src="{root}/assets/app.js"></script>
</body>
</html>
"""


def card_grid(cards, cls="cards"):
    return f'<div class="{cls}">' + "".join(cards) + "</div>"


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
def chapter_body(subj, ch, idx, total):
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
    qa_html = []
    for q in ch.get("qa", []):
        qa_html.append(
            f'<details class="qa"><summary><span class="marks">{html.escape(q["m"])} '
            f'marks</span> {inline(q["q"])}</summary>'
            f'<div class="ans">{blocks(q["a"] if isinstance(q["a"], list) else [q["a"]])}</div>'
            "</details>"
        )
    parts.append("".join(qa_html) or "<p>No questions filed yet.</p>")

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
    jump_items = [
        ("practical.html", "\U0001f9ea", cards_meta.get("practical", "Practical lab"),
         "Activities, diagrams, viva questions."),
        ("question-bank.html", "\u2753", cards_meta.get("questions", "Test yourself"),
         "Chapter-wise MCQs and written questions, syllabus-mapped."),
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

<h2>Jump in</h2>
{jump_cards}
"""
    crumbs = [("Home", "../index.html"), ("Home", None)]
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
    secs = []
    for ch in chapters:
        qa = "".join(
            f'<li><span class="marks">{html.escape(q["m"])}</span> {inline(q["q"])}</li>'
            for q in ch.get("qa", [])
        )
        qa_list = qa or '<li class="hint">No questions filed yet.</li>'
        secs.append(
            f'<section class="qblock"><h3 id="{ch["id"]}">Ch {ch["num"]} \u00b7 '
            f'{html.escape(ch["title"])}</h3>'
            f'<ul class="qlist">{qa_list}</ul>'
            f'<p><a class="btn" href="practice/{ch["id"]}.html">Practise with answers \u2192</a></p></section>'
        )
    toc = " ".join(
        f'<a class="chip" href="#{ch["id"]}">Ch {ch["num"]}</a>' for ch in chapters
    )
    body = f"""
<p class="kicker">{html.escape(subj["kicker"])}</p>
<h1>{html.escape(subj["title"])} \u2014 Question bank</h1>
<p class="lede">Every question filed on this site, grouped by chapter.
Original practice questions written to the syllabus \u2014 not official CBSE papers.</p>
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


def practice_body(subj, ch):
    qa = []
    for q in ch.get("qa", []):
        qa.append(
            f'<details class="qa"><summary><span class="marks">{html.escape(q["m"])} marks</span> '
            f'{inline(q["q"])}</summary><div class="ans">'
            f'{blocks(q["a"] if isinstance(q["a"], list) else [q["a"]])}</div></details>'
        )
    mcq = "".join(
        f'<details class="qa"><summary>{inline(m["q"])}</summary>'
        f'<div class="ans">{blocks([m["a"]])}</div></details>'
        for m in ch.get("mcq", [])
    )
    body = f"""
<p class="kicker">{html.escape(subj["kicker"])}</p>
<h1>Ch {ch["num"]} \u00b7 {html.escape(ch["title"])} \u2014 Practice</h1>
<p class="lede">Attempt first, then open the answer. Everything here is original
practice material mapped to the current syllabus.</p>
<h2>MCQs</h2>
{mcq or '<p class="hint">MCQs for this chapter are not written yet.</p>'}
<h2>Written questions</h2>
{"".join(qa) or '<p class="hint">Written questions for this chapter are not written yet.</p>'}
<p><a class="btn" href="../chapters/{ch["id"]}.html">\u2190 Back to the chapter</a></p>
"""
    return [("Home", "../../index.html"), (subj["title"], "../index.html"),
            (f'Ch {ch["num"]} \u00b7 {ch["title"]}', f"../chapters/{ch['id']}.html"),
            ("Practice", None)], body


# --------------------------------------------------------------------------
# portal
# --------------------------------------------------------------------------
def portal_body(subjects, counts, pending=()):
    cards = []
    for s in subjects:
        if s.get("external"):
            cards.append(
                f'<a class="subject-card" href="{html.escape(s["external"])}">'
                f'<span class="sc-code">{html.escape(s["code"])} \u00b7 separate site</span>'
                f'<strong>{html.escape(s["title"])}</strong>'
                f'<span class="sc-desc">{inline(s.get("short", ""))}</span>'
                f'<span class="sc-meta">Opens the existing {html.escape(s["code"])} hub \u2197</span></a>'
            )
            continue
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
<p class="lede">The same study hub for every subject: a progress dashboard, unit overviews,
and one deep page per chapter with concepts, formulas, memory tricks, mistakes to avoid
and exam Q&amp;A.</p>
{card_grid(cards, "subjects")}
<h2>How to use these</h2>
<ol class="order">
<li>Pick your subject, read the <strong>Marks lens</strong> on each chapter first \u2014 it tells you what is worth studying hard.</li>
<li>Work the <strong>Deep concepts</strong>, then close the page and attempt that chapter\u2019s questions.</li>
<li>Tick <strong>Mark complete</strong> at the bottom of each chapter; the hub tracks you on this device.</li>
<li>Finish with <strong>Quick revision</strong> and a timed sample paper.</li>
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
  </div>
</body>
</html>
"""


def build(check_only=False):
    if DIST.resolve() == REPO.resolve():
        raise SystemExit("refusing to build: output directory is the repo root")
    subjects = load("subjects.json")
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
        if subj.get("external"):
            counts[sid] = 0
            continue
        try:
            chapters = load_chapters(sid)
        except FileNotFoundError:
            # No chapter content authored for this subject yet: keep the portal
            # honest instead of failing the whole build.
            counts[sid] = 0
            pending.append(sid)
            print(f"  skipped {sid}: no chapter content yet")
            continue
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

        crumbs, body = hub_body(subj, chapters)
        write(DIST / sid / "index.html", page(f"{subj['title']} hub", crumbs, body, "..", sid))
        written.append(f"{sid}/index.html")

        for fn, fn_body in (
            ("syllabus.html", syllabus_body),
            ("revision.html", revision_body),
            ("question-bank.html", question_bank_body),
            ("pyq.html", pyq_body),
        ):
            crumbs, body = fn_body(subj, chapters)
            write(DIST / sid / fn, page(fn.replace(".html", " ").title(), crumbs, body, "..", sid))
            written.append(f"{sid}/{fn}")

        crumbs, body = practical_body(subj)
        write(DIST / sid / "practical.html", page("Practical", crumbs, body, "..", sid))
        written.append(f"{sid}/practical.html")

        for unit in subj["units"]:
            crumbs, body = unit_body(subj, unit, chapters)
            write(DIST / sid / "units" / f"{unit['slug']}.html",
                  page(unit["title"], crumbs, body, "../..", sid))
            written.append(f"{sid}/units/{unit['slug']}.html")

        for i, ch in enumerate(chapters, 1):
            crumbs, body = chapter_body(subj, ch, i, len(chapters))
            write(DIST / sid / "chapters" / f"{ch['id']}.html",
                  page(f"Ch {ch['num']} \u00b7 {ch['title']}", crumbs, body, "../..", sid))
            crumbs, body = practice_body(subj, ch)
            write(DIST / sid / "practice" / f"{ch['id']}.html",
                  page(f"Ch {ch['num']} practice", crumbs, body, "../..", sid))
            written.append(f"{sid}/chapters/{ch['id']}.html")

    crumbs, body = portal_body(subjects, counts, pending)
    write(DIST / "index.html", page("Home", crumbs, body, "."))
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
