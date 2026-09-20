"""Mock tests: a live question generator for every exam listed in the repo.

Clicking a mock generates a fresh paper in the browser from the site's own
banks — the chapter MCQs under site/content/chapters/ and the standalone
banks under site/content/banks/ — so nothing here is an official paper.
The blueprints live in site/content/mock-tests.json: one entry per exam with
`tests` mock slots and sections that say how many questions to draw from
which pool.

Every attempt picks questions the student has not been served before (tracked
in the browser's localStorage) and cycles only when a pool runs out, so two
attempts never show the same batch while the pool allows it. Each board
subject also gets a chapter-wise mock for every chapter that has MCQs.

Pages written (relative to the site root):

    mock-test/index.html           the centre: every exam, recent attempts
    mock-test/<exam>/index.html    pattern, the 10 mocks, chapter mocks
    mock-test/<exam>/test.html     the engine page: ?n=<mock number> for a
                                   full mock or ?chapter=<id> for a chapter
                                   mock — test screen, one-page report,
                                   printable paper and .txt downloads are
                                   all generated live from the pool

The engine that runs everything in the browser is site/theme/mock.js.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

CONTENT = Path(__file__).resolve().parent / "content"

SITE_URL = "https://clickalex.github.io/Class10CBSE"

# Option labels used by the banks: Latin for most subjects, Devanagari for
# Hindi and Sanskrit. A question uses exactly one of the two sets.
LABEL_SETS = ("abcd", "कखगघ")
OPT_RE = re.compile(r"\s*\(([a-dकखगघ])\)\s*")
ANS_RE = re.compile(r"^\s*\*\*\s*\(([a-dकखगघ])\)")

# A few MCQs per chapter are templated study-habit prompts ("the most
# exam-ready way to revise X is…"), not knowledge questions. They are useful
# on the practice page but have no place in a scored paper.
FILLER = (
    "exam-ready way to revise",
    "A 3-mark answer on",
    "का सबसे उपयोगी पुनरावलोकन",
    "इस पाठ का सार है",
)

# Literature questions often say "this poem" / "the narrator" / "कवि ने";
# outside their chapter page they need the lesson named, so questions from
# these subjects carry the chapter title as context on every screen and paper.
CONTEXT_SUBJECTS = {"english", "hindi", "sanskrit"}


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------
def is_filler(mcq) -> bool:
    stem = str(mcq.get("q", ""))
    return any(mark in stem for mark in FILLER)


def parse_mcq(mcq):
    """Split a bank MCQ into stem, four options and the key.

    Bank format: ``"q": "Stem (a) one (b) two (c) three (d) four"`` and
    ``"a": "**(b) two.** why"``. Returns None when the text does not fit.
    """
    q = str(mcq.get("q", ""))
    a = str(mcq.get("a", ""))
    parts = OPT_RE.split(q)
    # parts = [stem, label, text, label, text, ...]
    if len(parts) != 9:
        return None
    stem = parts[0].strip()
    labels = parts[1::2]
    options = [p.strip() for p in parts[2::2]]
    if not stem or any(not o for o in options):
        return None
    if list(labels) not in [list(s) for s in LABEL_SETS]:
        return None
    m = ANS_RE.match(a)
    if not m or m.group(1) not in labels:
        return None
    return {
        "stem": stem,
        "options": options,
        "labels": list(labels),
        "answer": labels.index(m.group(1)),
        "explanation": a.strip(),
    }


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------
def load_config():
    with open(CONTENT / "mock-tests.json", encoding="utf-8") as fh:
        return json.load(fh)


def load_banks():
    """Standalone banks (e.g. Mental Ability): {id: bank dict}."""
    banks = {}
    folder = CONTENT / "banks"
    if not folder.is_dir():
        return banks
    for path in sorted(folder.glob("*.json")):
        with open(path, encoding="utf-8") as fh:
            bank = json.load(fh)
        banks[bank["id"]] = bank
    return banks


def chapter_questions(subject, chapter):
    """Parsed, non-filler MCQs of one chapter, tagged for the report."""
    out = []
    for i, m in enumerate(chapter.get("mcq") or []):
        if is_filler(m):
            continue
        p = parse_mcq(m)
        if not p:
            continue
        p.update(
            uid=f"{subject['slug']}:{chapter['id']}:{i}",
            subject=subject["slug"],
            subject_title=subject["title"],
            group_key=f"{subject['slug']}/{chapter['id']}",
            group_title=f"Ch {chapter['num']} · {chapter['title']}",
            group_order=chapter["num"],
            chapter_id=chapter["id"],
            chapter_num=chapter["num"],
            chapter_title=chapter["title"],
            chapter_url=f"{subject['slug']}/chapters/{chapter['id']}.html",
            practice_url=f"{subject['slug']}/practice/{chapter['id']}.html",
            context=chapter["title"] if subject["slug"] in CONTEXT_SUBJECTS else "",
        )
        out.append(p)
    return out


def bank_questions(bank):
    out = []
    for gi, grp in enumerate(bank.get("groups") or []):
        for i, m in enumerate(grp.get("mcq") or []):
            p = parse_mcq(m)
            if not p:
                continue
            p.update(
                uid=f"bank:{bank['id']}:{grp['id']}:{i}",
                subject=f"bank:{bank['id']}",
                subject_title=bank["title"],
                group_key=f"bank:{bank['id']}/{grp['id']}",
                group_title=grp["title"],
                group_order=gi + 1,
                chapter_id=None,
                chapter_num=None,
                chapter_title=None,
                chapter_url=None,
                practice_url=None,
                context="",
            )
            out.append(p)
    return out


def _pool_questions(spec, subjects_by_slug, chapters_by_subject, banks):
    if "bank" in spec:
        bank = banks.get(spec["bank"])
        if bank is None:
            raise ValueError(f"mock-tests: unknown bank '{spec['bank']}'")
        return bank_questions(bank)
    subj = subjects_by_slug.get(spec.get("subject"))
    if subj is None:
        raise ValueError(f"mock-tests: unknown subject '{spec.get('subject')}'")
    chapters = chapters_by_subject.get(subj["slug"]) or []
    units = set(spec.get("units") or [])
    ids = set(spec.get("chapters") or [])
    out = []
    for ch in chapters:
        if units and ch.get("unit") not in units:
            continue
        if ids and ch["id"] not in ids:
            continue
        out.extend(chapter_questions(subj, ch))
    if not out:
        raise ValueError(f"mock-tests: pool {spec} has no questions")
    return out


# --------------------------------------------------------------------------
# pool assembly (per exam; the paper itself is generated in the browser)
# --------------------------------------------------------------------------
def assemble(config, subjects, chapters_by_subject, banks):
    """Return the exams with their pools.

    Each exam gains:
      ``sections_data``  list of {name, count, questions} — the pool each
                         section draws from (validated: pool >= count);
      ``pool_data``      {uid: question} — everything embedded in the page
                         (a whole subject for board exams, the union of the
                         section pools for entrance exams);
      ``chapters_data``  mockable chapters with their question counts
                         (board subjects only);
      ``stats``          sizes for the build report.
    """
    subjects_by_slug = {s["slug"]: s for s in subjects}
    exams = []
    for exam in config["exams"]:
        total = sum(sec["count"] for sec in exam["sections"])
        if total != exam["questions"]:
            raise ValueError(
                f"mock-tests/{exam['id']}: section counts add up to {total}, "
                f"not {exam['questions']}"
            )

        sections_data = []
        for sec in exam["sections"]:
            qs = {}
            for spec in sec["pools"]:
                for q in _pool_questions(spec, subjects_by_slug, chapters_by_subject, banks):
                    qs[q["uid"]] = q
            if len(qs) < sec["count"]:
                raise ValueError(
                    f"mock-tests/{exam['id']} section '{sec['name']}': needs "
                    f"{sec['count']} questions, pool has {len(qs)}"
                )
            sections_data.append({"name": sec["name"], "count": sec["count"], "questions": qs})

        # The embedded pool is the union of the section pools: for a board
        # subject that is every chapter its blueprint draws on (Course A and
        # Course B pages each carry their own chapters), for an entrance exam
        # the subjects it tests.
        pool = {}
        for sd in sections_data:
            pool.update(sd["questions"])
        if not pool:
            raise ValueError(f"mock-tests/{exam['id']}: empty pool")

        # chapters with at least one question in the pool get a chapter mock
        chapters_data = []
        if exam.get("subject"):
            for ch in chapters_by_subject.get(exam["subject"]) or []:
                n = sum(1 for q in pool.values() if q["chapter_id"] == ch["id"])
                if n:
                    chapters_data.append(
                        {"id": ch["id"], "num": ch["num"], "title": ch["title"], "n": n}
                    )

        e = dict(exam)
        e["sections_data"] = sections_data
        e["pool_data"] = pool
        e["chapters_data"] = chapters_data
        e["stats"] = {
            "pool": len(pool),
            "sections": {sd["name"]: len(sd["questions"]) for sd in sections_data},
            "chapters": len(chapters_data),
        }
        exams.append(e)
    return exams


# --------------------------------------------------------------------------
# rendering helpers
# --------------------------------------------------------------------------
def esc(s) -> str:
    return html.escape(str(s), quote=True)


def marking_text(exam) -> str:
    mc, mw = exam["marks_correct"], exam["marks_wrong"]
    plus = f"+{mc} correct"
    minus = f"−{mw} wrong" if mw else "no negative marking"
    return f"{plus} · {minus}"


def max_marks(exam) -> int:
    return exam["questions"] * exam["marks_correct"]


def minutes_text(m) -> str:
    h, r = divmod(int(m), 60)
    if h and r:
        return f"{h} h {r} min"
    if h:
        return f"{h} h"
    return f"{r} min"


def pattern_chips(exam) -> str:
    return (
        '<p class="mock-pattern">'
        f'<span>{exam["questions"]} questions</span>'
        f'<span>{minutes_text(exam["minutes"])}</span>'
        f'<span>Max {max_marks(exam)} marks</span>'
        f'<span>{esc(marking_text(exam))}</span>'
        f'<span>{esc(exam.get("length", "Mock"))}</span>'
        "</p>"
    )


def sections_table(exam, subjects=()) -> str:
    by_slug = {s["slug"]: s for s in subjects}
    rows = []
    for sec in exam["sections"]:
        srcs = []
        for spec in sec["pools"]:
            if "bank" in spec:
                srcs.append(spec["bank"].replace("-", " ").title() + " bank")
                continue
            subj = by_slug.get(spec["subject"])
            label = subj["title"] if subj else spec["subject"]
            if spec.get("units"):
                names = {
                    u["id"]: u.get("title") or u.get("name") or u["id"]
                    for u in (subj or {}).get("units", [])
                }
                # "Unit III · Natural Phenomena" -> "Natural Phenomena"
                pretty = [names.get(u, u).split(" · ")[-1] for u in spec["units"]]
                label += ": " + ", ".join(pretty)
            srcs.append(label)
        rows.append(
            f"<tr><td>{esc(sec['name'])}</td><td>{sec['count']}</td>"
            f"<td>{sec['count'] * exam['marks_correct']}</td><td>{esc('; '.join(srcs))}</td></tr>"
        )
    return (
        '<div class="tablewrap"><table><thead><tr><th>Section</th><th>Questions</th>'
        "<th>Marks</th><th>Drawn from</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _json_for_script(data) -> str:
    # "</script>" inside a JSON string would end the block early.
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def question_fields(q, inline, root):
    """The client-side form of one question (HTML-rendered, compact keys)."""
    return {
        "uid": q["uid"],
        "s": inline(q["stem"]),
        "o": [inline(o) for o in q["options"]],
        "l": q["labels"],
        "a": q["answer"],
        "e": inline(q["explanation"]),
        "t": q["group_title"],
        "k": q["group_key"],
        "c": inline(q["context"]) if q.get("context") else "",
        "src": q["subject_title"],
        "u": f"{root}/{q['chapter_url']}" if q.get("chapter_url") else None,
        "p": f"{root}/{q['practice_url']}" if q.get("practice_url") else None,
        "ord": q["group_order"],
        "ch": q.get("chapter_id"),
    }


def engine_payload(exam, inline, root):
    """Everything test.html needs: exam meta, section pools, the pool itself
    and the mockable chapter list."""
    pool = exam["pool_data"]
    sections = []
    for sd in exam["sections_data"]:
        ids = sorted(
            sd["questions"], key=lambda u: (sd["questions"][u]["group_order"], u)
        )
        sections.append({"name": sd["name"], "count": sd["count"], "ids": ids})
    return {
        "exam": {
            "id": exam["id"],
            "title": exam["title"],
            "code": exam.get("code", ""),
            "group": exam["group"],
            "tests": exam.get("tests", 10),
            "minutes": exam["minutes"],
            "marksCorrect": exam["marks_correct"],
            "marksWrong": exam["marks_wrong"],
            "questions": exam["questions"],
            "length": exam.get("length", ""),
            "patternNote": exam.get("pattern_note", ""),
            "subject": exam.get("subject") or "",
            "siteUrl": SITE_URL,
        },
        "sections": sections,
        "pool": [question_fields(pool[u], inline, root) for u in sorted(pool)],
        "chapters": exam["chapters_data"],
    }


# --------------------------------------------------------------------------
# page bodies
# --------------------------------------------------------------------------
def centre_body(config, exams, subjects):
    """mock-test/index.html — every exam with recent attempts."""
    total_slots = sum(e.get("tests", 10) for e in exams)
    unique_q = len({q["uid"] for e in exams for q in e["pool_data"].values()})
    n_chapters = sum(e["stats"]["chapters"] for e in exams if e["chapters_data"])

    group_html = []
    for grp in config["groups"]:
        cards = []
        for e in exams:
            if e["group"] != grp["id"]:
                continue
            ch_note = (
                f"<p class='mock-meta'>{e['stats']['chapters']} chapter-wise mocks</p>"
                if e["chapters_data"]
                else ""
            )
            cards.append(
                f'<article class="mock-card" id="{esc(e["id"])}">'
                f'<p class="sc-code">{esc(e.get("code", ""))} · {esc(e.get("length", "Mock"))}</p>'
                f'<h3><a href="{e["id"]}/index.html">{esc(e["title"])}</a></h3>'
                f'<p class="sc-desc">{esc(e.get("short", ""))}</p>'
                f'<p class="mock-meta">{e["questions"]} Qs · {minutes_text(e["minutes"])} · '
                f'{esc(marking_text(e))}</p>'
                f'<p class="mock-meta">Pool of {e["stats"]["pool"]} questions · {e.get("tests", 10)} mocks</p>'
                f"{ch_note}"
                f'<p class="mock-best" data-mock-best="{esc(e["id"])}">No attempt yet on this device.</p>'
                f'<p class="btnrow"><a class="btn primary" href="{e["id"]}/test.html?n=1">Start a mock →</a>'
                f'<a class="btn" href="{e["id"]}/index.html">Details &amp; chapters</a></p>'
                "</article>"
            )
        if not cards:
            continue
        group_html.append(
            f'<section id="{esc(grp["id"])}"><h2>{esc(grp["title"])} ({len(cards)})</h2>'
            f'<p>{esc(grp["intro"])}</p><div class="mock-grid">{"".join(cards)}</div></section>'
        )

    no_test = "".join(
        f'<li><a href="../after-10th/index.html#{esc(x["admission_id"])}">{esc(x["title"])}</a> — {esc(x["why"])}.</li>'
        for x in config.get("no_test", [])
    )
    nav = " · ".join(
        f'<a href="#{esc(g["id"])}">{esc(g["title"])}</a>' for g in config["groups"]
    )
    body = f"""
<p class="kicker">MOCK TESTS · CHECK YOUR OWN SCORE ONLINE</p>
<h1>Mock test centre</h1>
<p class="lede">{len(exams)} exams · {total_slots} mock tests · {n_chapters} chapter-wise mocks — every subject and every
entrance or scholarship test listed in this repository. <strong>Every attempt generates a fresh paper</strong> from the site's
question pool: take a mock online with a timer, get an instant <strong>one-page score report</strong>, and download the same paper
with its key to attempt on paper.</p>
<nav aria-label="Exam groups"><p>{nav} · <a href="#how">How it works</a></p></nav>
<div class="mock-recent" data-mock-recent hidden>
<h2>Your recent attempts</h2>
<div class="tablewrap"><table><thead><tr><th>When</th><th>Exam</th><th>Paper</th><th>Score</th><th>%</th><th>Time</th><th></th></tr></thead>
<tbody data-mock-recent-rows></tbody></table></div>
<p class="hint">Attempts are saved only in this browser (localStorage). <button type="button" class="btn" data-mock-clear>Clear history</button></p>
</div>
{"".join(group_html)}
<h2>Listed routes without an entrance test</h2>
<p>These options from the <a href="../after-10th/index.html">After 10th directory</a> select by merit or
counselling, so there is nothing to mock:</p>
<ul>{no_test}</ul>
<h2 id="how">How it works</h2>
<ol class="order">
<li><strong>A question generator, not a fixed paper</strong> — every mock is put together when you click it: each section draws its questions from the pool at random, avoiding the questions you were already served on this device. Two attempts get different papers until the pool cycles; the shuffle and the anti-repeat memory live in your browser.</li>
<li><strong>10 mocks per exam</strong> — every exam has ten numbered mock slots (Mock 1–10), each generating a fresh paper every time. Board subjects also have a chapter-wise mock for every chapter with MCQs.</li>
<li><strong>Online test</strong> — a countdown timer, one question at a time, a palette to jump around, mark-for-review, and auto-submit when time runs out. Progress survives a page reload.</li>
<li><strong>Instant score + one-page report</strong> — marks, percentage, accuracy, negative-marking loss, section-wise and chapter-wise breakdown, and the chapters to revise, each linked to its study page. Print it or save it as a single-A4 PDF, download it as text, or review every question with its explanation.</li>
<li><strong>Download the paper</strong> — the same generated paper can be printed (Save as PDF from the print dialog, with an OMR grid and an optional key page) or downloaded as plain text with a separate key file.</li>
</ol>
<div class="callout alt"><p>All questions are the site's own study material drawn from the chapter banks — the same
{unique_q} questions you can already practise chapter by chapter — plus an original Mental Ability bank. They are
<strong>not</strong> official CBSE, NVS, JMI, AMU, BHU, JEECUP, BCECEB, PW, ALLEN, Aakash or VMC papers, and the
entrance-test patterns are practice approximations: confirm the current official brochure before the real exam.</p></div>
<script src="../assets/mock.js"></script>
"""
    return [("Home", "../index.html"), ("Mock tests", None)], body


def exam_body(exam, admissions, subjects):
    """mock-test/<exam>/index.html — pattern, the 10 mocks, chapter mocks."""
    subj = next((s for s in subjects if s["slug"] == exam.get("subject")), None)
    inst = next((i for i in admissions if i["id"] == exam.get("admission_id")), None)
    tests = exam.get("tests", 10)

    slot_cards = "".join(
        f'<article class="slot-card">'
        f"<h3>Mock {n}</h3>"
        f'<p class="slot-meta">{exam["questions"]} Qs \u00b7 {minutes_text(exam["minutes"])} \u00b7 Max {max_marks(exam)}</p>'
        f'<p class="slot-best" data-mock-slot-best="{esc(exam["id"])}/{n}">No attempt yet</p>'
        f'<a class="btn primary" href="test.html?n={n}">Take online \u2192</a>'
        "</article>"
        for n in range(1, tests + 1)
    )

    chapter_html = ""
    if exam["chapters_data"]:
        chips = " ".join(
            f'<a class="chip" href="test.html?chapter={esc(c["id"])}" title="{esc(c["n"])} questions">'
            f"Ch {c['num']} · {esc(c['title'])} <span class='chip-n'>{c['n']}</span></a>"
            for c in exam["chapters_data"]
        )
        chapter_html = f"""
<h2>Chapter-wise mock tests · {len(exam["chapters_data"])}</h2>
<p>A quick scored mock on one chapter — every MCQ of that chapter, +1 per correct answer, no negative marking,
about a minute per question. Each attempt reshuffles the order and refreshes the questions.</p>
<p class="chips mock-chapters">{chips}</p>
"""

    links = []
    if subj:
        links.append(f'<a href="../../{subj["slug"]}/index.html">{esc(subj["title"])} hub</a>')
        links.append(f'<a href="../../{subj["slug"]}/drill.html">MCQ drill (all chapters, untimed)</a>')
        links.append(f'<a href="../../{subj["slug"]}/revision.html">Quick revision</a>')
        links.append('<a href="https://cbseacademic.nic.in/">CBSE Academic — official sample question papers and marking schemes (Class X)</a>')
    if inst:
        for i, url in enumerate(inst["sources"], 1):
            links.append(f'<a href="{esc(url)}">Official source {i}: {esc(url)}</a>')
        links.append(f'<a href="../../after-10th/index.html#{esc(inst["id"])}">Directory entry — eligibility, cycle, what to verify</a>')
    if exam["id"] == "pw-nsat":
        links.append('<a href="../../pw-nsat/index.html">PW NSAT hub — dated official-page snapshot</a>')
    if exam["id"] in ("hindi-a", "hindi-b"):
        other = "hindi-b" if exam["id"] == "hindi-a" else "hindi-a"
        links.append(f'<a href="../{other}/index.html">Studying the other course? Open the Hindi Course {"B" if other == "hindi-b" else "A"} mock</a>')

    sources = []
    for sec in exam["sections"]:
        for spec in sec["pools"]:
            if "bank" in spec:
                sources.append("the original Mental Ability bank")
            else:
                s = next((x for x in subjects if x["slug"] == spec["subject"]), None)
                if s:
                    sources.append(f"the {s['title']} chapter banks")
    src_text = ", ".join(dict.fromkeys(sources))

    negative = ""
    if exam["marks_wrong"]:
        negative = (
            f"<p><strong>Negative marking:</strong> every wrong answer costs {exam['marks_wrong']} mark"
            f"{'s' if exam['marks_wrong'] != 1 else ''}. Leave a question blank when you are guessing between "
            "three or four options; attempt it when you can eliminate two.</p>"
        )
    body = f"""
<p class="kicker">MOCK TEST · {esc(exam.get("code", ""))}</p>
<h1>{esc(exam["title"])} — mock tests</h1>
<p class="lede">{esc(exam.get("short", ""))} {tests} mocks, and each one is <strong>generated fresh from a pool of
{exam["stats"]["pool"]} questions</strong> when you click it. Take one online for an instant score and a one-page
report, or download the same paper with its key.</p>
{pattern_chips(exam)}
<h2>Mock tests · {tests}</h2>
<div class="mock-slots">{slot_cards}</div>
<p class="hint">Each card generates a new paper on every attempt — the questions you get are picked to avoid the ones
you have already been served on this device. The <em>printable paper, the .txt paper and the key</em> are on the test
screen, made from the same generated paper.</p>
{chapter_html}
<h2>Pattern used in this mock</h2>
<p>{esc(exam.get("pattern_note", ""))}</p>
{negative}
{sections_table(exam, subjects)}
<p class="hint">Questions are drawn from {esc(src_text)} on this site. The generator lives in your browser —
nothing is sent anywhere.</p>
<h2>Your attempts on this device</h2>
<div data-mock-attempts="{esc(exam["id"])}"><p class="hint">No attempts saved yet. Scores are stored only in this browser.</p></div>
<h2>Official material &amp; related pages</h2>
<ul>{"".join(f"<li>{l}</li>" for l in links)}</ul>
<div class="callout alt"><p>These mocks are original practice material built from the site's question banks — not an official
paper, and not a prediction. Entrance-test patterns above are practice approximations; verify the current official brochure.</p></div>
<p><a class="btn" href="../index.html">← All mock tests</a></p>
<script src="../../assets/mock.js"></script>
"""
    crumbs = [("Home", "../../index.html"), ("Mock tests", "../index.html"), (exam["title"], None)]
    return crumbs, body


def test_body(exam, group_title, payload):
    """mock-test/<exam>/test.html — the engine page; mock.js does the rest."""
    sec_rows = "".join(
        f"<tr><td>{esc(s['name'])}</td><td>{s['count']}</td><td>{s['count'] * exam['marks_correct']}</td></tr>"
        for s in exam["sections"]
    )
    tests = exam.get("tests", 10)
    body = f"""
<p class="kicker">MOCK TEST · {esc(group_title)}</p>
<h1>{esc(exam["title"])} <span data-mock-h1>— mock test</span></h1>
<p class="lede" data-mock-lede>Putting your paper together…</p>
<p class="chips" data-mock-slots></p>
<div class="mock-app" id="mock">

  <section class="mock-view" data-view="intro">
    {pattern_chips(exam)}
    <div class="tablewrap"><table><thead><tr><th>Section</th><th>Questions</th><th>Marks</th></tr></thead>
    <tbody>{sec_rows}</tbody></table></div>
    <div class="mock-instructions">
      <h2>Instructions</h2>
      <ol>
        <li><strong>This paper was generated just now</strong> from the site's question pool — it avoids the questions you were already served on this device, so every attempt is a different paper. Press <em>New questions</em> for another one before you start.</li>
        <li>The timer starts when you press <strong>Start test</strong> and the test submits itself at zero.</li>
        <li>Each question has one correct option. {esc(marking_text(exam))}; unattempted questions score 0.</li>
        <li>Use the palette to jump between questions; <em>Mark for review</em> only colours the palette, it does not affect the score.</li>
        <li>Your answers are kept in this browser while the test runs, so an accidental reload does not lose them.</li>
        <li>After submitting you get a one-page report (print or save as PDF), a text download and a full answer review.</li>
      </ol>
    </div>
    <p class="mock-fresh" data-mock-fresh></p>
    <p class="mock-name"><label>Name for the report (optional) <input type="text" data-mock-name maxlength="60" placeholder="Your name"></label></p>
    <p class="btnrow">
      <button type="button" class="btn primary" data-mock-start>Start test →</button>
      <button type="button" class="btn" data-act="regen">↻ New questions</button>
      <button type="button" class="btn" data-act="paper">Printable paper / PDF</button>
      <button type="button" class="btn" data-act="txt-paper">Download paper (.txt)</button>
      <button type="button" class="btn" data-act="txt-key">Answer key (.txt)</button>
    </p>
    <div data-mock-last hidden></div>
    <p class="hint">Original practice material built from this site's question banks — not an official paper.</p>
    <noscript><div class="callout"><p>This screen needs JavaScript to generate and score the paper — use the
    subject drill pages for untimed practice without it.</p></div></noscript>
  </section>

  <section class="mock-view" data-view="test" hidden>
    <div class="mock-bar">
      <span class="mock-timer" data-mock-timer aria-live="polite">--:--</span>
      <span class="mock-progress" data-mock-progress></span>
      <span class="mock-section" data-mock-section></span>
      <button type="button" class="btn primary mock-submit" data-mock-submit>Submit test</button>
    </div>
    <div class="mock-body">
      <div class="mock-q" data-mock-question></div>
      <aside class="mock-palette">
        <p class="mock-palette-head">Questions</p>
        <div class="mock-pal-grid" data-mock-palette></div>
        <p class="mock-legend"><span class="pal-btn is-answered">1</span> answered
          <span class="pal-btn is-marked">2</span> marked <span class="pal-btn">3</span> not answered</p>
      </aside>
    </div>
  </section>

  <section class="mock-view mock-report" id="report" data-view="report" hidden></section>

  <section class="mock-view" data-view="review" hidden>
    <div class="mock-review-bar">
      <button type="button" class="btn" data-mock-back-report>← Back to report</button>
      <span class="qfilters">
        <button type="button" class="qfilter is-on" data-mock-filter="all">All</button>
        <button type="button" class="qfilter" data-mock-filter="wrong">Wrong</button>
        <button type="button" class="qfilter" data-mock-filter="skipped">Skipped</button>
        <button type="button" class="qfilter" data-mock-filter="correct">Correct</button>
      </span>
    </div>
    <div class="qstack" data-mock-review></div>
  </section>

  <section class="mock-view" data-view="paper" hidden>
    <div class="paper" data-paper>
      <div class="paper-tools no-print" data-paper-tools></div>
      <div data-paper-body></div>
    </div>
  </section>

</div>
<p class="btnrow mock-foot"><a class="btn" href="index.html">← {esc(exam["title"])} mocks</a> <a class="btn" href="../index.html">All mock tests</a></p>
<script type="application/json" id="mock-data">{_json_for_script(payload)}</script>
<script src="../../assets/mock.js"></script>
"""
    crumbs = [
        ("Home", "../../index.html"),
        ("Mock tests", "../index.html"),
        (exam["title"], "index.html"),
        ("Test", None),
    ]
    return crumbs, body


# --------------------------------------------------------------------------
# entry points used by build.py
# --------------------------------------------------------------------------
def prepare(subjects, chapters_by_subject):
    """Load the config and banks and assemble every pool. Returns (config, exams)."""
    config = load_config()
    banks = load_banks()
    exams = assemble(config, subjects, chapters_by_subject, banks)
    return config, exams


def mock_for_subject(exams):
    """{subject slug: exam id} for the sidebar / hub links (first exam wins)."""
    out = {}
    for e in exams:
        if e.get("subject") and e["subject"] not in out:
            out[e["subject"]] = e["id"]
    return out


def mock_chapter_hosts(exams):
    """{(subject slug, chapter id): exam id} — which exam page hosts each
    chapter mock (board subjects carry their whole subject as a pool)."""
    out = {}
    for e in exams:
        if not e.get("subject"):
            continue
        for c in e["chapters_data"]:
            out.setdefault((e["subject"], c["id"]), e["id"])
    return out


def build_mock_tests(dist, config, exams, subjects, admissions, page, write, inline):
    """Write every mock-test page. Returns the list of site-relative paths
    written (for the build report)."""
    written = []
    group_titles = {g["id"]: g["title"] for g in config["groups"]}

    crumbs, body = centre_body(config, exams, subjects)
    write(dist / "mock-test" / "index.html",
          page("Mock tests", crumbs, body, "..", None, "mock"))
    written.append("mock-test/index.html")

    for exam in exams:
        folder = dist / "mock-test" / exam["id"]
        crumbs, body = exam_body(exam, admissions, subjects)
        write(folder / "index.html",
              page(f"{exam['title']} — mock tests", crumbs, body, "../..", None, "mock"))
        written.append(f"mock-test/{exam['id']}/index.html")

        gtitle = group_titles.get(exam["group"], "Mock test")
        payload = engine_payload(exam, inline, "../..")
        crumbs, body = test_body(exam, gtitle, payload)
        write(folder / "test.html",
              page(f"{exam['title']} — mock test (generated)", crumbs, body, "../..", None, "mock"))
        written.append(f"mock-test/{exam['id']}/test.html")
    return written
