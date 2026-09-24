"""Page shell and reusable components, assembled from site/partials/.

Everything a visitor sees on every page — <head>, header/drawer buttons, the
sidebar navigation, the footer, the 404 page and the button/chip components —
is markup that lives in site/partials/*.html. This module only fills those
partials with data; it owns no markup of its own beyond joining strings, so
design changes are edits to a .html file rather than to Python.

    from layout import page, sidebar, footer, not_found, component, button

Token syntax inside a partial is {{NAME}}. A partial that references a token
the caller forgot raises KeyError at build time, and any token left
unsubstituted in the output fails the build, so a typo can never reach docs/.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

SITE = Path(__file__).resolve().parent
REPO = SITE.parent
PARTIALS = SITE / "partials"

# Where GitHub Pages serves github.com/clickalex/Class10CBSE (a build of this
# site, published by the deploy workflows). Used for canonical/OG URLs and by
# the sitemap.
SITE_URL = "https://clickalex.github.io/Class10CBSE"
BASE = "/Class10CBSE"          # absolute path the 404 page links under
SESSION = "2026\u201327"        # board session shown in the sidebar and footer
CREDIT = "Mohammad Umair"

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

# Board / exam badges shown in the sidebar's toc-num pills.
MOCK_BADGES = {
    "maths": "041",
    "science": "086",
    "social-science": "087",
    "english": "184",
    "hindi-a": "002",
    "hindi-b": "085",
    "information-technology": "402",
    "computer-applications": "165",
    "sanskrit": "122",
    "nvs": "NVS",
    "jmi": "JMI",
    "amu": "AMU",
    "bhu": "BHU",
    "up-polytechnic": "UP",
    "bihar-polytechnic": "BR",
    "pw-nsat": "NSAT",
    "tallentex": "TAL",
    "anthe": "ANT",
    "iacst": "ACST",
    "vmc-viq": "VIQ",
}

# Short titles for the sidebar and footer, keyed by mock-test exam id.
MOCK_NAV_TITLES = {
    "maths": "Mathematics",
    "science": "Science",
    "social-science": "Social Science",
    "english": "English Language & Literature",
    "hindi-a": "Hindi Course A",
    "hindi-b": "Hindi Course B",
    "information-technology": "Information Technology",
    "computer-applications": "Computer Applications",
    "sanskrit": "Sanskrit",
    "nvs": "JNV Class XI",
    "jmi": "JMI Class XI (Science)",
    "amu": "AMU Class XI (Science)",
    "bhu": "BHU / CHS SET Class XI",
    "up-polytechnic": "UP Polytechnic (JEECUP)",
    "bihar-polytechnic": "Bihar Polytechnic (DCECE)",
    "pw-nsat": "PW NSAT (Class 10)",
    "tallentex": "ALLEN TALLENTEX",
    "anthe": "Aakash ANTHE",
    "iacst": "Aakash iACST",
    "vmc-viq": "Vidyamandir Classes VIQ",
}

# BCP-47 language per subject, so screen readers and search engines get the
# right language for Devanagari content instead of guessing English.
SUBJECT_LANGS = {"hindi": "hi", "sanskrit": "sa"}

# Filled in by configure() (called from build.build()) so every page can
# render the same subject switcher and mock-test links.
NAV_SUBJECTS: list = []
NAV_PENDING: set = set()
NAV_MOCK: dict = {}          # {subject slug: mock-test exam id}
MOCK_CHAPTERS: dict = {}     # {(subject slug, chapter id): mock exam id}
NAV_MOCK_GROUPS: list = []
NAV_MOCK_EXAMS: list = []

_TOKEN_RE = re.compile(r"\{\{(\w+)\}\}")
_COMPONENT_RE = re.compile(
    r"<!-- @component:([\w-]+) -->\n(.*?)\n<!-- @end -->", re.S)
# Documentation comments inside a partial are namespaced "<!-- partials/... -->"
# so they can be dropped from the published HTML: they explain the template to
# whoever edits it and must never ship to a visitor's browser.
_DOC_COMMENT_RE = re.compile(r"<!--\s*partials/.*?-->\n?", re.S)
_CACHE: dict = {}


def configure(subjects=(), pending=(), mock=None, mock_chapters=None,
              mock_groups=(), mock_exams=()):
    """Publish the shared navigation data for a build (or a test)."""
    global NAV_SUBJECTS, NAV_PENDING, NAV_MOCK, MOCK_CHAPTERS
    global NAV_MOCK_GROUPS, NAV_MOCK_EXAMS
    NAV_SUBJECTS = list(subjects)
    NAV_PENDING = set(pending)
    NAV_MOCK = dict(mock or {})
    MOCK_CHAPTERS = dict(mock_chapters or {})
    NAV_MOCK_GROUPS = list(mock_groups)
    NAV_MOCK_EXAMS = list(mock_exams)


# --------------------------------------------------------------------------
# partial loading / token substitution
# --------------------------------------------------------------------------
def _load(name):
    if name not in _CACHE:
        text = (PARTIALS / name).read_text(encoding="utf-8")
        _CACHE[name] = _DOC_COMMENT_RE.sub("", text)
    return _CACHE[name]


def render(name, **tokens):
    """Fill one partial file with tokens; fail loudly on anything left over."""
    missing = _TOKEN_RE.findall(_load(name))
    unknown = [key for key in missing if key not in tokens]
    if unknown:
        raise KeyError(f"partials/{name}: caller forgot token(s) {unknown}")

    def sub(match):
        return str(tokens[match.group(1)])

    out = _TOKEN_RE.sub(sub, _load(name))
    leftover = _TOKEN_RE.findall(out)
    if leftover:
        raise ValueError(
            f"partials/{name}: unsubstituted token(s) left in output: {leftover}")
    return out


def components():
    """{name: snippet} parsed out of partials/buttons.html."""
    if "_components" not in _CACHE:
        text = _load("buttons.html")
        found = {name: body.strip("\n") for name, body in _COMPONENT_RE.findall(text)}
        if not found:
            raise ValueError("partials/buttons.html defines no components")
        _CACHE["_components"] = found
    return _CACHE["_components"]


def component(name, **tokens):
    """Render one reusable component from partials/buttons.html."""
    snippets = components()
    if name not in snippets:
        raise KeyError(f"unknown component {name!r}; "
                       f"have: {', '.join(sorted(snippets))}")
    tokens.setdefault("MODIFIERS", "")
    tokens.setdefault("ATTRS", "")
    body = snippets[name]
    for key in _TOKEN_RE.findall(body):
        if key not in tokens:
            raise KeyError(f"component {name}: missing token {key}")

    def sub(match):
        return str(tokens[match.group(1)])

    return _TOKEN_RE.sub(sub, body)


def button(href, label, primary=False, attrs=""):
    """The site's call-to-action link; markup lives in partials/buttons.html."""
    return component("button", HREF=href, LABEL=label,
                     MODIFIERS=" primary" if primary else "", ATTRS=attrs)


def button_row(items, modifiers=""):
    return component("button-row", ITEMS=items, MODIFIERS=modifiers)


def chip(href, label, modifiers="", attrs=""):
    return component("chip", HREF=href, LABEL=label,
                     MODIFIERS=modifiers, ATTRS=attrs)


def chip_row(items, modifiers=""):
    return component("chip-row", ITEMS=items, MODIFIERS=modifiers)


def callout(text, modifiers=""):
    return component("callout", TEXT=text, MODIFIERS=modifiers)


# --------------------------------------------------------------------------
# navigation drawer
# --------------------------------------------------------------------------
def get_mock_nav_data():
    if not NAV_MOCK_EXAMS:
        conf_file = SITE / "content" / "mock-tests.json"
        if conf_file.is_file():
            try:
                with open(conf_file, encoding="utf-8") as fh:
                    cfg = json.load(fh)
                NAV_MOCK_GROUPS[:] = cfg.get("groups", [])
                NAV_MOCK_EXAMS[:] = cfg.get("exams", [])
            except Exception:
                pass
    return NAV_MOCK_GROUPS, NAV_MOCK_EXAMS


def href_to(root, path):
    """A link that works from any page depth."""
    return path if root == "." else f"{root}/{path}"


def sidebar(root, subject=None, active=None, chapters=None, chapter_id=None,
            mock_exam=None, active_mock=None, subactive=None):
    """The navigation drawer: all subjects, then this subject's pages/chapters.

    Modelled on the AI-Course book sidebar - a grouped table of contents that
    is always on screen on a desktop and slides in behind a ☰ button on a phone.
    """
    home = href_to(root, "index.html")
    progress = ""
    if subject and chapters is not None:
        progress = (
            '<div class="progress-wrap">'
            '<div class="progress-label"><span>Chapters done</span>'
            f'<span data-subject-text="{html.escape(subject)}" data-total="{len(chapters)}">'
            f"0 of {len(chapters)}</span></div>"
            '<div class="bar"><span class="fill" '
            f'data-subject="{html.escape(subject)}" data-total="{len(chapters)}"></span></div>'
            "</div>"
        )

    bits = ['<div class="toc-group">All subjects</div>']
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

    on_centre = " is-on" if (active == "mock" and not mock_exam) else ""
    cur_centre = ' aria-current="page"' if (active == "mock" and not mock_exam) else ""
    bits.append('<div class="toc-group">Mock tests</div>')
    bits.append(
        f'<a class="toc-item{on_centre}" href="{href_to(root, "mock-test/index.html")}"{cur_centre}>'
        '<span class="toc-num">&#10003;</span>Mock test centre</a>'
    )

    mock_groups, mock_exams_list = get_mock_nav_data()
    sub_title_map = {
        "board": "Board exams",
        "school": "Class XI entrance",
        "diploma": "Polytechnic entrance",
        "scholarship": "Scholarships & coaching",
    }
    for grp in mock_groups:
        grp_exams = [e for e in mock_exams_list if e.get("group") == grp["id"]]
        if not grp_exams:
            continue
        stitle = sub_title_map.get(grp["id"], grp.get("title", ""))
        bits.append(f'<div class="toc-sub">{html.escape(stitle)}</div>')
        for e in grp_exams:
            eid = e["id"]
            on_e = " is-on" if mock_exam == eid else ""
            cur_e = ' aria-current="page"' if mock_exam == eid else ""
            badge = MOCK_BADGES.get(eid, e.get("code", "M")[:4].strip())
            ntitle = MOCK_NAV_TITLES.get(eid, e.get("title", eid).split(" — ")[0])
            url = href_to(root, f"mock-test/{eid}/index.html")
            bits.append(
                f'<a class="toc-item toc-ch{on_e}" href="{url}"{cur_e}>'
                f'<span class="toc-num">{html.escape(badge)}</span>{html.escape(ntitle)}</a>'
            )

    on = " is-on" if (active == "admissions" and subactive != "report") else ""
    cur = ' aria-current="page"' if (active == "admissions" and subactive != "report") else ""
    bits.append('<div class="toc-group">Beyond Class 10</div>')
    bits.append(
        f'<a class="toc-item{on}" href="{href_to(root, "after-10th/index.html")}"{cur}>'
        '<span class="toc-num">XI</span>Admissions &amp; scholarships</a>'
    )
    if active == "admissions":
        on_rep = " is-on" if subactive == "report" else ""
        cur_rep = ' aria-current="page"' if subactive == "report" else ""
        bits.append(
            f'<a class="toc-item toc-ch{on_rep}" href="{href_to(root, "after-10th/report.html")}"{cur_rep}>'
            '<span class="toc-num">&#128269;</span>Daily watch report</a>'
        )

    on = " is-on" if active == "pw-nsat" else ""
    cur = ' aria-current="page"' if active == "pw-nsat" else ""
    bits.append('<div class="toc-group">Scholarships &amp; coaching</div>')
    bits.append(
        f'<a class="toc-item{on}" href="{href_to(root, "pw-nsat/index.html")}"{cur}>'
        '<span class="toc-num">NSAT</span>PW NSAT</a>'
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
        subj_mocks = [e for e in mock_exams_list if e.get("subject") == subject]
        if len(subj_mocks) == 1:
            m_id = subj_mocks[0]["id"]
            bits.append(
                f'<a class="toc-item" href="{href_to(root, f"mock-test/{m_id}/index.html")}">'
                '<span class="toc-num">&#10003;</span>Mock test</a>'
            )
        elif len(subj_mocks) > 1:
            for sm in subj_mocks:
                sm_id = sm["id"]
                sname = "Course A" if sm_id == "hindi-a" else (
                    "Course B" if sm_id == "hindi-b" else sm["title"])
                bits.append(
                    f'<a class="toc-item" href="{href_to(root, f"mock-test/{sm_id}/index.html")}">'
                    f'<span class="toc-num">&#10003;</span>Mock test ({html.escape(sname)})</a>'
                )
        elif subject in NAV_MOCK:
            bits.append(
                f'<a class="toc-item" href="{href_to(root, f"mock-test/{NAV_MOCK[subject]}/index.html")}">'
                '<span class="toc-num">&#10003;</span>Mock test</a>'
            )

        if chapters is not None and subj:
            bits.append('<div class="toc-group">Chapters</div>')
            for unit in subj["units"]:
                chs = [c for c in chapters if c.get("unit") == unit["id"]]
                if not chs:
                    continue
                bits.append(f'<div class="toc-sub">{html.escape(unit["title"])}</div>')
                for c in chs:
                    on = " is-on" if c["id"] == chapter_id else ""
                    cur = ' aria-current="page"' if c["id"] == chapter_id else ""
                    url = href_to(root, subject + "/chapters/" + c["id"] + ".html")
                    bits.append(
                        f'<a class="toc-item toc-ch{on}" href="{url}"{cur}>'
                        f'<span class="toc-num">{c["num"]}</span>'
                        f'{html.escape(c["title"])}</a>'
                    )

    if mock_exam:
        exam = next((e for e in mock_exams_list if e["id"] == mock_exam), None)
        if exam:
            exam_title = MOCK_NAV_TITLES.get(
                mock_exam, exam.get("title", mock_exam).split(" — ")[0])
            bits.append(f'<div class="toc-group">{html.escape(exam_title)}</div>')
            on_pat = " is-on" if active_mock == "exam" else ""
            cur_pat = ' aria-current="page"' if active_mock == "exam" else ""
            bits.append(
                f'<a class="toc-item{on_pat}" href="{href_to(root, f"mock-test/{mock_exam}/index.html")}"{cur_pat}>'
                '<span class="toc-num">&bull;</span>Pattern &amp; 10 mocks</a>'
            )
            on_test = " is-on" if active_mock == "test" else ""
            cur_test = ' aria-current="page"' if active_mock == "test" else ""
            bits.append(
                f'<a class="toc-item{on_test}" href="{href_to(root, f"mock-test/{mock_exam}/test.html?n=1")}"{cur_test}>'
                '<span class="toc-num">&#9654;</span>Take online mock test</a>'
            )
            if exam.get("chapters_data"):
                bits.append(
                    f'<div class="toc-sub">Chapter mocks ({len(exam["chapters_data"])})</div>')
                for c in exam["chapters_data"]:
                    url = href_to(root, f"mock-test/{mock_exam}/test.html?chapter={c['id']}")
                    bits.append(
                        f'<a class="toc-item toc-ch" href="{url}">'
                        f'<span class="toc-num">{c["num"]}</span>{html.escape(c["title"])}</a>'
                    )
            if exam.get("subject"):
                exam_subj = exam["subject"]
                s = next((x for x in NAV_SUBJECTS if x["slug"] == exam_subj), None)
                stitle = s["title"] if s else exam_subj.title()
                bits.append(
                    f'<a class="toc-item" href="{href_to(root, f"{exam_subj}/index.html")}">'
                    f'<span class="toc-num">&larr;</span>{html.escape(stitle)} study hub</a>'
                )
            if exam.get("admission_id"):
                exam_adm = exam["admission_id"]
                bits.append(
                    f'<a class="toc-item" href="{href_to(root, f"after-10th/index.html#{exam_adm}")}">'
                    '<span class="toc-num">&larr;</span>Admission details</a>'
                )
            if mock_exam == "pw-nsat":
                bits.append(
                    f'<a class="toc-item" href="{href_to(root, "pw-nsat/index.html")}">'
                    '<span class="toc-num">&larr;</span>PW NSAT hub</a>'
                )

    return render("navigation.html", HOME=home, SESSION=SESSION,
                  PROGRESS=progress, GROUPS="\n".join(bits),
                  CREDIT=html.escape(CREDIT))


# --------------------------------------------------------------------------
# footer
# --------------------------------------------------------------------------
def footer(root):
    subj_links = " ".join(
        f'<a href="{href_to(root, s["slug"] + "/index.html")}">{html.escape(s["title"])}</a>'
        if s["slug"] not in NAV_PENDING
        else f'<span class="foot-off">{html.escape(s["title"])}</span>'
        for s in NAV_SUBJECTS
    )
    mock_links = " ".join(
        f'<a href="{href_to(root, f"mock-test/{eid}/index.html")}">'
        f'{html.escape(MOCK_NAV_TITLES.get(eid, eid))}</a>'
        for eid in ["maths", "science", "social-science", "english", "hindi-a",
                    "hindi-b", "information-technology", "computer-applications",
                    "sanskrit"]
    )
    subject_nav = (f'<nav class="foot-subj" aria-label="All subjects">{subj_links}</nav>'
                   if subj_links else "")
    mock_nav = (
        f'<nav class="foot-subj foot-mocks" aria-label="Mock tests">'
        f'<a href="{href_to(root, "mock-test/index.html")}"><strong>Mock tests:</strong></a> '
        f'{mock_links} '
        f'<a href="{href_to(root, "after-10th/index.html")}">Admissions &amp; scholarships</a> '
        f'<a href="{href_to(root, "pw-nsat/index.html")}">PW NSAT</a></nav>'
    )
    return render("footer.html", SESSION=SESSION, SUBJECT_LINKS=subject_nav,
                  MOCK_LINKS=mock_nav, CREDIT=html.escape(CREDIT))


# --------------------------------------------------------------------------
# page shell
# --------------------------------------------------------------------------
def page(title, crumbs, body, root="..", subject=None, active=None,
         chapters=None, chapter_id=None, mock_exam=None, active_mock=None,
         subactive=None, lang="en", path=None):
    """Assemble one page from the partials in site/partials/.

    `path` is the page's site-relative output path (e.g. "maths/index.html");
    it drives the canonical and Open Graph URLs. `lang` is the BCP-47 language
    of the content.
    """
    esc_title = html.escape(title)
    description = html.escape(
        f"CBSE Class 10 {title} \u2014 chapter notes, formulas, exam Q&A and revision.")
    canonical = f"{SITE_URL}/{path}" if path else f"{SITE_URL}/"
    head = render("head.html", TITLE=esc_title, DESCRIPTION=description,
                  ROOT=root, CANONICAL=canonical, SITE_URL=SITE_URL)
    crumb_html = ' <span class="sep">/</span> '.join(
        f'<a href="{url}">{html.escape(label)}</a>' if url else html.escape(label)
        for label, url in crumbs
    )
    navigation = sidebar(root, subject, active, chapters, chapter_id,
                         mock_exam, active_mock, subactive)
    scripts = f'<script src="{href_to(root, "assets/js/app.js")}"></script>'
    return render(
        "page.html",
        LANG=lang,
        HEAD=head,
        HEADER=render("header.html"),
        NAVIGATION=navigation,
        CRUMBS=crumb_html,
        BODY=body,
        FOOTER=footer(root),
        SCRIPTS=scripts,
    )


def not_found(base=BASE):
    """A self-contained 404 page.

    GitHub Pages answers every unknown path with this file, so the stylesheet
    and the links have to be absolute under the published base path.
    """
    return render("notfound.html", BASE=base, CREDIT=html.escape(CREDIT))
