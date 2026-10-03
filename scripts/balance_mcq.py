#!/usr/bin/env python3
"""Rebalance the answer key of the site's MCQs (audit finding A, 2 Oct 2026).

The banks were written by hand and the key drifted: (b) was right for 55% of the
chapter MCQs and (d) for 1%, so a student who marked (b) throughout scored about
half marks and learned a habit the real paper punishes. This script spreads the
correct answer over (a)-(d) -- or (क)-(घ) in Hindi and Sanskrit -- by moving the
correct option inside each question. It rewrites two fields per MCQ, nothing else:

    "q": "Stem (a) one  (b) two  (c) three  (d) four"   -> options re-ordered
    "a": "**(b) two.** why ..."                         -> the key letter follows

Rules, in the order they matter:

  * The wrong options keep their relative order; only the right one moves. The
    result is a pure function of the question, never of where the answer used to
    be, so running the script twice changes nothing (``--check`` relies on this).
  * Questions whose options depend on their position are left exactly as they
    are: a catch-all option ("all of the above", "both", "neither", "none",
    कोई नहीं, दोनों ...), an explanation that cites a letter, and number lists
    that mix in a word ("0, 1, 2, undefined"). A list of four sorted numbers may
    only be turned round (rising <-> falling, which swaps (b) with (c) and (a)
    with (d)); the other number lists may move, but never into sorted order, so
    a question cannot change class between two runs.
  * Within a chapter the letters are as even as the fixed questions allow, with
    the remainder going to the letters the subject has used least so far; the
    order inside the chapter comes from a hash of the chapter id (no random
    module, so the result is the same on every Python version) and avoids three
    equal answers in a row.

Usage:
    python3 scripts/balance_mcq.py            rewrite the content files in place
    python3 scripts/balance_mcq.py --check    change nothing; exit 1 if a rewrite is due

Standard library only. After a rewrite run ``python3 site/build.py`` so docs/ follows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
sys.path.insert(0, str(SITE))

import mocktest  # noqa: E402  (the one place that knows how an MCQ is parsed)

CHAPTERS = SITE / "content" / "chapters"
BANKS = SITE / "content" / "banks"

SALTS = 600            # attempts to find an order with no run of three equal answers

# One option label together with the whitespace around it, e.g. "  (b) ".
TOKEN_RE = re.compile(r"(\s*\([a-dकखगघ]\)\s*)")
LETTER_IN_TEXT_RE = re.compile(r"\([a-dकखगघ]\)|\boptions? [a-d]\b", re.I)

# --------------------------------------------------------------------------
# what must not move
# --------------------------------------------------------------------------
_CATCH_FIRST = {"all", "both", "none", "neither", "either"}
_CATCH_HINT = {"above", "these", "them", "options", "following", "i", "ii", "a", "b", "c", "d"}
_CATCH_SOME_OF = {"any", "one", "only", "some"}        # "any of the above", "one of these"
_CATCH_LAST = {"above", "these"}
# Hindi and Sanskrit are matched as whole words, so सर्वेश्वर is not "सर्वे" and
# "कोई प्रदर्शन नहीं" (no performance) is not "कोई नहीं" (none of these).
_CATCH_DEVA = {"सभी", "दोनों", "उपर्युक्त", "उपरोक्त", "उभौ", "उभे", "सर्वे", "सर्वम्", "सर्वाणि"}
_CATCH_DEVA_ENDS = (("कोई", "नहीं"), ("कोई", "भी", "नहीं"), ("किसी", "में", "नहीं"), ("किसी", "से", "नहीं"),
                    ("कोऽपि", "न"), ("न", "कोऽपि"), ("इनमें", "से", "कोई"))
_LETTER_LIST_RE = re.compile(r"^(?:both )?\(?[a-d]\)?(?:,| and | & )\(?[a-d]\)?(?: and \(?[a-d]\)?)?(?: both| only)?$")


def _words(text):
    return [w.strip(".,;:!?।॥()[]“”‘’\"'") for w in text.lower().split()]


def is_catch_all(option):
    """True for an option that only makes sense in its place ("none of these")."""
    words = [w for w in _words(option) if w]
    if not words or len(words) > 5:
        return False
    text = " ".join(words)
    if _LETTER_LIST_RE.match(text):
        return True
    if words[0] in _CATCH_FIRST and (len(words) <= 2 or any(w in _CATCH_HINT for w in words[1:])):
        return True
    if words[0] in _CATCH_SOME_OF and words[-1] in _CATCH_LAST:
        return True
    if len(words) <= 4:
        if any(w in _CATCH_DEVA for w in words):
            return True
        if any(tuple(words[-len(end):]) == end for end in _CATCH_DEVA_ENDS):
            return True
    return False


# --- number lists ---------------------------------------------------------
_NUM_RE = re.compile(r"[-−]?\d[\d,]*(?:\.\d+)?(?:\s*/\s*\d+)?")


def _value(token):
    """The number a token stands for: 6,000 -> 6000, 7/2 -> 3.5, −5 -> -5."""
    token = token.replace("−", "-").replace(" ", "")
    if re.match(r"^-?\d{1,3}(?:,\d{3})+", token):
        token = token.replace(",", "")
    else:
        token = token.split(",")[0]
    if "/" in token:
        num, den = token.split("/", 1)
        return float(num) / float(den) if float(den) else None
    return float(token) if token not in ("", "-") else None


def _first_value(option):
    m = _NUM_RE.search(option)
    return _value(m.group(0)) if m else None


def _first_int(option):
    m = re.search(r"\d+", option)
    return int(m.group(0)) if m else None


def _digit_runs(option):
    runs = tuple(int(x) for x in re.findall(r"\d+", option))
    return runs or None


_KEYS = (_first_value, _first_int, _digit_runs)


def _ordered(options, need):
    """True when at least `need` options carry a number and, read in order, those numbers
    are strictly rising or strictly falling under some reading of "number"."""
    for key in _KEYS:
        nums = [v for v in (key(o) for o in options) if v is not None]
        if len(nums) < need:
            continue
        if all(x < y for x, y in zip(nums, nums[1:])) or all(x > y for x, y in zip(nums, nums[1:])):
            return True
    return False


def looks_ordered(options):
    """Three or more numbers listed in order -- 10, 20, 40, 80 or 802.3, 802.11 -- so
    moving one option would break the list."""
    return _ordered(options, 3)


def is_number_list(options):
    """All four options are numbers listed in order: such a list may be turned round."""
    return _ordered(options, 4)


def numeric_count(options):
    """How many options carry a number, under the reading that finds the most."""
    return max(sum(1 for o in options if key(o) is not None) for key in _KEYS)


# --------------------------------------------------------------------------
# one MCQ
# --------------------------------------------------------------------------
def split_question(q):
    """(stem, [label tokens], [option texts], trailing whitespace) of a bank MCQ."""
    parts = TOKEN_RE.split(q)
    stem, tokens, texts = parts[0], parts[1::2], parts[2::2]
    tail = texts[-1][len(texts[-1].rstrip()):]
    texts = [t.strip() for t in texts]
    return stem, tokens, texts, tail


def key_letter_span(answer):
    m = mocktest.ANS_RE.match(answer)
    return (m.start(1), m.end(1)) if m else None


def arrangement(parsed, target, turn=False):
    """The options with the right one at index `target`. The wrong ones keep their relative
    order; `turn` instead reads the whole list backwards (a sorted number list, turned round)."""
    options = parsed["options"]
    if turn:
        return list(reversed(options))
    wrong = [o for i, o in enumerate(options) if i != parsed["answer"]]
    return wrong[:target] + [options[parsed["answer"]]] + wrong[target:]


def rebuild(mcq, parsed, target, turn=False):
    """The MCQ with its right option at index `target`: (new q, new a, new options)."""
    stem, tokens, _texts, tail = split_question(mcq["q"])
    ordered = arrangement(parsed, target, turn)
    q = stem + "".join(tok + text for tok, text in zip(tokens, ordered)) + tail
    start, end = key_letter_span(mcq["a"])
    a = mcq["a"][:start] + parsed["labels"][target] + mcq["a"][end:]
    return q, a, ordered


FREE, TURN, FIXED = "free", "turn", "fixed"


def classify(mcq, parsed):
    """(kind, why): FREE may move anywhere; TURN is a list of four sorted numbers that may
    only be turned round; FIXED stays exactly as it is, and `why` says so."""
    options = parsed["options"]
    if any(is_catch_all(o) for o in options):
        return FIXED, "catch-all option"
    after_key = mcq["a"][key_letter_span(mcq["a"])[1]:]
    if LETTER_IN_TEXT_RE.search(after_key):
        return FIXED, "explanation cites a letter"
    if re.search(r"\b(assertion|reason \(r\))", parsed["stem"], re.I):
        return FIXED, "assertion-reason"
    if is_number_list(options):
        return TURN, "sorted list of four numbers"
    if looks_ordered(options):
        return FIXED, "sorted numbers beside a word"
    return FREE, None


# --------------------------------------------------------------------------
# the content, as units (a chapter, or one group of a standalone bank)
# --------------------------------------------------------------------------
class Unit:
    def __init__(self, key, subject, mcqs):
        self.key = key
        self.subject = subject
        self.mcqs = mcqs
        self.parsed, self.kind, self.why = [], [], []
        for m in mcqs:
            p = mocktest.parse_mcq(m)
            if p is None:
                raise SystemExit(f"{key}: an MCQ does not parse: {str(m.get('q'))[:70]!r}")
            kind, why = classify(m, p)
            self.parsed.append(p)
            self.kind.append(kind)
            self.why.append(why)
        self.target = [None] * len(mcqs)       # the planned answer index, set by plan()

    def of(self, kind):
        return [i for i, k in enumerate(self.kind) if k == kind]

    def fixed_letters(self):
        return {i: self.parsed[i]["answer"] for i in self.of(FIXED)}


class ContentFile:
    def __init__(self, path):
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        self.data = json.loads(self.text)
        self.units = []
        if isinstance(self.data, list):                       # chapters of one subject
            for ch in self.data:
                if ch.get("mcq"):
                    self.units.append(Unit(f"{path.parent.name}/{ch['id']}", path.parent.name, ch["mcq"]))
        else:                                                 # a standalone bank
            for g in self.data.get("groups", []):
                if g.get("mcq"):
                    self.units.append(Unit(f"bank:{self.data['id']}/{g['id']}", f"bank:{self.data['id']}", g["mcq"]))


def _dump(data, original):
    out = json.dumps(data, indent=2, ensure_ascii=False)
    nl = "\n" if original.endswith("\n") else ""
    return out + nl


def _dump_compact_items(data, original):
    """Hand-laid-out banks keep each MCQ on one line: {"q": "...", "a": "..."}."""
    out = json.dumps(data, indent=2, ensure_ascii=False)
    out = re.sub(r'\{\n *("q": [^\n]*),\n *("a": [^\n]*)\n *\}', r"{\1, \2}", out)
    return out + ("\n" if original.endswith("\n") else "")


def writer_for(cf):
    """Pick the serializer that reproduces the file on disk exactly (or None)."""
    for dump in (_dump, _dump_compact_items):
        if dump(json.loads(cf.text), cf.text) == cf.text:
            return dump
    return None


def load_files():
    paths = sorted(CHAPTERS.rglob("*.json")) + sorted(BANKS.glob("*.json"))
    return [ContentFile(p) for p in paths]


# --------------------------------------------------------------------------
# the plan
# --------------------------------------------------------------------------
def _hash_shuffle(items, seed):
    """Fisher-Yates driven by sha256, so it is identical on every Python version."""
    items = list(items)
    for i in range(len(items) - 1, 0, -1):
        digest = hashlib.sha256(f"{seed}:{i}".encode("utf-8")).digest()
        j = int.from_bytes(digest[:8], "big") % (i + 1)
        items[i], items[j] = items[j], items[i]
    return items


def _longest_run(seq):
    best = run = 0
    prev = None
    for x in seq:
        run = run + 1 if x == prev else 1
        prev = x
        best = max(best, run)
    return best


def _forbidden(unit, i):
    """Letters a free question must not take because its numbers would land in sorted order."""
    p = unit.parsed[i]
    if numeric_count(p["options"]) < 3:
        return set()
    return {t for t in range(4) if looks_ordered(arrangement(p, t))}


def _decide(unit, subject_run):
    """Decide every answer index of one unit: {question index: planned index}.

    1. Fixed questions stay. 2. A sorted number list picks the less used of its two
    positions (b or c; a or d), keeping the way it already reads when they tie. 3. The free
    questions level the unit up, the remainder going to the letter the subject has used
    least; their order comes from a hash of the unit key, with no run of three equal
    answers and no number list landing in sorted order (a question that would is moved to
    the permitted letter the unit has used least)."""
    chosen = dict(unit.fixed_letters())
    counts = Counter(chosen.values())
    for i in unit.of(TURN):
        now = unit.parsed[i]["answer"]
        pick = min((now, 3 - now), key=lambda L: (counts[L], subject_run[L], L != now, L))
        chosen[i] = pick
        counts[pick] += 1
    free = unit.of(FREE)
    quota = Counter()
    for _ in free:
        pick = min(range(4), key=lambda L: (counts[L], subject_run[L], L))
        counts[pick] += 1
        quota[pick] += 1
    letters = sorted(quota.elements())
    forbidden = {i: _forbidden(unit, i) for i in free}
    best, best_score = [], None
    for salt in range(SALTS):
        cand = _hash_shuffle(letters, f"{unit.key}:{salt}")
        key = dict(chosen)
        key.update(zip(free, cand))
        broken = sum(1 for i, L in zip(free, cand) if L in forbidden[i])
        score = (broken, max(0, _longest_run([key[i] for i in sorted(key)]) - 2))
        if best_score is None or score < best_score:
            best, best_score = cand, score
        if score == (0, 0):
            break
    chosen.update(zip(free, best))
    for i in free:
        if chosen[i] in forbidden[i]:
            # a placement that would sort a number list is never taken: that question takes
            # the permitted letter its unit has used least (its own position is always permitted)
            counts = Counter(L for j, L in chosen.items() if j != i)
            allowed = [L for L in range(4) if L not in forbidden[i]]
            chosen[i] = min(allowed, key=lambda L: (counts[L], subject_run[L], L))
    return chosen


def plan(files):
    """Set unit.target for every question; returns the units in processing order."""
    units = [u for cf in files for u in cf.units]
    by_subject = {}
    for u in units:
        by_subject.setdefault(u.subject, []).append(u)
    for group in by_subject.values():
        # a subject's fixed questions are known up front, so the letters they over-use are
        # already counted when the first chapter decides who gets a remainder
        run = Counter()
        for u in group:
            run.update(u.fixed_letters().values())
        for u in group:
            chosen = _decide(u, run)
            for i in range(len(u.mcqs)):
                u.target[i] = chosen[i]
            run.update(chosen[i] for i in u.of(TURN) + u.of(FREE))
    return units


# --------------------------------------------------------------------------
# applying and reporting
# --------------------------------------------------------------------------
def apply_plan(units):
    """Rewrite the MCQ dicts in place; returns how many questions changed."""
    changed = 0
    for u in units:
        for i, (m, p) in enumerate(zip(u.mcqs, u.parsed)):
            t = u.target[i]
            if t == p["answer"]:
                continue
            turn = u.kind[i] == TURN
            q, a, ordered = rebuild(m, p, t, turn)
            again = mocktest.parse_mcq({"q": q, "a": a})
            # the safety net: same four options, the same one right, now at index t
            assert again and again["answer"] == t and sorted(again["options"]) == sorted(p["options"]), u.key
            assert again["options"][t] == p["options"][p["answer"]], u.key
            m["q"], m["a"] = q, a
            changed += 1
    return changed


def distribution(units, current=True):
    """{subject: Counter of answer index}; `current` False reads the planned letters."""
    out = {}
    for u in units:
        c = out.setdefault(u.subject, Counter())
        for i, p in enumerate(u.parsed):
            c[p["answer"] if current else u.target[i]] += 1
    return out


def _row(name, c):
    n = sum(c.values())
    cells = "  ".join(f"{c[i]:4d} {c[i] / n:5.1%}" for i in range(4))
    return f"{name:26s} {n:5d}   {cells}"


def report(units):
    before, after = distribution(units, True), distribution(units, False)
    head = f"{'':26s} {'MCQs':>5s}   " + "  ".join(f"{'(' + 'abcd'[i] + ')':>10s}" for i in range(4))
    for title, dist in (("BEFORE", before), ("AFTER", after)):
        print(f"\n{title}\n{head}")
        total = Counter()
        for subject in sorted(dist):
            print(_row(subject, dist[subject]))
            total.update(dist[subject])
        print(_row("ALL", total))
    kept = Counter(w for u in units for k, w in zip(u.kind, u.why) if k == FIXED)
    turned = sum(len(u.of(TURN)) for u in units)
    print("\nleft exactly as they are:", ", ".join(f"{n} {why}" for why, n in kept.most_common()) or "none")
    print(f"may only be turned round: {turned} {'sorted lists of four numbers'}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="change nothing; exit 1 if a rewrite is due")
    ap.add_argument("--quiet", action="store_true", help="skip the before/after table")
    args = ap.parse_args(argv)

    files = load_files()
    units = plan(files)
    due = sum(1 for u in units for i, p in enumerate(u.parsed) if u.target[i] != p["answer"])
    if not args.quiet:
        report(units)

    if args.check:
        if due:
            print(f"\n{due} MCQ answer keys would change: run python3 scripts/balance_mcq.py")
            return 1
        print("\nthe answer key is already balanced and stable")
        return 0

    changed = apply_plan(units)
    written = 0
    for cf in files:
        if not cf.units:
            continue
        # a rewrite must not smuggle in formatting changes: use the serializer that reproduces
        # the file on disk byte for byte, or refuse
        dump = writer_for(cf)
        if dump is None:
            raise SystemExit(f"{cf.path}: cannot reproduce this file's formatting; refusing to rewrite it")
        new = dump(cf.data, cf.text)
        if new != cf.text:
            cf.path.write_text(new, encoding="utf-8")
            written += 1
    print(f"\nrewrote {changed} MCQs in {written} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
