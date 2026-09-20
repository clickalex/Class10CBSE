"""Mock-test blueprints, the question pools and the generated engine pages.

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

    def test_every_exam_offers_ten_mocks(self):
        for exam in self.config["exams"]:
            with self.subTest(exam=exam["id"]):
                self.assertEqual(exam.get("tests"), 10, "every exam must offer 10 mock slots")

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


class PoolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.subjects = _subjects()
        cls.chapters = {s["slug"]: build.load_chapters(s["slug"]) for s in cls.subjects}
        cls.config, cls.exams = mocktest.prepare(cls.subjects, cls.chapters)
        cls.by_id = {e["id"]: e for e in cls.exams}

    def test_every_section_pool_covers_its_count(self):
        for exam in self.exams:
            for sd in exam["sections_data"]:
                with self.subTest(exam=exam["id"], section=sd["name"]):
                    self.assertGreaterEqual(
                        len(sd["questions"]), sd["count"],
                        f"pool has {len(sd['questions'])} questions for {sd['count']} slots",
                    )
                    for q in sd["questions"].values():
                        self.assertEqual(len(q["options"]), 4)
                        self.assertIn(q["answer"], range(4))
                        self.assertTrue(q["explanation"])
                        self.assertFalse(mocktest.is_filler({"q": q["stem"]}))

    def test_pools_have_unique_questions(self):
        for exam in self.exams:
            with self.subTest(exam=exam["id"]):
                pool = exam["pool_data"]
                stems = [(q["stem"], tuple(q["options"])) for q in pool.values()]
                self.assertEqual(len(stems), len(set(stems)), "duplicate question inside one pool")
                for sd in exam["sections_data"]:
                    self.assertLessEqual(set(sd["questions"]), set(pool), "section pool outside the page pool")

    def test_every_chapter_with_mcqs_is_mockable(self):
        mockable = set()
        for e in self.exams:
            mockable |= {(e["subject"], c["id"]) for c in e["chapters_data"]}
        for subj in self.subjects:
            for ch in self.chapters.get(subj["slug"]) or []:
                n = len(mocktest.chapter_questions(subj, ch))
                with self.subTest(subject=subj["slug"], chapter=ch["id"]):
                    if n:
                        self.assertIn(
                            (subj["slug"], ch["id"]), mockable,
                            f"{subj['slug']}/{ch['id']} has {n} MCQs but no chapter mock",
                        )
                    else:
                        self.assertNotIn((subj["slug"], ch["id"]), mockable)

    def test_chapter_mock_serves_every_mcq_of_the_chapter(self):
        for e in self.exams:
            for c in e["chapters_data"]:
                with self.subTest(exam=e["id"], chapter=c["id"]):
                    n = sum(1 for q in e["pool_data"].values() if q["chapter_id"] == c["id"])
                    self.assertEqual(n, c["n"], "chapter mock count must match the pool")

    def test_hindi_courses_split_their_chapters(self):
        a, b = self.by_id["hindi-a"], self.by_id["hindi-b"]
        total = len(self.chapters["hindi"])
        a_ids = {c["id"] for c in a["chapters_data"]}
        b_ids = {c["id"] for c in b["chapters_data"]}
        self.assertLess(len(a_ids), total, "hindi-a must not list every hindi chapter")
        self.assertLess(len(b_ids), total, "hindi-b must not list every hindi chapter")
        all_mockable = {c["id"] for c in a["chapters_data"]} | {c["id"] for c in b["chapters_data"]}
        for ch in self.chapters["hindi"]:
            if mocktest.chapter_questions(self.by_id["hindi-a"] and _subj("hindi"), ch):
                self.assertIn(ch["id"], all_mockable)

    def test_short_pool_raises(self):
        tiny = dict(self.config)
        tiny["exams"] = [{
            "id": "tiny", "group": "board", "title": "Tiny", "tests": 10, "questions": 500,
            "minutes": 10, "marks_correct": 1, "marks_wrong": 0,
            "sections": [{"name": "All", "count": 500, "pools": [{"subject": "maths"}]}],
        }]
        with self.assertRaises(ValueError):
            mocktest.assemble(tiny, self.subjects, self.chapters, mocktest.load_banks())

    def test_mock_for_subject_maps_every_subject(self):
        nav = mocktest.mock_for_subject(self.exams)
        for s in self.subjects:
            self.assertIn(s["slug"], nav)
        self.assertEqual(nav["hindi"], "hindi-a")

    def test_mock_chapter_hosts_cover_every_mockable_chapter(self):
        hosts = mocktest.mock_chapter_hosts(self.exams)
        by_id = self.by_id
        for e in self.exams:
            for c in e["chapters_data"]:
                with self.subTest(exam=e["id"], chapter=c["id"]):
                    host = hosts.get((e["subject"], c["id"]))
                    self.assertIsNotNone(host, f"{c['id']} has no hosting page")
                    self.assertIn(c["id"], {x["id"] for x in by_id[host]["chapters_data"]},
                                  f"{c['id']} hosted on {host}, which does not list it")


def _subj(slug):
    return next(s for s in _subjects() if s["slug"] == slug)


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

    def test_expected_files_per_exam(self):
        config = json.loads((CONTENT / "mock-tests.json").read_text(encoding="utf-8"))
        self.assertTrue((self.tmp / "mock-test" / "index.html").exists())
        self.assertTrue((self.tmp / "assets" / "mock.js").exists())
        for exam in config["exams"]:
            folder = self.tmp / "mock-test" / exam["id"]
            self.assertTrue((folder / "index.html").exists(), exam["id"])
            self.assertTrue((folder / "test.html").exists(), exam["id"])
            self.assertFalse(list(folder.glob("set-*")), f"{exam['id']} still has fixed set files")

    def test_engine_payload_is_well_formed(self):
        html_ = (self.tmp / "mock-test" / "maths" / "test.html").read_text(encoding="utf-8")
        self.assertNotIn("</scr" + "ipt>\"", html_)  # the payload must stay escapable
        m = re.search(r'<script type="application/json" id="mock-data">(.*?)</script>', html_, re.S)
        self.assertIsNotNone(m)
        data = json.loads(m.group(1).replace("<\\/", "</"))
        self.assertEqual(data["exam"]["id"], "maths")
        self.assertEqual(data["exam"]["tests"], 10)
        self.assertEqual(len(data["sections"]), 7)
        for sec in data["sections"]:
            self.assertGreaterEqual(len(sec["ids"]), sec["count"])
            self.assertEqual(len(sec["ids"]), len(set(sec["ids"])))
        uids = [q["uid"] for q in data["pool"]]
        self.assertEqual(len(uids), len(set(uids)), "pool has duplicate uids")
        for q in data["pool"]:
            self.assertEqual(len(q["o"]), 4)
            self.assertIn(q["a"], range(4))
            self.assertTrue(q["e"])
            self.assertNotIn("**", q["s"])
        pool_ids = set(uids)
        for sec in data["sections"]:
            self.assertLessEqual(set(sec["ids"]), pool_ids, "section ids must live in the pool")
        self.assertEqual(len(data["chapters"]), 14, "maths chapter mocks")
        for c in data["chapters"]:
            n = sum(1 for q in data["pool"] if q["ch"] == c["id"])
            self.assertEqual(n, c["n"])

    def test_exam_page_lists_ten_slots_and_chapter_mocks(self):
        for exam in ("maths", "nvs", "hindi-b"):
            html_ = (self.tmp / "mock-test" / exam / "index.html").read_text(encoding="utf-8")
            with self.subTest(exam=exam):
                for n in range(1, 11):
                    self.assertIn(f'href="test.html?n={n}"', html_)
                self.assertIn('data-mock-slot-best="%s/10"' % exam, html_)
        maths = (self.tmp / "mock-test" / "maths" / "index.html").read_text(encoding="utf-8")
        self.assertGreater(maths.count("test.html?chapter="), 10)
        nvs = (self.tmp / "mock-test" / "nvs" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("test.html?chapter=", nvs, "entrance exams have no chapter mocks")

    def test_chapter_pages_link_to_their_chapter_mock(self):
        subjects = _subjects()
        linked = 0
        for subj in subjects:
            folder = self.tmp / subj["slug"] / "chapters"
            if not folder.is_dir():
                continue
            for f in folder.glob("*.html"):
                html_ = f.read_text(encoding="utf-8")
                m = re.search(r'href="(\.\./\.\./mock-test/[a-z0-9-]+)/test\.html\?chapter=([a-z0-9-]+)"', html_)
                if m:
                    linked += 1
                    target = self.tmp / "mock-test" / m.group(1).split("/")[-1] / "test.html"
                    self.assertTrue(target.exists(), f"{f.name} -> {m.group(1)}")
        self.assertGreater(linked, 100, "chapter pages should carry the mock-test button")

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
    """The generator and scoring helpers are plain functions; run them in Node."""

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

    def test_generator_respects_sections_and_avoids_repeats(self):
        res = self.run_js(
            "const secs=[{name:'A',count:5,ids:['a1','a2','a3','a4','a5','a6','a7','a8','a9','a10']},"
            "{name:'B',count:3,ids:['b1','b2','b3','b4','b5','b6']}];"
            "const byId={};"
            "secs.forEach(s=>s.ids.forEach(id=>byId[id]={uid:id,ord:1,ans:0,opts:[1,2,3,4]}));"
            "const g1=core.generate(secs,byId,[],[]);"
            "const g2=core.generate(secs,byId,g1.questions.map(q=>q.uid),g1.questions.map(q=>q.uid));"
            "return {"
            " n1:g1.questions.length, fresh1:g1.fresh, n2:g2.questions.length, fresh2:g2.fresh,"
            " overlap:g2.questions.filter(q=>g1.questions.some(p=>p.uid===q.uid)).length,"
            " secCounts:[g2.questions.filter(q=>q.sec===0).length, g2.questions.filter(q=>q.sec===1).length],"
            " numbered:g2.questions.every((q,i)=>q.n===i+1), dup:g2.questions.length===new Set(g2.questions.map(q=>q.uid)).size"
            "};"
        )
        self.assertEqual(res["n1"], 8)
        self.assertEqual(res["fresh1"], 8)
        self.assertEqual(res["n2"], 8)
        self.assertEqual(res["fresh2"], 8, "second paper must be fully fresh (pools 10 and 6)")
        self.assertEqual(res["overlap"], 0, "no question repeats from the previous paper")
        self.assertEqual(res["secCounts"], [5, 3])
        self.assertTrue(res["numbered"])
        self.assertTrue(res["dup"])

    def test_generator_cycles_only_when_the_pool_is_exhausted(self):
        """Pool of 8, papers of 4: papers 1 and 2 are fully fresh; paper 3
        must cycle but still avoid the immediately previous batch."""
        res = self.run_js(
            "const secs=[{name:'A',count:4,ids:['a1','a2','a3','a4','a5','a6','a7','a8']}];"
            "const byId={}; secs[0].ids.forEach(id=>byId[id]={uid:id,ord:1,ans:0,opts:[1,2,3,4]});"
            "const g1=core.generate(secs,byId,[],[]);"
            "const g2=core.generate(secs,byId,g1.questions.map(q=>q.uid),g1.questions.map(q=>q.uid));"
            "const seen3=g1.questions.concat(g2.questions).map(q=>q.uid);"
            "const g3=core.generate(secs,byId,seen3,g2.questions.map(q=>q.uid));"
            "return {fresh1:g1.fresh, fresh2:g2.fresh,"
            " overlap2:g2.questions.filter(q=>g1.questions.some(p=>p.uid===q.uid)).length,"
            " fresh3:g3.fresh,"
            " lastOverlap:g3.questions.filter(q=>g2.questions.some(p=>p.uid===q.uid)).length,"
            " backToG1:g3.questions.filter(q=>g1.questions.some(p=>p.uid===q.uid)).length};"
        )
        self.assertEqual(res["fresh1"], 4)
        self.assertEqual(res["fresh2"], 4)
        self.assertEqual(res["overlap2"], 0)
        self.assertEqual(res["fresh3"], 0, "the whole pool has been served by now")
        self.assertEqual(res["lastOverlap"], 0, "the immediately previous batch is avoided while older questions exist")
        self.assertEqual(res["backToG1"], 4, "cycling returns to the oldest served batch first")

    def test_generator_keeps_sections_disjoint(self):
        """Two sections drawing from the same ids must not share a question."""
        res = self.run_js(
            "const ids=['a1','a2','a3','a4'];"
            "const secs=[{name:'A',count:2,ids:ids},{name:'B',count:2,ids:ids}];"
            "const byId={}; ids.forEach(id=>byId[id]={uid:id,ord:1,ans:0,opts:[1,2,3,4]});"
            "const g=core.generate(secs,byId,[],[]);"
            "return {n:g.questions.length, unique:new Set(g.questions.map(q=>q.uid)).size,"
            " shared:g.questions.filter(q=>q.sec===1).filter(q=>g.questions.some(p=>p.sec===0&&p.uid===q.uid)).length};"
        )
        self.assertEqual(res["n"], 4)
        self.assertEqual(res["unique"], 4)
        self.assertEqual(res["shared"], 0, "two sections must not share a question")

    def test_plain_text_strips_the_inline_html(self):
        res = self.run_js(
            "return {a: core.plainText('<strong>H</strong>₂O &amp; <em>life</em>'),"
            " b: core.plainText('5 &lt; 6 and 7 &gt; 2'),"
            " c: core.plainText('  lots   of   space  ')};"
        )
        self.assertEqual(res["a"], "H₂O & life")
        self.assertEqual(res["b"], "5 < 6 and 7 > 2")
        self.assertEqual(res["c"], "lots of space")

    def test_paper_and_key_text_are_buildable(self):
        res = self.run_js(
            "const meta={title:'Test Exam',code:'X01',label:'Mock 1',minutes:60,"
            " marking:{marksCorrect:4,marksWrong:1},maxMarks:200,length:'Mock',patternNote:'note',"
            " sections:[{name:'Maths'},{name:'Physics'}],onlineUrl:'https://x/y'};"
            "const Q=[{n:1,sec:0,stem:'2+2 = <strong>4</strong>?',labels:['a','b','c','d'],ans:1,"
            " opts:['3','4','5','6'],exp:'**(b) 4.** yes',topic:'Ch 1 · Sums',src:'Maths',ctx:''},"
            "{n:2,sec:1,stem:'Unit of force?',labels:['a','b','c','d'],ans:0,"
            " opts:['N','J','W','Pa'],exp:'<strong>(a) N.</strong> newton',topic:'Ch 2 · Forces',src:'Science',ctx:'From a chapter'}];"
            "const p=core.paperText(meta,Q), k=core.keyText(meta,Q);"
            "return {pHasExam:p.includes('Test Exam (X01)'), pHasQ1:p.includes('Q1. 2+2 = 4?'),"
            " pNoHtml:!p.includes('<'), pGrid:p.includes('ANSWER GRID'),"
            " kQuick:k.includes('Q2 (a)')||k.includes('Q  2 (a)'), kExp:k.includes('Q2. (a) N. newton'),"
            " kMark:k.includes('correct x 4 - wrong x 1')};"
        )
        self.assertTrue(res["pHasExam"])
        self.assertTrue(res["pHasQ1"])
        self.assertTrue(res["pNoHtml"])
        self.assertTrue(res["pGrid"])
        self.assertTrue(res["kQuick"])
        self.assertTrue(res["kExp"])
        self.assertTrue(res["kMark"])


if __name__ == "__main__":
    unittest.main()
