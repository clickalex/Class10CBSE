"""Mock tests: timed, auto-scored MCQ papers for every exam listed in the repo.

Content comes from the site's own banks — the chapter MCQs under
site/content/chapters/ and the standalone banks under site/content/banks/ —
so nothing here is an official paper. The blueprints live in
site/content/mock-tests.json: one entry per exam, each with sections that
say how many questions to draw from which pool.

Set assembly is deterministic (seeded by exam id) so a rebuild reproduces the
same papers: the printable paper, the .txt download and the online test for
"Set 2" are always the same 40 questions.

Pages written (relative to the site root):

    mock-test/index.html                 the centre: every exam, best scores
    mock-test/<exam>/index.html          pattern, sets, downloads, attempts
    mock-test/<exam>/set-N.html          the test screen + one-page report
    mock-test/<exam>/set-N-paper.html    printable paper (+ key) -> Save as PDF
    mock-test/<exam>/set-N.txt           plain-text paper
    mock-test/<exam>/set-N-key.txt       plain-text answer key

The engine that runs the test in the browser is site/theme/mock.js.
"""
from __future__ import annotations

import html
import json
import random
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


def plain(text: str) -> str:
    """Strip the bank's inline markup for the .txt downloads."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", str(text))
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


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
                chapter_url=None,
                practice_url=None,
                context="",
            )
            out.append(p)
    return out


# --------------------------------------------------------------------------
# set assembly
# --------------------------------------------------------------------------
class _Queue:
    """A shuffled, cyclic queue of one chapter's questions."""

    def __init__(self, items, rng):
        self.items = list(items)
        rng.shuffle(self.items)
        self.pos = 0

    def next_not_in(self, used, avoid=None):
        """Next question not in ``used`` (and, if given, not in ``avoid``)."""
        n = len(self.items)
        for k in range(n):
            q = self.items[(self.pos + k) % n]
            if q["uid"] in used or (avoid is not None and q["uid"] in avoid):
                continue
            self.pos = (self.pos + k + 1) % n
            return q
        return None


class Pool:
    """Questions grouped by chapter, drawn round-robin so every set covers
    the whole pool evenly. Cursors persist across sets, so Set 2 continues
    where Set 1 stopped. Questions never used in any earlier set are drawn
    first; a question repeats across sets only once every chapter in the
    pool has been exhausted."""

    def __init__(self, questions, seed):
        rng = random.Random(seed)
        groups = {}
        for q in questions:
            groups.setdefault(q["group_key"], []).append(q)
        keys = sorted(groups, key=lambda k: (groups[k][0]["subject"], groups[k][0]["group_order"]))
        self.queues = [_Queue(groups[k], rng) for k in keys]
        self.size = len(questions)
        self.rr = rng.randrange(len(self.queues)) if self.queues else 0

    def take(self, count, used, seen=None):
        """Draw ``count`` questions not in ``used`` (this set). ``seen`` holds
        uids used by earlier sets; they are drawn only when nothing fresh is
        left anywhere in the pool."""
        picked = []
        if not self.queues:
            return picked
        for avoid in ((seen or set()), None):
            misses = 0
            while len(picked) < count and misses < len(self.queues):
                queue = self.queues[self.rr % len(self.queues)]
                self.rr += 1
                q = queue.next_not_in(used, avoid)
                if q is None:
                    misses += 1
                    continue
                misses = 0
                picked.append(q)
                used.add(q["uid"])
            if len(picked) >= count:
                break
        return picked


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


def assemble(config, subjects, chapters_by_subject, banks):
    """Return the exams with their sets filled in.

    Each exam gains ``sets``: a list (one per set) of question dicts with
    ``n`` (1-based number), ``section`` (index) and the parsed fields; and
    ``stats``: pool sizes and how many questions had to repeat across sets.
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
        pools = {}
        pool_sizes = {}
        for si, sec in enumerate(exam["sections"]):
            qs = []
            for spec in sec["pools"]:
                qs.extend(_pool_questions(spec, subjects_by_slug, chapters_by_subject, banks))
            pools[si] = Pool(qs, seed=f"{exam['id']}::{sec['name']}")
            pool_sizes[sec["name"]] = len(qs)

        sets, seen_before, repeats = [], set(), 0
        for set_no in range(1, exam["sets"] + 1):
            used = set()
            paper = []
            for si, sec in enumerate(exam["sections"]):
                picked = pools[si].take(sec["count"], used, seen_before)
                if len(picked) < sec["count"]:
                    raise ValueError(
                        f"mock-tests/{exam['id']} set {set_no}: section "
                        f"'{sec['name']}' needs {sec['count']} questions, pool has {len(picked)}"
                    )
                picked.sort(key=lambda q: (q["subject"], q["group_order"], q["uid"]))
                for q in picked:
                    item = dict(q)
                    item["section"] = si
                    paper.append(item)
            for n, item in enumerate(paper, 1):
                item["n"] = n
                if item["uid"] in seen_before:
                    repeats += 1
                seen_before.add(item["uid"])
            sets.append(paper)

        e = dict(exam)
        e["sets_data"] = sets
        e["stats"] = {"pools": pool_sizes, "repeats": repeats}
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
                names = {u["id"]: u.get("title") or u.get("name") or u["id"] for u in (subj or {}).get("units", [])}
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


def question_payload(exam, set_no, paper, inline, root):
    """What mock.js needs: the questions with HTML-rendered text and links."""
    questions = []
    for q in paper:
        questions.append({
            "n": q["n"],
            "sec": q["section"],
            "ctx": inline(q["context"]) if q.get("context") else "",
            "stem": inline(q["stem"]),
            "opts": [inline(o) for o in q["options"]],
            "labels": q["labels"],
            "ans": q["answer"],
            "exp": inline(q["explanation"]),
            "topic": q["group_title"],
            "topicKey": q["group_key"],
            "src": q["subject_title"],
            "url": f"{root}/{q['chapter_url']}" if q["chapter_url"] else None,
            "practice": f"{root}/{q['practice_url']}" if q["practice_url"] else None,
        })
    return {
        "exam": {
            "id": exam["id"],
            "title": exam["title"],
            "code": exam.get("code", ""),
            "group": exam["group"],
            "set": set_no,
            "sets": exam["sets"],
            "minutes": exam["minutes"],
            "marksCorrect": exam["marks_correct"],
            "marksWrong": exam["marks_wrong"],
            "questions": exam["questions"],
            "length": exam.get("length", ""),
        },
        "sections": [{"name": s["name"], "count": s["count"]} for s in exam["sections"]],
        "questions": questions,
    }


# --------------------------------------------------------------------------
# page bodies
# --------------------------------------------------------------------------
def centre_body(config, exams, subjects):
    """mock-test/index.html — every exam with its sets and your best score."""
    subj_titles = {s["slug"]: s["title"] for s in subjects}
    total_sets = sum(e["sets"] for e in exams)
    total_q = sum(e["sets"] * e["questions"] for e in exams)
    unique_q = len({q["uid"] for e in exams for paper in e["sets_data"] for q in paper})

    group_html = []
    for grp in config["groups"]:
        cards = []
        for e in exams:
            if e["group"] != grp["id"]:
                continue
            set_links = " ".join(
                f'<a class="chip" href="{e["id"]}/set-{n}.html">Set {n}</a>'
                for n in range(1, e["sets"] + 1)
            )
            cards.append(
                f'<article class="mock-card" id="{esc(e["id"])}">'
                f'<p class="sc-code">{esc(e.get("code", ""))} · {esc(e.get("length", "Mock"))}</p>'
                f'<h3><a href="{e["id"]}/index.html">{esc(e["title"])}</a></h3>'
                f'<p class="sc-desc">{esc(e.get("short", ""))}</p>'
                f'<p class="mock-meta">{e["questions"]} Qs · {minutes_text(e["minutes"])} · '
                f'{esc(marking_text(e))}</p>'
                f'<p class="mock-best" data-mock-best="{esc(e["id"])}">No attempt yet on this device.</p>'
                f'<p class="chips">{set_links}</p>'
                f'<p class="btnrow"><a class="btn primary" href="{e["id"]}/set-1.html">Start Set 1 →</a>'
                f'<a class="btn" href="{e["id"]}/index.html">Details &amp; downloads</a></p>'
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
<p class="lede">{len(exams)} exams · {total_sets} sets · {total_q} questions ({unique_q} distinct) — every subject
and every entrance or scholarship test listed in this repository. Take a set online with a timer and get an
instant <strong>one-page score report</strong>, or download the paper and answer key to attempt it on paper.</p>
<nav aria-label="Exam groups"><p>{nav} · <a href="#how">How it works</a></p></nav>
<div class="mock-recent" data-mock-recent hidden>
<h2>Your recent attempts</h2>
<div class="tablewrap"><table><thead><tr><th>When</th><th>Exam</th><th>Set</th><th>Score</th><th>%</th><th>Time</th><th></th></tr></thead>
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
<li><strong>Online test</strong> — a countdown timer, one question at a time, a palette to jump around, mark-for-review, and auto-submit when time runs out. Progress survives a page reload.</li>
<li><strong>Instant score</strong> — marks, percentage, accuracy, section-wise and chapter-wise breakdown, and the chapters to revise, each linked to its study page.</li>
<li><strong>One-page report</strong> — print it or save it as a PDF (the print layout is a single A4 page), or download it as a text file. Review every question with its explanation.</li>
<li><strong>Download the paper</strong> — each set has a printable paper (Save as PDF from the print dialog, with or without the answer key), a plain-text paper and a plain-text key.</li>
<li><strong>Fixed sets</strong> — a set is always the same questions, so a paper you printed last week matches the online version and its key.</li>
</ol>
<div class="callout alt"><p>All questions are the site's own study material drawn from the chapter banks — the same
{unique_q} questions you can already practise chapter by chapter — plus an original Mental Ability bank. They are
<strong>not</strong> official CBSE, NVS, JMI, AMU, BHU, JEECUP, BCECEB, PW, ALLEN, Aakash or VMC papers, and the
entrance-test patterns are practice approximations: confirm the current official brochure before the real exam.</p></div>
<script src="../assets/mock.js"></script>
"""
    return [("Home", "../index.html"), ("Mock tests", None)], body


def exam_body(exam, admissions, subjects):
    """mock-test/<exam>/index.html — pattern, sets, downloads, attempts."""
    subj = next((s for s in subjects if s["slug"] == exam.get("subject")), None)
    inst = next((i for i in admissions if i["id"] == exam.get("admission_id")), None)

    set_rows = "".join(
        f'<tr><td>Set {n}</td><td>{exam["questions"]} Qs · {minutes_text(exam["minutes"])}</td>'
        f'<td><a class="btn primary" href="set-{n}.html">Take online →</a></td>'
        f'<td><a class="btn" href="set-{n}-paper.html">Printable / PDF</a> '
        f'<a class="btn" href="set-{n}.txt" download>Paper .txt</a> '
        f'<a class="btn" href="set-{n}-key.txt" download>Key .txt</a></td>'
        f'<td data-mock-set-best="{esc(exam["id"])}/{n}">—</td></tr>'
        for n in range(1, exam["sets"] + 1)
    )

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
<p class="lede">{esc(exam.get("short", ""))} {exam["sets"]} fixed sets. Take a set online for an instant score and
a one-page report, or download it as a printable paper.</p>
{pattern_chips(exam)}
<h2>Sets</h2>
<div class="tablewrap"><table><thead><tr><th>Set</th><th>Pattern</th><th>Online</th><th>Download</th><th>Your best</th></tr></thead>
<tbody>{set_rows}</tbody></table></div>
<p class="hint">“Printable / PDF” opens the paper in a print layout — choose <em>Save as PDF</em> in the print dialog. The
answer key prints on separate pages after the paper and can be switched off before printing.</p>
<h2>Pattern used in this mock</h2>
<p>{esc(exam.get("pattern_note", ""))}</p>
{negative}
{sections_table(exam, subjects)}
<p class="hint">Questions are drawn from {esc(src_text)} on this site. Each set is fixed: the same questions online, on paper and in the key.</p>
<h2>Your attempts on this device</h2>
<div data-mock-attempts="{esc(exam["id"])}"><p class="hint">No attempts saved yet. Scores are stored only in this browser.</p></div>
<h2>Official material &amp; related pages</h2>
<ul>{"".join(f"<li>{l}</li>" for l in links)}</ul>
<div class="callout alt"><p>These sets are original practice material built from the site's question banks — not an official
paper, and not a prediction. Entrance-test patterns above are practice approximations; verify the current official brochure.</p></div>
<p><a class="btn" href="../index.html">← All mock tests</a></p>
<script src="../../assets/mock.js"></script>
"""
    crumbs = [("Home", "../../index.html"), ("Mock tests", "../index.html"), (exam["title"], None)]
    return crumbs, body


def test_body(exam, set_no, paper, inline, group_title):
    """mock-test/<exam>/set-N.html — the test screen; mock.js does the rest."""
    payload = question_payload(exam, set_no, paper, inline, "../..")
    sec_rows = "".join(
        f"<tr><td>{esc(s['name'])}</td><td>{s['count']}</td><td>{s['count'] * exam['marks_correct']}</td></tr>"
        for s in exam["sections"]
    )
    other_sets = " ".join(
        f'<a class="chip" href="set-{n}.html">Set {n}</a>' if n != set_no else f'<span class="chip is-on">Set {n}</span>'
        for n in range(1, exam["sets"] + 1)
    )
    body = f"""
<p class="kicker">MOCK TEST · {esc(group_title)}</p>
<h1>{esc(exam["title"])} — Set {set_no}</h1>
<p class="lede">{exam["questions"]} questions · {minutes_text(exam["minutes"])} · {esc(marking_text(exam))}.
Answer on screen, submit, and get your score with a one-page report.</p>
<p class="chips">{other_sets}</p>
<div class="mock-app" id="mock" data-mock-key="{esc(exam["id"])}/{set_no}">

  <section class="mock-view" data-view="intro">
    {pattern_chips(exam)}
    <div class="tablewrap"><table><thead><tr><th>Section</th><th>Questions</th><th>Marks</th></tr></thead>
    <tbody>{sec_rows}</tbody></table></div>
    <div class="mock-instructions">
      <h2>Instructions</h2>
      <ol>
        <li>The timer starts when you press <strong>Start test</strong> and the test submits itself at zero.</li>
        <li>Each question has one correct option. {esc(marking_text(exam))}; unattempted questions score 0.</li>
        <li>Use the palette to jump between questions; <em>Mark for review</em> only colours the palette, it does not affect the score.</li>
        <li>Your answers are kept in this browser while the test runs, so an accidental reload does not lose them.</li>
        <li>After submitting you get a one-page report (print or save as PDF), a text download and a full answer review.</li>
      </ol>
    </div>
    <p class="mock-name"><label>Name for the report (optional) <input type="text" data-mock-name maxlength="60" placeholder="Your name"></label></p>
    <p class="btnrow">
      <button type="button" class="btn primary" data-mock-start>Start test →</button>
      <a class="btn" href="set-{set_no}-paper.html">Printable paper / PDF</a>
      <a class="btn" href="set-{set_no}.txt" download>Download paper (.txt)</a>
      <a class="btn" href="set-{set_no}-key.txt" download>Answer key (.txt)</a>
    </p>
    <div data-mock-last hidden></div>
    <p class="hint">Original practice material built from this site's question banks — not an official paper.</p>
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

</div>
<p class="btnrow mock-foot"><a class="btn" href="index.html">← {esc(exam["title"])} mocks</a> <a class="btn" href="../index.html">All mock tests</a></p>
<script type="application/json" id="mock-data">{_json_for_script(payload)}</script>
<script src="../../assets/mock.js"></script>
"""
    crumbs = [
        ("Home", "../../index.html"),
        ("Mock tests", "../index.html"),
        (exam["title"], "index.html"),
        (f"Set {set_no}", None),
    ]
    return crumbs, body


def paper_body(exam, set_no, paper, inline, group_title):
    """mock-test/<exam>/set-N-paper.html — print layout with optional key."""
    qs_html = []
    current_sec = None
    for q in paper:
        if q["section"] != current_sec:
            current_sec = q["section"]
            sec = exam["sections"][current_sec]
            first = q["n"]
            last = first + sec["count"] - 1
            qs_html.append(
                f'<h2 class="paper-sec">Section {chr(65 + current_sec)} · {esc(sec["name"])} '
                f'<span>Q{first}–Q{last} · {sec["count"] * exam["marks_correct"]} marks</span></h2>'
            )
        opts = "".join(
            f'<li><span class="paper-lab">({esc(l)})</span> {inline(o)}</li>'
            for l, o in zip(q["labels"], q["options"])
        )
        ctx = f'<span class="paper-ctx">[{inline(q["context"])}]</span> ' if q.get("context") else ""
        qs_html.append(
            f'<div class="paper-q"><p class="paper-stem"><strong>{q["n"]}.</strong> {ctx}{inline(q["stem"])}</p>'
            f'<ul class="paper-opts">{opts}</ul></div>'
        )

    omr = "".join(
        f'<div class="omr-row"><span class="omr-n">{q["n"]}</span>'
        + "".join(f'<span class="omr-bubble">{esc(l)}</span>' for l in q["labels"])
        + "</div>"
        for q in paper
    )
    key_rows = "".join(
        f'<tr><td>{q["n"]}</td><td><strong>({esc(q["labels"][q["answer"]])})</strong> {inline(q["options"][q["answer"]])}</td>'
        f'<td>{inline(q["explanation"])}</td><td>{esc(q["group_title"])}</td></tr>'
        for q in paper
    )
    body = f"""
<div class="paper" data-paper>
<div class="paper-tools no-print">
  <p class="kicker">MOCK TEST · {esc(group_title)} · PRINTABLE PAPER</p>
  <p class="btnrow">
    <button type="button" class="btn primary" onclick="window.print()">Print / Save as PDF</button>
    <a class="btn" href="set-{set_no}.txt" download>Download paper (.txt)</a>
    <a class="btn" href="set-{set_no}-key.txt" download>Download key (.txt)</a>
    <a class="btn" href="set-{set_no}.html">Take this set online →</a>
  </p>
  <p><label><input type="checkbox" data-paper-key checked> Include the answer key and explanations when printing (it starts on a new page)</label>
  <label class="paper-toggle"><input type="checkbox" data-paper-show-key> Show the key on screen now</label></p>
  <p class="hint">In the print dialog choose <em>Save as PDF</em> to download the paper. Portrait A4, default margins.</p>
</div>

<header class="paper-head">
  <p class="paper-brand">Class 10 CBSE study hub · Mock test</p>
  <h1>{esc(exam["title"])} <small>{esc(exam.get("code", ""))}</small></h1>
  <p class="paper-set">Set {set_no} of {exam["sets"]}</p>
  <table class="paper-meta"><tbody>
    <tr><th>Time allowed</th><td>{minutes_text(exam["minutes"])}</td><th>Maximum marks</th><td>{max_marks(exam)}</td></tr>
    <tr><th>Questions</th><td>{exam["questions"]}</td><th>Marking</th><td>{esc(marking_text(exam))}</td></tr>
    <tr><th>Name</th><td class="paper-blank"></td><th>Date</th><td class="paper-blank"></td></tr>
  </tbody></table>
  <ol class="paper-instr">
    <li>All questions are compulsory unless you are practising negative marking; each has exactly one correct option.</li>
    <li>Mark your answers on the answer grid at the end, then check them against the key.</li>
    <li>{esc(exam.get("length", "Mock"))} — pattern: {esc(exam.get("pattern_note", ""))}</li>
  </ol>
</header>

<main class="paper-qs">{"".join(qs_html)}</main>

<section class="paper-omr">
  <h2>Answer grid</h2>
  <div class="omr">{omr}</div>
</section>

<section class="paper-key" data-paper-key-block>
  <h2>Answer key &amp; explanations — {esc(exam["title"])} · Set {set_no}</h2>
  <div class="tablewrap"><table class="key-table"><thead><tr><th>Q</th><th>Answer</th><th>Why</th><th>Topic</th></tr></thead>
  <tbody>{key_rows}</tbody></table></div>
</section>

<footer class="paper-foot">Original practice material from {SITE_URL}/ — not an official paper. Created by Mohammad Umair.
Score this set online: {SITE_URL}/mock-test/{esc(exam["id"])}/set-{set_no}.html</footer>
</div>
<script src="../../assets/mock.js"></script>
"""
    crumbs = [
        ("Home", "../../index.html"),
        ("Mock tests", "../index.html"),
        (exam["title"], "index.html"),
        (f"Set {set_no} · paper", None),
    ]
    return crumbs, body


# --------------------------------------------------------------------------
# plain-text downloads
# --------------------------------------------------------------------------
def paper_txt(exam, set_no, paper) -> str:
    rule = "=" * 72
    lines = [
        "CLASS 10 CBSE STUDY HUB - MOCK TEST",
        rule,
        f"Exam    : {exam['title']} ({exam.get('code', '')})",
        f"Set     : {set_no} of {exam['sets']}",
        f"Time    : {minutes_text(exam['minutes'])}",
        f"Marks   : {max_marks(exam)} ({marking_text(exam)})",
        f"Pattern : {exam.get('length', 'Mock')} - {exam.get('pattern_note', '')}",
        rule,
        "",
        "Instructions",
        "1. Each question has exactly one correct option.",
        "2. Write your answers in the answer grid at the end, then check the key file.",
        f"3. {marking_text(exam)}; unattempted questions score 0.",
        "",
    ]
    current_sec = None
    for q in paper:
        if q["section"] != current_sec:
            current_sec = q["section"]
            sec = exam["sections"][current_sec]
            first = q["n"]
            last = first + sec["count"] - 1
            title = f"SECTION {chr(65 + current_sec)} - {sec['name']} (Q{first}-Q{last}, {sec['count'] * exam['marks_correct']} marks)"
            lines += ["", title, "-" * len(title), ""]
        ctx = f"[{plain(q['context'])}] " if q.get("context") else ""
        lines.append(f"Q{q['n']}. {ctx}{plain(q['stem'])}")
        for l, o in zip(q["labels"], q["options"]):
            lines.append(f"    ({l}) {plain(o)}")
        lines.append("")
    lines += ["", "ANSWER GRID", "-" * 11]
    row = []
    for q in paper:
        row.append(f"Q{q['n']:>3} [   ]")
        if len(row) == 5:
            lines.append("  ".join(row))
            row = []
    if row:
        lines.append("  ".join(row))
    lines += [
        "",
        rule,
        f"Answer key : set-{set_no}-key.txt",
        f"Score online: {SITE_URL}/mock-test/{exam['id']}/set-{set_no}.html",
        "Original practice material from the Class 10 CBSE study hub - not an official paper.",
        "Created by Mohammad Umair.",
        "",
    ]
    return "\n".join(lines)


def key_txt(exam, set_no, paper) -> str:
    rule = "=" * 72
    lines = [
        f"ANSWER KEY - {exam['title']} ({exam.get('code', '')}) - Set {set_no}",
        rule,
        f"Marking: {marking_text(exam)}. Score = correct x {exam['marks_correct']}"
        + (f" - wrong x {exam['marks_wrong']}" if exam["marks_wrong"] else "")
        + f". Maximum {max_marks(exam)}.",
        "",
        "Quick key",
    ]
    row = []
    for q in paper:
        row.append(f"Q{q['n']:>3} ({q['labels'][q['answer']]})")
        if len(row) == 6:
            lines.append("  ".join(row))
            row = []
    if row:
        lines.append("  ".join(row))
    lines += ["", "Explanations", "-" * 12, ""]
    for q in paper:
        lines.append(f"Q{q['n']}. {plain(q['explanation'])}")
        lines.append(f"      Topic: {q['group_title']} ({q['subject_title']})")
        lines.append("")
    lines += [rule, f"Paper: set-{set_no}.txt  |  Online: {SITE_URL}/mock-test/{exam['id']}/set-{set_no}.html", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# entry point used by build.py
# --------------------------------------------------------------------------
def prepare(subjects, chapters_by_subject):
    """Load the config and banks and assemble every set. Returns (config, exams)."""
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


def build_mock_tests(dist, config, exams, subjects, admissions, page, write, inline):
    """Write every mock-test page and download file. Returns the list of
    site-relative paths written (for the build report)."""
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
        for set_no, paper in enumerate(exam["sets_data"], 1):
            crumbs, body = test_body(exam, set_no, paper, inline, gtitle)
            write(folder / f"set-{set_no}.html",
                  page(f"{exam['title']} — Set {set_no} mock test", crumbs, body, "../..", None, "mock"))
            crumbs, body = paper_body(exam, set_no, paper, inline, gtitle)
            write(folder / f"set-{set_no}-paper.html",
                  page(f"{exam['title']} — Set {set_no} paper", crumbs, body, "../..", None, "mock"))
            write(folder / f"set-{set_no}.txt", paper_txt(exam, set_no, paper))
            write(folder / f"set-{set_no}-key.txt", key_txt(exam, set_no, paper))
            written += [
                f"mock-test/{exam['id']}/set-{set_no}.html",
                f"mock-test/{exam['id']}/set-{set_no}-paper.html",
                f"mock-test/{exam['id']}/set-{set_no}.txt",
                f"mock-test/{exam['id']}/set-{set_no}-key.txt",
            ]
    return written
