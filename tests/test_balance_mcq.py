"""The MCQ answer key must be balanced -- and stay balanced.

Audit finding A (2 Oct 2026): across the chapter MCQs the right option was (b) 55% of
the time and (d) 1% of the time, so a student who marked (b) throughout scored about
half marks. scripts/balance_mcq.py spreads the key over (a)-(d) / (क)-(घ) by moving the
right option inside each question. These tests pin the result (bands, per subject and
per chapter, so a lopsided chapter cannot hide inside a balanced total), pin the rules the
script follows, and run it end to end on a throwaway bank.

Run with:  python3 -m unittest tests.test_balance_mcq -v
"""
import contextlib
import importlib.util
import io
import json
import math
import sys
import tempfile
import types
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
sys.path.insert(0, str(SITE))

import mocktest  # noqa: E402

_spec = importlib.util.spec_from_file_location("balance_mcq", ROOT / "scripts" / "balance_mcq.py")
balance = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(balance)


def mcq(stem, options, right, labels="abcd", sep="  "):
    """A bank MCQ in the site's format: stem + options in `q`, **(key) text.** why in `a`."""
    q = stem + " " + sep.join(f"({l}) {o}" for l, o in zip(labels, options))
    return {"q": q, "a": f"**({labels[right]}) {options[right]}.** because"}


def unit_of(mcqs, key="test/ch", subject="test"):
    return balance.Unit(key, subject, mcqs)


def run_plan(*units):
    balance.plan([types.SimpleNamespace(units=list(units))])


def right_text(m):
    p = mocktest.parse_mcq(m)
    return p["options"][p["answer"]]


# --------------------------------------------------------------------------
# the numbers in the repository
# --------------------------------------------------------------------------
class AnswerKeyBandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.units = [u for cf in balance.load_files() for u in cf.units]
        cls.keys = [[p["answer"] for p in u.parsed] for u in cls.units]

    @staticmethod
    def shares(counter):
        n = sum(counter.values())
        return [counter[i] / n for i in range(4)]

    def test_the_whole_bank_was_read(self):
        """Count the MCQs straight from the JSON, so an empty or partial load cannot pass."""
        raw = 0
        for path in (ROOT / "site" / "content" / "chapters").rglob("*.json"):
            raw += sum(len(ch.get("mcq") or []) for ch in json.loads(path.read_text(encoding="utf-8")))
        for path in (ROOT / "site" / "content" / "banks").glob("*.json"):
            raw += sum(len(g.get("mcq") or []) for g in json.loads(path.read_text(encoding="utf-8"))["groups"])
        self.assertGreater(raw, 1400)
        self.assertEqual(sum(len(k) for k in self.keys), raw)

    def test_each_letter_is_right_about_a_quarter_of_the_time(self):
        total = Counter(a for key in self.keys for a in key)
        for letter, share in zip("abcd", self.shares(total)):
            self.assertTrue(0.23 <= share <= 0.27, f"({letter}) is the key for {share:.1%} of all MCQs: {dict(total)}")

    def test_every_subject_is_balanced_too(self):
        by_subject = {}
        for u, key in zip(self.units, self.keys):
            by_subject.setdefault(u.subject, Counter()).update(key)
        self.assertGreaterEqual(len(by_subject), 9)           # eight subjects and the Mental Ability bank
        for subject, counter in by_subject.items():
            for letter, share in zip("abcd", self.shares(counter)):
                self.assertTrue(0.20 <= share <= 0.30, f"{subject}: ({letter}) is the key for {share:.1%} ({dict(counter)})")

    def test_no_chapter_leans_on_one_letter(self):
        for u, key in zip(self.units, self.keys):
            if len(key) < 4:
                continue
            top = max(Counter(key).values())
            self.assertLessEqual(top, math.ceil(len(key) / 4) + 2, f"{u.key}: {Counter(key)} of {len(key)} MCQs")

    def test_no_chapter_has_three_equal_answers_in_a_row(self):
        for u, key in zip(self.units, self.keys):
            self.assertLessEqual(balance._longest_run(key), 2, f"{u.key}: answers run {key}")

    def test_the_balancer_has_nothing_left_to_do(self):
        """The rewrite is a fixed point: running it again changes nothing. If this fails
        after you added or edited an MCQ, run  python3 scripts/balance_mcq.py  and rebuild."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = balance.main(["--check", "--quiet"])
        self.assertEqual(code, 0, out.getvalue())

    def test_the_writer_reproduces_every_file_byte_for_byte(self):
        """A rewrite may only change the two MCQ fields; any other difference would be a
        formatting change smuggled in."""
        for cf in balance.load_files():
            if cf.units:
                dump = balance.writer_for(cf)
                self.assertIsNotNone(dump, f"{cf.path.name}: layout cannot be reproduced")
                self.assertEqual(dump(json.loads(cf.text), cf.text), cf.text)


# --------------------------------------------------------------------------
# the rules
# --------------------------------------------------------------------------
class RuleTests(unittest.TestCase):
    def test_catch_all_options_are_recognised_and_ordinary_ones_are_not(self):
        for text in ("all of the above", "None of these", "Both A and B", "both", "neither", "none", "either way",
                     "any of the above", "all equally", "Both I and II", "Neither I nor II", "a and b", "(a) and (c)",
                     "कोई नहीं", "इनमें से कोई नहीं", "उपर्युक्त सभी", "दोनों में", "किसी में नहीं", "किसी से नहीं"):
            self.assertTrue(balance.is_catch_all(text), text)
        for text in ("avoids all risk", "bans all religions", "all citizens of the country", "respect for all religions",
                     "7 years and above", "well above the head", "delete one of them", "Only I", "both parents equally",
                     "कोई प्रदर्शन नहीं", "सर्वेश्वर", "सभी जीवों के प्रति दया का भाव रखना चाहिए"):
            self.assertFalse(balance.is_catch_all(text), text)

    def test_number_lists_are_read_the_way_an_author_reads_them(self):
        sorted_four = (["2", "4", "8", "24"], ["1/6", "1/3", "1/2", "2/3"], ["6,000", "18,000", "40,000", "500,000"],
                       ["100 J", "10 J", "1 J", "0.1 J"], ["1959", "1969", "1989", "1995"], ["−5", "−2", "1", "4"],
                       ["IEEE 802.3", "IEEE 802.11", "IEEE 802.15", "IEEE 802.16"])
        for opts in sorted_four:
            self.assertTrue(balance.is_number_list(opts), opts)
        for opts in (["40", "42", "44", "36"], ["x + 1", "x − 1", "2x", "x²"], ["3", "5", "8", "2"], ["1", "2", "1", "3"]):
            self.assertFalse(balance.looks_ordered(opts), opts)
        # three sorted numbers beside a word stay put but are not turned round
        beside_word = ["0", "1", "2", "undefined"]
        self.assertTrue(balance.looks_ordered(beside_word))
        self.assertFalse(balance.is_number_list(beside_word))

    def test_classification(self):
        cases = {
            balance.FREE: mcq("Capital of France?", ["Lyon", "Paris", "Nice", "Lille"], 1),
            balance.TURN: mcq("HCF of 8 and 12?", ["2", "4", "8", "24"], 1),
            balance.FIXED: mcq("Choose.", ["one", "two", "three", "all of the above"], 3),
        }
        for kind, m in cases.items():
            self.assertEqual(balance.classify(m, mocktest.parse_mcq(m))[0], kind, m["q"])
        cites = {"q": "Pick. (a) w  (b) x  (c) y  (d) z", "a": "**(b) x.** Option (c) is a trap."}
        self.assertEqual(balance.classify(cites, mocktest.parse_mcq(cites)), (balance.FIXED, "explanation cites a letter"))
        word = mcq("Value?", ["0", "1", "2", "undefined"], 1)
        self.assertEqual(balance.classify(word, mocktest.parse_mcq(word))[0], balance.FIXED)

    def test_rebuild_moves_only_the_right_option(self):
        m = mcq("Capital of France?", ["Lyon", "Paris", "Nice", "Lille"], 1)
        p = mocktest.parse_mcq(m)
        q, a, ordered = balance.rebuild(m, p, 3)
        self.assertEqual(q, "Capital of France? (a) Lyon  (b) Nice  (c) Lille  (d) Paris")
        self.assertEqual(a, "**(d) Paris.** because")
        self.assertEqual(ordered, ["Lyon", "Nice", "Lille", "Paris"])
        again = mocktest.parse_mcq({"q": q, "a": a})
        self.assertEqual(again["options"][again["answer"]], "Paris")

    def test_devanagari_labels_and_spacing_survive(self):
        m = mcq("भारत की राजधानी?", ["मुंबई", "दिल्ली", "कोलकाता", "चेन्नई"], 1, labels="कखगघ", sep=" ")
        q, a, _ = balance.rebuild(m, mocktest.parse_mcq(m), 2)
        self.assertEqual(q, "भारत की राजधानी? (क) मुंबई (ख) कोलकाता (ग) दिल्ली (घ) चेन्नई")
        self.assertTrue(a.startswith("**(ग) दिल्ली.**"))

    def test_a_turned_list_is_still_a_sorted_list_and_the_key_follows(self):
        m = mcq("HCF of 8 and 12?", ["2", "4", "8", "24"], 1)
        q, a, ordered = balance.rebuild(m, mocktest.parse_mcq(m), 2, turn=True)
        self.assertEqual(ordered, ["24", "8", "4", "2"])
        self.assertTrue(a.startswith("**(c) 4.**"))
        self.assertTrue(balance.is_number_list(ordered))

    def test_a_lopsided_chapter_is_levelled_and_a_second_run_changes_nothing(self):
        names = "abcdefgh"                                                 # no digits: not number lists
        mcqs = [mcq(f"Which of these is right, case {c}?", [f"wrong {c}", f"right {c}", f"false {c}", f"incorrect {c}"], 1)
                for c in names]                                            # every key is (b)
        wanted = [right_text(m) for m in mcqs]
        u = unit_of(mcqs)
        run_plan(u)
        self.assertEqual(Counter(u.target), {0: 2, 1: 2, 2: 2, 3: 2})
        balance.apply_plan([u])
        self.assertEqual([right_text(m) for m in mcqs], wanted)             # the same option is right
        self.assertEqual(Counter(mocktest.parse_mcq(m)["answer"] for m in mcqs), {0: 2, 1: 2, 2: 2, 3: 2})
        self.assertLessEqual(balance._longest_run([mocktest.parse_mcq(m)["answer"] for m in mcqs]), 2)
        snapshot = json.dumps(mcqs, ensure_ascii=False)
        again = unit_of(mcqs)
        run_plan(again)
        self.assertEqual(balance.apply_plan([again]), 0)
        self.assertEqual(json.dumps(mcqs, ensure_ascii=False), snapshot)

    def test_wrong_options_keep_their_relative_order(self):
        m = mcq("Pick the odd one out.", ["alpha", "bravo", "charlie", "delta"], 2)
        for target in range(4):
            wrong = [o for o in balance.arrangement(mocktest.parse_mcq(m), target) if o != "charlie"]
            self.assertEqual(wrong, ["alpha", "bravo", "delta"])

    def test_fixed_questions_are_never_touched(self):
        fixed = [mcq(f"Q{i}: which?", ["x", "y", "z", "none of these"], 1) for i in range(4)]
        free = [mcq(f"Q{i}: name it.", [f"a{i}", f"b{i}", f"c{i}", f"d{i}"], 1) for i in range(4)]
        before = json.dumps(fixed)
        u = unit_of(fixed + free)
        run_plan(u)
        balance.apply_plan([u])
        self.assertEqual(json.dumps(fixed), before)
        # four fixed (b)s: the free ones take the other three letters first
        free_keys = [mocktest.parse_mcq(m)["answer"] for m in free]
        self.assertNotIn(1, free_keys[:3])

    def test_sorted_lists_are_only_turned_round_to_even_out_b_and_c(self):
        lists = [mcq(f"Q{i}: value?", [str(10 * k + i) for k in (1, 2, 3, 4)], 1) for i in range(4)]
        u = unit_of(lists)
        run_plan(u)
        self.assertEqual(Counter(u.target), {1: 2, 2: 2})
        balance.apply_plan([u])
        for m in lists:
            self.assertTrue(balance.is_number_list(mocktest.parse_mcq(m)["options"]))

    def test_unsorted_numbers_never_land_in_sorted_order(self):
        # moving the 9 to the end would give 1, 2, 3, 9: a sorted list, which would change the
        # question's class between two runs, so that placement is forbidden
        m = mcq("Pick the number.", ["1", "2", "9", "3"], 2)
        u = unit_of([m] * 1 + [mcq(f"Q{i}", [str(i + 1), str(i + 2), str(i + 9), str(i + 3)], 2) for i in range(7)])
        self.assertEqual(balance._forbidden(u, 0), {3})
        run_plan(u)
        balance.apply_plan([u])
        for q in u.mcqs:
            self.assertFalse(balance.looks_ordered(mocktest.parse_mcq(q)["options"]), q["q"])

    def test_a_forbidden_placement_goes_to_the_least_used_permitted_letter(self):
        # In every one of these, putting the right option first would make a sorted list
        # (wrong 1, wrong 2, wrong 3 already rise), so (a) is forbidden for all eight.
        mcqs = [mcq(f"Q{i}: pick.", [f"w{i}-1", f"r{i}", f"w{i}-2", f"w{i}-3"], 1) for i in range(8)]
        u = unit_of(mcqs)
        self.assertTrue(all(balance._forbidden(u, i) == {0} for i in range(8)))
        run_plan(u)
        self.assertNotIn(0, u.target)
        counts = Counter(u.target)
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)     # (b), (c), (d): 3 + 3 + 2
        balance.apply_plan([u])
        for m in mcqs:
            self.assertFalse(balance.looks_ordered(mocktest.parse_mcq(m)["options"]), m["q"])
        again = unit_of(mcqs)
        run_plan(again)
        self.assertEqual(balance.apply_plan([again]), 0)

    def test_the_shuffle_depends_on_nothing_but_its_seed(self):
        """sha256 driven, not random: the same result on every Python version."""
        out = balance._hash_shuffle([0, 1, 2, 3, 0, 1, 2, 3], "maths/ch01:0")
        self.assertEqual(out, balance._hash_shuffle([0, 1, 2, 3, 0, 1, 2, 3], "maths/ch01:0"))
        self.assertEqual(sorted(out), [0, 0, 1, 1, 2, 2, 3, 3])
        self.assertNotEqual(out, balance._hash_shuffle([0, 1, 2, 3, 0, 1, 2, 3], "maths/ch01:1"))
        self.assertEqual(out, [3, 0, 1, 3, 2, 2, 1, 0])       # pinned: a new algorithm would reshuffle the whole bank


# --------------------------------------------------------------------------
# the script, end to end, on a throwaway copy of the layout
# --------------------------------------------------------------------------
class ScriptEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        (base / "chapters" / "maths").mkdir(parents=True)
        (base / "banks").mkdir()
        mcqs = [mcq(f"Q{i}: which one is right?", [f"w{i}a", f"r{i}", f"w{i}b", f"w{i}c"], 1) for i in range(8)]
        self.path = base / "chapters" / "maths" / "01.json"
        self.chapters = [{"id": "ch01-x", "num": 1, "title": "X", "mcq": mcqs, "qa": [{"t": "S", "m": "2", "q": "Q?", "a": "A."}]}]
        # no trailing newline, as in the English, Hindi, CA and Social Science files
        self.path.write_text(json.dumps(self.chapters, indent=2, ensure_ascii=False), encoding="utf-8")
        self.saved = (balance.CHAPTERS, balance.BANKS)
        balance.CHAPTERS, balance.BANKS = base / "chapters", base / "banks"

    def tearDown(self):
        balance.CHAPTERS, balance.BANKS = self.saved
        self.tmp.cleanup()

    def run_main(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()):
            return balance.main(list(argv))

    def test_check_flags_a_lopsided_bank_and_the_rewrite_fixes_it(self):
        self.assertEqual(self.run_main("--check", "--quiet"), 1)
        before = self.path.read_text(encoding="utf-8")
        self.assertEqual(self.run_main("--check", "--quiet"), 1)
        self.assertEqual(self.path.read_text(encoding="utf-8"), before, "--check must not write")
        self.assertEqual(self.run_main("--quiet"), 0)
        after = self.path.read_text(encoding="utf-8")
        self.assertNotEqual(after, before)
        self.assertFalse(after.endswith("\n"), "the file's missing final newline must be kept")
        data = json.loads(after)
        self.assertEqual(data[0]["qa"], self.chapters[0]["qa"])             # nothing else was touched
        key = Counter(mocktest.parse_mcq(m)["answer"] for m in data[0]["mcq"])
        self.assertEqual(key, {0: 2, 1: 2, 2: 2, 3: 2})
        self.assertEqual(self.run_main("--check", "--quiet"), 0)
        self.assertEqual(self.run_main("--quiet"), 0)
        self.assertEqual(self.path.read_text(encoding="utf-8"), after, "a second rewrite must change nothing")

    def test_a_file_it_cannot_reproduce_is_refused_not_mangled(self):
        # hand-edited layout: different indentation from anything the writer produces
        text = json.dumps(self.chapters, indent=4, ensure_ascii=False)
        self.path.write_text(text, encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.run_main("--quiet")
        self.assertEqual(self.path.read_text(encoding="utf-8"), text)


if __name__ == "__main__":
    unittest.main()
