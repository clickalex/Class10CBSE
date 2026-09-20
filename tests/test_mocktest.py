"""Mock-test blueprints, set assembly and generated pages.

Run with:  python3 -m unittest tests.test_mocktest -v
"""
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
CONTENT = SITE / "content"


def _load_build():
    spec = importlib.util.spec_from_file_location("build", SITE / "build.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SITE))
    spec.loader.exec_module(module)
    return module


build = _load_build()
mocktest = build.mocktest


def _subjects():
    data = json.loads((CONTENT / "subjects.json").read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data["subjects"]


class BlueprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((CONTENT / "mock-tests.json").read_text(encoding="utf-8"))
        cls.admissions = json.loads((CONTENT / "admissions.json").read_text(encoding="utf-8"))["institutions"]
        cls.subjects = _subjects()

    def test_every_listed_exam_has_a_mock_or_an_explicit_reason(self):
        covered = {e["admission_id"] for e in self.config["exams"] if e.get("admission_id")}
        no_test = {n["admission_id"] for n in self.config.get("no_test", [])}
        for inst in self.admissions:
            with self.subTest(inst=inst["id"]):
                self.assertTrue(
                    inst["id"] in covered or inst["id"] in no_test,
                    f"{inst['id']} is in admissions.json but has neither a mock test nor a no_test entry",
                )
        for aid in covered | no_test:
            self.assertIn(aid, {i["id"] for i in self.admissions}, f"{aid} is not an admissions.json id")
        self.assertFalse(covered & no_test, "an exam cannot be both mocked and no_test")

    def test_every_subject_has_a_board_mock(self):
        by_subject = {e["subject"] for e in self.config["exams"] if e.get("subject")}
        for subj in self.subjects:
            with self.subTest(subject=subj["slug"]):
                self.assertIn(subj["slug"], by_subject)

    def test_section_counts_and_marking(self):
        ids = set()
        for exam in self.config["exams"]:
            with self.subTest(exam=exam["id"]):
                self.assertNotIn(exam["id"], ids, "duplicate exam id")
                ids.add(exam["id"])
                self.assertRegex(exam["id"], r"^[a-z0-9-]+$")
                total = sum(s["count"] for s in exam["sections"])
                self.assertEqual(total, exam["questions"], "section counts must add up to `questions`")
                self.assertGreater(exam["minutes"], 0)
                self.assertGreater(exam["marks_correct"], 0)
                self.assertGreaterEqual(exam["marks_wrong"], 0)
                self.assertGreaterEqual(exam["sets"], 1)
                for sec in exam["sections"]:
                    self.assertTrue(sec["name"])
                    self.assertGreater(sec["count"], 0)
                    self.assertTrue(sec["pools"], "each section needs at least one pool")


class BankTests(unittest.TestCase):
    def test_mental_ability_bank_parses(self):
        bank = json.loads((CONTENT / "banks" / "mental-ability.json").read_text(encoding="utf-8"))
        questions = mocktest.bank_questions(bank)
        self.assertGreaterEqual(len(questions), 60)
        keys = [(q["stem"], tuple(q["options"])) for q in questions]
        self.assertEqual(len(keys), len(set(keys)), "duplicate question in the mental-ability bank")
        for q in questions:
            self.assertEqual(len(q["options"]), 4)
            self.assertIn(q["answer"], range(4))
            self.assertTrue(q["explanation"])

    def test_filler_prompts_are_excluded(self):
        self.assertTrue(mocktest.is_filler({"q": "The most exam-ready way to revise “X” is: (a) …"}))
        self.assertTrue(mocktest.is_filler({"q": "A 3-mark answer on “X” should: (a) …"}))
        self.assertTrue(mocktest.is_filler({"q": "“X” का सबसे उपयोगी पुनरावलोकन क्या है? (क) …"}))
        self.assertFalse(mocktest.is_filler({"q": "The HCF of 8 and 12 is: (a) 2 (b) 4 (c) 8 (d) 24"}))

    def test_no_templated_mcq_reaches_a_pool(self):
        """Study-habit prompts are copy-pasted across chapters with identical
        options. Any option set shared by four or more chapters must be caught
        by ``is_filler`` — otherwise a new template has slipped into the mocks."""
        from collections import defaultdict
        where = defaultdict(set)
        items = defaultdict(list)
        for subj in _subjects():
            for ch in build.load_chapters(subj["slug"]):
                for m in ch.get("mcq") or []:
                    parsed = mocktest.parse_mcq(m)
                    if not parsed:
                        continue
                    key = tuple(parsed["options"])
                    where[key].add(ch["id"])
                    items[key].append(m)
        templates = [k for k, chapters in where.items() if len(chapters) >= 4]
        self.assertTrue(templates, "expected the known study-habit templates to exist")
        for key in templates:
            for m in items[key]:
                self.assertTrue(mocktest.is_filler(m), f"templated MCQ not excluded: {m['q'][:80]}")

    def test_parse_mcq_handles_both_label_styles(self):
        q = mocktest.parse_mcq({"q": "Pick one: (a) x (b) y (c) z (d) w", "a": "**(c) z.** because"})
        self.assertEqual(q["options"], ["x", "y", "z", "w"])
        self.assertEqual(q["answer"], 2)
        q = mocktest.parse_mcq({"q": "चुनिए — (क) एक (ख) दो (ग) तीन (घ) चार", "a": "**(ख) दो** — कारण"})
        self.assertEqual(q["labels"], ["क", "ख", "ग", "घ"])
        self.assertEqual(q["answer"], 1)
        self.assertIsNone(mocktest.parse_mcq({"q": "Only three: (a) x (b) y (c) z", "a": "**(a)**"}))


class AssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.subjects = _subjects()
        cls.chapters = {s["slug"]: build.load_chapters(s["slug"]) for s in cls.subjects}
        cls.config, cls.exams = mocktest.prepare(cls.subjects, cls.chapters)

    def test_every_set_is_full_and_free_of_duplicates(self):
        for exam in self.exams:
            for n, paper in enumerate(exam["sets_data"], 1):
                with self.subTest(exam=exam["id"], set=n):
                    self.assertEqual(len(paper), exam["questions"])
                    uids = [q["uid"] for q in paper]
                    self.assertEqual(len(uids), len(set(uids)), "a question appears twice in one set")
                    self.assertEqual([q["n"] for q in paper], list(range(1, len(paper) + 1)))
                    for si, sec in enumerate(exam["sections"]):
                        self.assertEqual(sum(1 for q in paper if q["section"] == si), sec["count"])
                    for q in paper:
                        self.assertEqual(len(q["options"]), 4)
                        self.assertIn(q["answer"], range(4))
                        self.assertFalse(mocktest.is_filler({"q": q["stem"]}))

    def test_no_question_repeats_across_sets(self):
        # The blueprints are sized to the banks; if a bank shrinks this fails
        # loudly instead of quietly recycling questions.
        for exam in self.exams:
            with self.subTest(exam=exam["id"]):
                self.assertEqual(exam["stats"]["repeats"], 0)

    def test_assembly_is_deterministic(self):
        _, again = mocktest.prepare(self.subjects, self.chapters)
        for a, b in zip(self.exams, again):
            self.assertEqual(
                [[q["uid"] for q in p] for p in a["sets_data"]],
                [[q["uid"] for q in p] for p in b["sets_data"]],
            )

    def test_mock_for_subject_maps_every_subject(self):
        nav = mocktest.mock_for_subject(self.exams)
        for s in self.subjects:
            self.assertIn(s["slug"], nav)
        self.assertEqual(nav["hindi"], "hindi-a")

    def test_short_pool_raises(self):
        tiny = dict(self.config)
        tiny["exams"] = [{
            "id": "tiny", "group": "board", "title": "Tiny", "sets": 1, "questions": 500,
            "minutes": 10, "marks_correct": 1, "marks_wrong": 0,
            "sections": [{"name": "All", "count": 500, "pools": [{"subject": "maths"}]}],
        }]
        with self.assertRaises(ValueError):
            mocktest.assemble(tiny, self.subjects, self.chapters, mocktest.load_banks())


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="c10-mock-"))
        build.DIST = cls.tmp
        cls.written, _ = build.build()
        cls.broken, cls.checked = build.validate()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_no_broken_links_in_the_whole_site(self):
        self.assertEqual(self.broken, 0)

    def test_expected_files_per_set(self):
        config = json.loads((CONTENT / "mock-tests.json").read_text(encoding="utf-8"))
        self.assertTrue((self.tmp / "mock-test" / "index.html").exists())
        self.assertTrue((self.tmp / "assets" / "mock.js").exists())
        for exam in config["exams"]:
            folder = self.tmp / "mock-test" / exam["id"]
            self.assertTrue((folder / "index.html").exists(), exam["id"])
            for n in range(1, exam["sets"] + 1):
                for name in (f"set-{n}.html", f"set-{n}-paper.html", f"set-{n}.txt", f"set-{n}-key.txt"):
                    self.assertTrue((folder / name).exists(), f"{exam['id']}/{name}")

    def test_online_payload_matches_the_downloads(self):
        html_ = (self.tmp / "mock-test" / "maths" / "set-1.html").read_text(encoding="utf-8")
        m = re.search(r'<script type="application/json" id="mock-data">(.*?)</script>', html_, re.S)
        self.assertIsNotNone(m)
        data = json.loads(m.group(1).replace("<\\/", "</"))
        self.assertEqual(data["exam"]["id"], "maths")
        self.assertEqual(data["exam"]["set"], 1)
        self.assertEqual(len(data["questions"]), 28)
        self.assertEqual(len(data["sections"]), 7)
        key = (self.tmp / "mock-test" / "maths" / "set-1-key.txt").read_text(encoding="utf-8")
        for i, q in enumerate(data["questions"], 1):
            letter = q["labels"][q["ans"]]
            self.assertRegex(key, rf"Q\s*{i} \({re.escape(letter)}\)", f"key for Q{i} differs from the online payload")
        paper = (self.tmp / "mock-test" / "maths" / "set-1.txt").read_text(encoding="utf-8")
        self.assertIn(f"Q{len(data['questions'])}.", paper)
        self.assertNotIn("**", paper)

    def test_hubs_link_to_mock_tests(self):
        home = (self.tmp / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="mock-test/index.html"', home)
        maths = (self.tmp / "maths" / "index.html").read_text(encoding="utf-8")
        self.assertIn("../mock-test/maths/index.html", maths)
        after = (self.tmp / "after-10th" / "index.html").read_text(encoding="utf-8")
        self.assertIn("../mock-test/nvs/index.html", after)
        nsat = (self.tmp / "pw-nsat" / "index.html").read_text(encoding="utf-8")
        self.assertIn("../mock-test/pw-nsat/index.html", nsat)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class ScoringCoreTests(unittest.TestCase):
    """The browser scoring helpers are plain functions; run them in Node."""

    def run_js(self, snippet):
        script = (
            f"const core = require({json.dumps(str(SITE / 'theme' / 'mock.js'))});\n"
            f"process.stdout.write(JSON.stringify((function(){{ {snippet} }})()));"
        )
        out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30)
        return json.loads(out.stdout)

    def test_score_with_negative_marking(self):
        res = self.run_js(
            "const Q=[{sec:0,ans:0,topic:'a',topicKey:'a'},{sec:0,ans:1,topic:'a',topicKey:'a'},"
            "{sec:1,ans:2,topic:'b',topicKey:'b'},{sec:1,ans:3,topic:'b',topicKey:'b'}];"
            "const r = core.score(Q, [0, 0, 2, null], {marksCorrect: 4, marksWrong: 1});"
            "return {marks:r.marks,max:r.max,correct:r.correct,wrong:r.wrong,skipped:r.skipped,pct:r.pct,"
            "accuracy:r.accuracy,secs:r.sections.map(s=>[s.sec,s.marks,s.pct]),weak:core.weakTopics(r.topics).map(t=>t.key),"
            "grade:core.grade(r.pct),t:[core.fmtTime(65),core.fmtTime(3600),core.fmtTime(-1)]};"
        )
        self.assertEqual(res["marks"], 7)
        self.assertEqual(res["max"], 16)
        self.assertEqual((res["correct"], res["wrong"], res["skipped"]), (2, 1, 1))
        self.assertEqual(res["pct"], 44)
        self.assertEqual(res["accuracy"], 67)
        self.assertEqual(res["secs"], [[0, 3, 38], [1, 4, 50]])
        self.assertEqual(sorted(res["weak"]), ["a", "b"])
        self.assertEqual(res["grade"], "Needs practice")
        self.assertEqual(res["t"], ["01:05", "1:00:00", "00:00"])

    def test_score_never_goes_below_zero_percent(self):
        res = self.run_js(
            "const Q=[{sec:0,ans:0},{sec:0,ans:0}];"
            "const r = core.score(Q, [1, 1], {marksCorrect: 4, marksWrong: 1});"
            "return {marks:r.marks,pct:r.pct,negative:r.negative};"
        )
        self.assertEqual(res["marks"], -2)
        self.assertEqual(res["pct"], 0)
        self.assertEqual(res["negative"], 2)


if __name__ == "__main__":
    unittest.main()
