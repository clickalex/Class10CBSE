"""Content-quality guards for the chapter banks.

The 2 Oct 2026 audit found written Q&As and MCQs built from copy-pasted templates
("Riya is revising ...", "Read and answer: Two students attempt ...", "The most
exam-ready way to revise ... is:"). They are being replaced, chapter by chapter, with
real questions. These tests keep what has been replaced replaced:

  * COMPLETED files must contain no template at all;
  * everywhere else the number of templated items may only go DOWN (a ratchet).
    Lower QA_CEILING / MCQ_CEILING and extend COMPLETED when more chapters are
    rewritten; the target is zero;
  * no chapter repeats a question, every written answer has text, and every MCQ has
    four distinct options and a key that points at one of them.

Run with:  python3 -m unittest tests.test_content_quality -v
"""
import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
CHAPTERS = SITE / "content" / "chapters"
sys.path.insert(0, str(SITE))

import mocktest  # noqa: E402

# The written-question templates found by the audit. English-medium subjects and
# Hindi/Sanskrit each had their own set of five, every one pasted into most chapters.
TEMPLATE_FRAMES = {
    "riya": r"^\w+ is revising “",
    "amit": r"^\w+ is given this exam-style task from “",
    "note": r"^Read and answer:\s*\n\s*\nA Class 10 student is preparing “",
    "two-students": r"^Read and answer:\s*\n\s*\nTwo students attempt:",
    "discuss": r"^Discuss “[^”]*” in detail\. Include the idea that carries marks",
    "hindi-reena": r"^रीना कक्षा 10 की परीक्षा की तैयारी कर रही है",
    "hindi-sthiti": r"^निम्नलिखित स्थिति पढ़कर उत्तर दीजिए।\s*\n\s*\nकक्षा 10 की एक छात्रा",
    "hindi-case": r"^केस पढ़ें और उत्तर दें।\s*\n\s*\nदो मित्र एक ही प्रश्न",
    "hindi-amit": r"^अमित को यह प्रश्न मिला:",
    "hindi-vistar": r"^“[^”]*” को विस्तार से समझाइए",
}
_FRAMES = {name: re.compile(rx) for name, rx in TEMPLATE_FRAMES.items()}

# Chapter files whose templated Q&As and filler MCQs have all been replaced.
COMPLETED = (
    "computer-applications/",
    "information-technology/",
    "maths/",
    "science/",
    "social-science/",
    "english/01-prose.json",
    "english/02-poems.json",
    "english/03-footprints.json",
    "english/04-skills.json",
    "hindi/01-kshitij.json",
    "hindi/02-kritika.json",
    "hindi/03-sparsh.json",
    "hindi/04-sanchayan.json",
    "hindi/05-vyakaran.json",
    "sanskrit/01-shemushi.json",
)

# Templated items still in the repository (3 Oct 2026). Only ever lower these.
QA_CEILING = 0      # written Q&As matching a template (was 721 of 2,133)
MCQ_CEILING = 0     # MCQs that mocktest.is_filler excludes (was 300 of 1,426)


def _template_of(text):
    for name, rx in _FRAMES.items():
        if rx.search(text):
            return name
    return None


def _chapters():
    """Yield (relative file, chapter dict) for every chapter in the banks."""
    for path in sorted(CHAPTERS.rglob("*.json")):
        rel = path.relative_to(CHAPTERS).as_posix()
        for ch in json.loads(path.read_text(encoding="utf-8")):
            yield rel, ch


def _templated():
    """[(file, chapter id, kind, text)] for every templated item in the banks."""
    found = []
    for rel, ch in _chapters():
        for q in ch.get("qa") or []:
            if _template_of(q["q"]):
                found.append((rel, ch["id"], "qa", q["q"][:60]))
        for m in ch.get("mcq") or []:
            if mocktest.is_filler(m):
                found.append((rel, ch["id"], "mcq", m["q"][:60]))
    return found


class TemplateDetectionTests(unittest.TestCase):
    """The ratchet below is only meaningful if the detectors really detect."""

    SAMPLES = {
        "riya": "Riya is revising “Real Numbers” (HCF/LCM). A classmate lost marks by doing this: x",
        "amit": "Amit is given this exam-style task from “Real Numbers”: “State Euclid’s lemma.” Treat it as …",
        "note": "Read and answer:\n\nA Class 10 student is preparing “Real Numbers”. Their note says: …",
        "two-students": "Read and answer:\n\nTwo students attempt: “State Euclid’s lemma.” Student A writes …",
        "discuss": "Discuss “Real Numbers” in detail. Include the idea that carries marks, one worked example …",
        "hindi-reena": "रीना कक्षा 10 की परीक्षा की तैयारी कर रही है। पाठ “सूर के पद” पर आधारित …",
        "hindi-sthiti": "निम्नलिखित स्थिति पढ़कर उत्तर दीजिए।\n\nकक्षा 10 की एक छात्रा “सूर के पद” का पुनरावलोकन कर रही है …",
        "hindi-case": "केस पढ़ें और उत्तर दें।\n\nदो मित्र एक ही प्रश्न हल कर रहे हैं: “…”",
        "hindi-amit": "अमित को यह प्रश्न मिला: “सूरदास की भाषा …” इसे अनुप्रयोग प्रश्न की तरह …",
        "hindi-vistar": "“सूर के पद” को विस्तार से समझाइए और एक परीक्षा-उदाहरण दीजिए।",
    }

    def test_every_frame_matches_its_known_template_and_only_that_one(self):
        self.assertEqual(set(self.SAMPLES), set(TEMPLATE_FRAMES))
        for name, text in self.SAMPLES.items():
            self.assertEqual(_template_of(text), name)

    def test_real_questions_are_not_mistaken_for_templates(self):
        for text in (
            "Prove that √5 is irrational. Hence show that 3 + 2√5 is irrational.",
            "Read and answer:\n\nA calculator displays these decimal forms: 7/80 = 0.0875 …",
            "Discuss the causes of the Revolt of 1857.",
            "सूरदास की काव्य-भाषा और भक्ति-धारा का परिचय दीजिए।",
        ):
            self.assertIsNone(_template_of(text), text)

    def test_the_mock_engine_still_excludes_study_habit_mcqs(self):
        self.assertTrue(mocktest.is_filler({"q": "The most exam-ready way to revise “X” is: (a) …"}))
        self.assertFalse(mocktest.is_filler({"q": "The HCF of 8 and 12 is: (a) 2 (b) 4 (c) 8 (d) 24"}))


class ReplacedContentStaysReplacedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.found = _templated()

    def test_completed_files_contain_no_template(self):
        bad = [f for f in self.found if f[0].startswith(COMPLETED)]
        self.assertEqual(bad, [], f"templated items are back in a completed file: {bad[:5]}")

    def test_templated_items_only_ever_decrease(self):
        qa = sum(1 for f in self.found if f[2] == "qa")
        mcq = sum(1 for f in self.found if f[2] == "mcq")
        self.assertLessEqual(qa, QA_CEILING, f"{qa} templated written Q&As; the ceiling is {QA_CEILING}")
        self.assertLessEqual(mcq, MCQ_CEILING, f"{mcq} filler MCQs; the ceiling is {MCQ_CEILING}")
        # when work lowers the count, the ceiling must follow, or the ratchet stops ratcheting
        self.assertGreaterEqual(qa, QA_CEILING - 25, "lower QA_CEILING to the new count")
        self.assertGreaterEqual(mcq, MCQ_CEILING - 25, "lower MCQ_CEILING to the new count")


class BankIntegrityTests(unittest.TestCase):
    def test_no_chapter_repeats_a_question(self):
        for rel, ch in _chapters():
            for kind in ("qa", "mcq"):
                texts = [" ".join(q["q"].split()) for q in ch.get(kind) or []]
                dupes = [t[:60] for t, n in Counter(texts).items() if n > 1]
                self.assertEqual(dupes, [], f"{rel} {ch['id']} repeats a {kind} question")

    def test_every_written_answer_is_text_or_a_flat_list_of_text(self):
        """A list nested inside an answer used to be printed as a Python list, brackets and
        quotes included (two English answers did this); an empty item is just as invisible."""
        for rel, ch in _chapters():
            for q in ch.get("qa") or []:
                parts = q["a"] if isinstance(q["a"], list) else [q["a"]]
                ok = bool(parts) and all(isinstance(p, str) and p.strip() for p in parts)
                self.assertTrue(ok, f"{rel} {ch['id']}: answer to {q['q'][:50]!r} must be text or a flat list of text")

    def test_every_mcq_has_four_distinct_options_and_a_valid_key(self):
        for rel, ch in _chapters():
            for m in ch.get("mcq") or []:
                parsed = mocktest.parse_mcq(m)
                self.assertIsNotNone(parsed, f"{rel} {ch['id']}: unparsable MCQ {m['q'][:60]!r}")
                options = [o.strip() for o in parsed["options"]]   # 'A,B,C' and 'a,b,c' are different options
                self.assertEqual(len(set(options)), 4, f"{rel} {ch['id']}: duplicate options in {m['q'][:60]!r}")
                self.assertIn(parsed["answer"], range(4))


if __name__ == "__main__":
    unittest.main()
