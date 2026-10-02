"""Direct downloads: official CBSE links, the hub's own question-bank files,
save-as-PDF printing and the link checker.

What these pin down:

  * site/content/downloads.json only ever names https files on CBSE's two
    hosts, covers every subject, and its URLs follow CBSE's directory scheme
    (so a typo in a session or sitting cannot ship);
  * every subject's PYQ page offers every one of its official files, and every
    bank page offers the hub's own .txt files, which really exist;
  * the .txt exports hold every written Q&A and MCQ exactly once and show the
    same text the page shows, byte-stable between builds;
  * print.js opens answers for a print and puts the page back afterwards;
  * scripts/check_downloads.py tells a good file from a missing one, an HTML
    "soft 404", and a server that is simply not there.

Run with:  python3 -m unittest tests.test_downloads -v
"""
import contextlib
import copy
import html
import io
import http.server
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
sys.path.insert(0, str(SITE))

import downloads  # noqa: E402
import layout  # noqa: E402

_spec = importlib.util.spec_from_file_location("build", SITE / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

_cd = importlib.util.spec_from_file_location("check_downloads", ROOT / "scripts" / "check_downloads.py")
check_downloads = importlib.util.module_from_spec(_cd)
_cd.loader.exec_module(check_downloads)

JS = SITE / "theme" / "js" / "print.js"


def _subjects():
    return json.loads((SITE / "content" / "subjects.json").read_text(encoding="utf-8"))


def _label(q):
    return build.TYPE_META[build.infer_qa_type(q)][1]


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_strings(item)
    elif isinstance(obj, dict):
        for item in obj.values():
            yield from _walk_strings(item)


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = downloads.load()
        cls.slugs = [s["slug"] for s in _subjects()]

    def test_manifest_is_valid(self):
        self.assertEqual(downloads.validate(self.data, self.slugs), [])

    def test_every_subject_has_papers_for_every_course(self):
        self.assertEqual(sorted(self.data["subjects"]), sorted(self.slugs))
        for slug, entry in self.data["subjects"].items():
            for course in entry["courses"]:
                self.assertGreaterEqual(len(course["pyq"]), 4, f"{slug}/{course['id']}")
                self.assertIn("2026-27", course["sqp"], f"{slug}/{course['id']}")

    def test_only_https_cbse_files_are_linked(self):
        for what, url in downloads.file_urls(self.data) + downloads.list_urls(self.data):
            self.assertRegex(url, r"^https://(www\.cbse\.gov\.in|cbseacademic\.nic\.in)/", what)
        for what, url in downloads.file_urls(self.data):
            self.assertRegex(url, r"\.(pdf|zip)$", what)

    def test_urls_follow_cbses_directory_scheme(self):
        """A paper filed under the wrong sitting or session is a wrong download."""
        base = {"2026": "https://www.cbse.gov.in/cbsenew/question-paper/2026/X/",
                "2026-second": "https://www.cbse.gov.in/cbsenew/question-paper/2026-COMPTT/Second_Board_X/",
                "2025": "https://www.cbse.gov.in/cbsenew/question-paper/2025/X/",
                "2025-compartment": "https://www.cbse.gov.in/cbsenew/question-paper/2025-COMPTT/X/",
                "2024": "https://www.cbse.gov.in/cbsenew/question-paper/2024/X/"}
        self.assertEqual({s["id"] for s in self.data["sittings"]}, set(base))
        for slug, entry in self.data["subjects"].items():
            for course in entry["courses"]:
                for sitting, f in course["pyq"].items():
                    self.assertTrue(f["url"].startswith(base[sitting]), f"{slug} {sitting}: {f['url']}")
                for session, f in course["sqp"].items():
                    folder = f"ClassX_{session.replace('-', '_')}/"
                    if slug == "information-technology":
                        self.assertIn("/Curriculum26/SQP_MS_X/402_", f["sqp"])
                        self.assertIn("/Curriculum26/SQP_MS_X/402_", f["ms"])
                        continue
                    self.assertRegex(f["sqp"], rf"/web_material/SQP/{folder}[A-Za-z]+-SQP\.pdf$")
                    self.assertRegex(f["ms"], rf"/web_material/SQP/{folder}[A-Za-z]+-MS\.pdf$")
                    # the paper and its marking scheme share a stem
                    self.assertEqual(f["sqp"][:-len("-SQP.pdf")], f["ms"][:-len("-MS.pdf")])

    def test_a_course_never_lists_the_same_file_twice(self):
        for slug, entry in self.data["subjects"].items():
            for course in entry["courses"]:
                urls = [f["url"] for f in course["pyq"].values()]
                self.assertEqual(len(urls), len(set(urls)), f"{slug}/{course['id']}")

    def test_validate_rejects_bad_manifests(self):
        def broken(mutate):
            data = copy.deepcopy(self.data)
            mutate(data)
            return downloads.validate(data, self.slugs)

        maths = lambda d: d["subjects"]["maths"]["courses"][0]
        self.assertTrue(broken(lambda d: maths(d)["pyq"]["2026"].update(url="http://www.cbse.gov.in/x.zip")))
        self.assertTrue(broken(lambda d: maths(d)["pyq"]["2026"].update(url="https://evil.example/x.zip")))
        self.assertTrue(broken(lambda d: maths(d)["pyq"]["2026"].update(url="https://www.cbse.gov.in/x.exe")))
        self.assertTrue(broken(lambda d: maths(d)["pyq"]["2026"].update(url="https://www.cbse.gov.in/a b.zip")))
        self.assertTrue(broken(lambda d: maths(d)["pyq"]["2026"].update(size="big")))
        self.assertTrue(broken(lambda d: maths(d)["pyq"].update({"1999": {"url": "https://www.cbse.gov.in/x.zip"}})))
        self.assertTrue(broken(lambda d: maths(d)["sqp"].update({"2030-31": {"sqp": "https://cbseacademic.nic.in/a.pdf",
                                                                           "ms": "https://cbseacademic.nic.in/b.pdf"}})))
        self.assertTrue(broken(lambda d: d["subjects"].pop("sanskrit")))
        self.assertTrue(broken(lambda d: d["subjects"].update(klingon={"courses": []})))
        self.assertTrue(broken(lambda d: d.update(checked_on="yesterday")))
        self.assertTrue(broken(lambda d: d.update(version=2)))
        self.assertTrue(broken(lambda d: d["lists"]["qb"].update(url="https://example.com/qb.html")))

    def test_a_broken_manifest_fails_the_build(self):
        saved = downloads.load
        downloads.load = lambda *a, **k: {**copy.deepcopy(self.data), "version": 99}
        tmp = Path(tempfile.mkdtemp(prefix="c10-badman-"))
        old = build.DIST
        build.DIST = tmp
        try:
            with self.assertRaisesRegex(ValueError, "downloads.json"):
                build.build()
        finally:
            build.DIST = old
            downloads.load = saved
            shutil.rmtree(tmp, ignore_errors=True)


class BuiltSiteTests(unittest.TestCase):
    """One build into a scratch folder, then look at what it published."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="c10-dl-"))
        saved = build.DIST
        build.DIST = cls.tmp
        try:
            cls.written, _ = build.build()
        finally:
            build.DIST = saved
        cls.data = downloads.load()
        cls.subjects = _subjects()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def page(self, rel):
        return (self.tmp / rel).read_text(encoding="utf-8")

    def test_downloads_page_is_published_and_listed(self):
        self.assertIn("downloads/index.html", self.written)
        text = self.page("downloads/index.html")
        self.assertIn("<h1>Previous-year papers &amp; question banks</h1>", text)
        for subj in self.subjects:
            self.assertIn(f'<section class="dl" id="{subj["slug"]}">', text, subj["slug"])
        self.assertIn("downloads/index.html</loc>", self.page("sitemap.xml"))
        self.assertIn('name="description" content="Direct download links', text)

    def test_every_pyq_page_offers_every_official_file(self):
        for subj in self.subjects:
            slug = subj["slug"]
            text = self.page(f"{slug}/pyq.html")
            self.assertIn('<section class="dl" id="downloads">', text, slug)
            wanted = [u for what, u in downloads.file_urls(self.data)
                      if what.startswith(slug + "/")]
            self.assertGreaterEqual(len(wanted), 5, slug)
            for url in wanted:
                self.assertIn(f'href="{html.escape(url)}"', text, f"{slug}: {url}")

    def test_every_bank_page_links_real_text_files(self):
        for subj in self.subjects:
            slug = subj["slug"]
            text = self.page(f"{slug}/question-bank.html")
            whole = f"../downloads/{slug}/class10-{slug}-question-bank.txt"
            self.assertIn(f'href="{whole}" download', text, slug)
            self.assertTrue((self.tmp / "downloads" / slug / f"class10-{slug}-question-bank.txt").is_file())
            for ch in build.load_chapters(slug):
                name = f"class10-{slug}-{ch['id']}.txt"
                self.assertIn(f'href="../downloads/{slug}/{name}" download', text, name)
                self.assertTrue((self.tmp / "downloads" / slug / name).is_file(), name)

    def test_official_bank_is_offered_where_cbse_publishes_one(self):
        for slug, name in (("maths", "MathsX.pdf"), ("science", "ScienceX.pdf"), ("english", "EnglishX.pdf")):
            self.assertIn(f"/web_material/QuestionBank/ClassX/{name}", self.page(f"{slug}/question-bank.html"))
        for slug in ("sanskrit", "information-technology"):
            self.assertIn("has not published a Class X question bank", self.page(f"{slug}/question-bank.html"))

    def test_two_course_subjects_get_two_columns(self):
        for slug, labels in (("maths", ("Standard (041)", "Basic (241)")), ("hindi", ("Course A (002)", "Course B (085)"))):
            text = self.page(f"{slug}/pyq.html")
            for label in labels:
                self.assertIn(f'<th scope="col">{label}</th>', text)
        # Maths 2026: one ZIP covers both papers, so it is one merged cell
        self.assertIn('colspan="2"', self.page("maths/pyq.html"))
        self.assertNotIn('colspan="2"', self.page("science/pyq.html"))

    def test_missing_papers_are_said_not_skipped(self):
        # CBSE lists no 2026 second-exam paper for Computer Applications
        self.assertIn("Not listed by CBSE", self.page("computer-applications/pyq.html"))

    def test_external_links_are_safe_and_open_in_a_new_tab(self):
        offenders = []
        for path in self.tmp.rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            for tag in re.findall(r"<a [^>]*>", text):
                if 'target="_blank"' in tag and "noopener" not in tag:
                    offenders.append(f"{path.relative_to(self.tmp)}: {tag[:80]}")
                if re.search(r'href="https://(www\.cbse\.gov\.in|cbseacademic\.nic\.in)/web_material|cbsenew/question-paper/', tag) \
                        and 'rel="noopener noreferrer"' not in tag:
                    offenders.append(f"{path.relative_to(self.tmp)}: {tag[:80]}")
        self.assertEqual(offenders, [])

    def test_navigation_leads_to_the_downloads(self):
        for rel in ("index.html", "maths/index.html", "maths/chapters/ch01-real-numbers.html",
                    "mock-test/index.html", "downloads/index.html"):
            depth = rel.count("/")
            href = "../" * depth + "downloads/index.html"
            self.assertIn(f'href="{href}"', self.page(rel), rel)
        self.assertIn('aria-current="page"><span class="toc-num">PDF</span>', self.page("downloads/index.html"))
        self.assertIn('<a class="toc-item" href="../downloads/index.html"><span class="toc-num">PDF</span>',
                      self.page("maths/index.html"))
        self.assertIn("downloads/index.html", self.page("index.html"))

    def test_hub_cards_stop_calling_trend_notes_practice(self):
        hub = self.page("maths/index.html")
        self.assertNotIn("PYQ practice", hub)
        self.assertIn("Previous-year papers", hub)

    def test_answer_pages_load_print_js_and_the_rest_do_not(self):
        for rel in ("maths/question-bank.html", "maths/drill.html",
                    "maths/practice/ch01-real-numbers.html"):
            self.assertIn("assets/js/print.js", self.page(rel), rel)
        for rel in ("maths/revision.html", "maths/syllabus.html", "downloads/index.html"):
            self.assertNotIn("print.js", self.page(rel), rel)
        self.assertTrue((self.tmp / "assets" / "js" / "print.js").is_file())

    def test_save_as_pdf_buttons_match_the_script_contract(self):
        text = self.page("maths/question-bank.html")
        self.assertIn('data-save-pdf="answers"', text)
        self.assertIn('data-save-pdf="questions"', text)
        scopes = re.findall(r'data-scope="([^"]+)"', text)
        ids = set(re.findall(r'<section class="qblock" id="([^"]+)"', text))
        self.assertEqual(set(scopes), ids, "every chapter row must scope to a real section")
        js = JS.read_text(encoding="utf-8")
        for needle in ("data-save-pdf", "data-scope", "beforeprint", "afterprint", "details.qans"):
            self.assertIn(needle, js)

    def test_printed_pages_keep_the_disclaimer_and_the_credit(self):
        """The footer is what says "not official CBSE papers" and who made the hub:
        a saved PDF must keep both, so print hides only the footer's link lists."""
        for rel in ("maths/question-bank.html", "maths/drill.html", "maths/practice/ch01-real-numbers.html"):
            footer = re.search(r"<footer.*?</footer>", self.page(rel), re.S).group(0)
            self.assertIn("not official CBSE papers", footer, rel)
            self.assertIn(f'<p class="credit">Created by <strong>{layout.CREDIT}</strong></p>', footer, rel)
        css = (SITE / "theme" / "css" / "style.css").read_text(encoding="utf-8")
        generic = css[css.rindex("/* ---------- print: bank, drill"):]
        hidden = generic[:generic.index("{ display: none !important; }")]
        self.assertIn("body:not(.mock-page) .foot-subj", hidden)
        self.assertNotRegex(hidden, r"\.foot(?![-\w])", "the footer itself must stay in print")
        self.assertNotIn(".credit", hidden)

    def test_print_stylesheet_covers_the_hooks_the_markup_uses(self):
        css = (SITE / "theme" / "css" / "style.css").read_text(encoding="utf-8")
        for needle in ('body[data-print="questions"] .qans', "body[data-print-scope] .qblock:not(.is-print-scope)",
                       ".sr-only", ".dl-table", ".dl-btn", ".linkbtn", "details.qans > summary"):
            self.assertIn(needle, css, needle)
        # the mock-test print rules must stay scoped to the mock pages
        generic = css[css.rindex("/* ---------- print: bank, drill"):]
        self.assertNotIn("\nbody {", generic)
        self.assertIn("body:not(.mock-page) .sidebar", generic)

    def test_download_links_are_not_blocked_by_the_global_ignore_rules(self):
        """*.pdf and *.zip are git-ignored; a generated file with those suffixes would silently not ship."""
        ignored = {line.strip() for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()}
        for path in (self.tmp / "downloads").rglob("*"):
            if path.is_file():
                self.assertNotIn(f"*{path.suffix}", ignored, path.name)


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.subjects = _subjects()
        cls.chapters = {s["slug"]: build.load_chapters(s["slug"]) for s in cls.subjects}
        cls.files = downloads.export_files(cls.subjects, cls.chapters, _label)

    def test_one_file_per_subject_and_per_chapter(self):
        want = sum(1 + len(c) for c in self.chapters.values())
        self.assertEqual(len(self.files), want)
        self.assertIn("maths/class10-maths-question-bank.txt", self.files)
        self.assertIn("hindi/class10-hindi-ch01-sur-ke-pad.txt", self.files)

    def test_every_question_appears_exactly_once(self):
        for slug, chapters in self.chapters.items():
            n_qa = sum(len(c["qa"]) for c in chapters)
            n_mcq = sum(len(c["mcq"]) for c in chapters)
            whole = self.files[f"{slug}/class10-{slug}-question-bank.txt"]
            self.assertEqual(len(re.findall(r"^Q\d+\. \[", whole, re.M)), n_qa, slug)
            self.assertEqual(len(re.findall(r"^M\d+\. ", whole, re.M)), n_mcq, slug)
            self.assertEqual(whole.count("\n    Ans:"), n_qa + n_mcq, slug)
            for ch in chapters:
                part = self.files[f"{slug}/class10-{slug}-{ch['id']}.txt"]
                self.assertEqual(len(re.findall(r"^Q\d+\. \[", part, re.M)), len(ch["qa"]), ch["id"])
                self.assertEqual(len(re.findall(r"^M\d+\. ", part, re.M)), len(ch["mcq"]), ch["id"])
                self.assertIn(f"CHAPTER {ch['num']} \u00b7 {ch['title']}", part)

    def test_no_inline_markup_leaks_into_the_text(self):
        # (Literal <br> and <p> are fine: the Computer Applications chapters teach HTML.
        # The exact-match test below covers everything else.)
        leaks = []
        for rel, text in self.files.items():
            if "**" in text:
                leaks.append(f"{rel}: bold markers")
            if re.search(r"`[^`\n]+`", text):
                leaks.append(f"{rel}: backtick code span")
        self.assertEqual(leaks, [])

    def test_plain_text_is_exactly_what_the_page_shows(self):
        """plain() must agree with build.inline() on every string in the content."""
        checked = 0
        for path in sorted((SITE / "content").rglob("*.json")):
            for s in _walk_strings(json.loads(path.read_text(encoding="utf-8"))):
                shown = html.unescape(re.sub(r"<[^>]+>", "", build.inline(s)))
                self.assertEqual(downloads.plain(s), shown, f"{path.name}: {s[:70]!r}")
                checked += 1
        self.assertGreater(checked, 20000)

    def test_files_are_utf8_with_a_bom_and_keep_devanagari(self):
        raw = self.files["hindi/class10-hindi-question-bank.txt"]
        self.assertTrue(raw.startswith("\ufeff"))
        data = raw.encode("utf-8")
        self.assertEqual(data[:3], b"\xef\xbb\xbf")
        self.assertIn("ब्रजभाषा", data.decode("utf-8"))
        self.assertIn("Subject Code 002", raw.split("\n")[0])

    def test_export_is_deterministic(self):
        again = downloads.export_files(self.subjects, self.chapters, _label)
        self.assertEqual(again, self.files)

    def test_tables_and_lists_render_as_text(self):
        table = downloads._block_lines([{"table": {"head": ["Port", "Use"], "rows": [["80", "HTTP"]]}}])
        self.assertEqual(table, ["Port | Use", "---- | ---", "80 | HTTP"])
        self.assertEqual(downloads._block_lines(["- one", "2. two", "plain **bold**"]),
                         ["\u2022 one", "2. two", "plain bold"])

    def test_names_are_descriptive_because_students_share_them(self):
        self.assertEqual(downloads.export_name("maths"), "class10-maths-question-bank.txt")
        self.assertEqual(downloads.export_name("maths", "ch01-real-numbers"), "class10-maths-ch01-real-numbers.txt")


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class PrintScriptTests(unittest.TestCase):
    """print.js against a stub document: no browser needed."""

    HARNESS = r"""
const core = require(%(js)s);
const handlers = {}, winHandlers = {};
const attrs = {};
const body = { setAttribute(k, v) { attrs[k] = v; }, removeAttribute(k) { delete attrs[k]; } };
const details = [{ open: false }, { open: true }, { open: false }];
const classes = new Set();
const section = { classList: { add(c) { classes.add(c); }, remove(c) { classes.delete(c); } } };
const doc = {
  body,
  querySelectorAll(sel) { return sel === "details.qans" ? details : []; },
  getElementById(id) { return id === "ch1" ? section : null; },
  addEventListener(type, fn) { handlers[type] = fn; },
};
const snapshots = [];
const win = {
  addEventListener(type, fn) { winHandlers[type] = fn; },
  print() {
    winHandlers.beforeprint();
    snapshots.push({ attrs: Object.assign({}, attrs), open: details.map(d => d.open), scope: [...classes] });
    winHandlers.afterprint();
  },
};
core.bind(win, doc);
function button(mode, scope) {
  const el = { getAttribute(n) { return n === "data-save-pdf" ? mode : (n === "data-scope" ? scope : null); } };
  return { target: { closest(sel) { return sel === "[data-save-pdf]" ? el : null; } }, preventDefault() {} };
}
function after() { return { attrs: Object.assign({}, attrs), open: details.map(d => d.open), scope: [...classes] }; }
const out = (function () { %(snippet)s })();
process.stdout.write(JSON.stringify(out));
"""

    def run_js(self, snippet):
        script = self.HARNESS % {"js": json.dumps(str(JS)), "snippet": snippet}
        out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_answers_mode_opens_everything_then_restores_the_page(self):
        r = self.run_js("handlers.click(button('answers', null)); return {during: snapshots[0], after: after()};")
        self.assertEqual(r["during"]["attrs"], {"data-print": "answers"})
        self.assertEqual(r["during"]["open"], [True, True, True])
        self.assertEqual(r["after"]["attrs"], {})
        self.assertEqual(r["after"]["open"], [False, True, False], "only the answers print.js opened are closed again")

    def test_questions_mode_leaves_answers_alone(self):
        r = self.run_js("handlers.click(button('questions', null)); return {during: snapshots[0], after: after()};")
        self.assertEqual(r["during"]["attrs"], {"data-print": "questions"})
        self.assertEqual(r["during"]["open"], [False, True, False])
        self.assertEqual(r["after"]["attrs"], {})

    def test_scope_marks_one_section_and_is_removed_afterwards(self):
        r = self.run_js("handlers.click(button('answers', 'ch1')); return {during: snapshots[0], after: after()};")
        self.assertEqual(r["during"]["attrs"], {"data-print": "answers", "data-print-scope": "ch1"})
        self.assertEqual(r["during"]["scope"], ["is-print-scope"])
        self.assertEqual(r["after"]["scope"], [])
        self.assertEqual(r["after"]["attrs"], {})

    def test_unknown_scope_prints_the_whole_page(self):
        r = self.run_js("handlers.click(button('answers', 'nope')); return snapshots[0];")
        self.assertEqual(r["attrs"], {"data-print": "answers"})

    def test_plain_ctrl_p_prints_the_answers_too(self):
        r = self.run_js("win.print(); return {during: snapshots[0], after: after()};")
        self.assertEqual(r["during"]["attrs"], {"data-print": "answers"})
        self.assertEqual(r["during"]["open"], [True, True, True])
        self.assertEqual(r["after"]["open"], [False, True, False])

    def test_unknown_mode_falls_back_to_answers(self):
        r = self.run_js("handlers.click(button('whatever', null)); return snapshots[0];")
        self.assertEqual(r["attrs"], {"data-print": "answers"})

    def test_clicks_elsewhere_do_nothing(self):
        r = self.run_js("handlers.click({target: {closest() { return null; }}}); return snapshots.length;")
        self.assertEqual(r, 0)


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, kind, body=b"x", head=False):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _route(self, head):
        path = self.path
        if path == "/ok.pdf":
            self._send(200, "application/pdf", head=head)
        elif path == "/ok.zip":
            self._send(200, "application/zip", head=head)
        elif path == "/soft404.pdf":
            self._send(200, "text/html; charset=utf-8", b"<html>Page not found</html>", head=head)
        elif path == "/no-head.pdf":
            if head:
                self._send(405, "text/plain", head=True)
            else:
                self._send(206, "application/pdf")
        else:
            self._send(404, "text/plain", b"missing", head=head)

    def do_HEAD(self):
        self._route(True)

    def do_GET(self):
        self._route(False)


class LinkCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def status(self, path):
        return check_downloads.probe(self.base + path, timeout=5)[0]

    def test_good_files_are_ok(self):
        self.assertEqual(self.status("/ok.pdf"), "ok")
        self.assertEqual(self.status("/ok.zip"), "ok")

    def test_missing_file_is_broken(self):
        status, detail = check_downloads.probe(self.base + "/gone.pdf", timeout=5)
        self.assertEqual(status, "broken")
        self.assertIn("404", detail)

    def test_html_page_served_for_a_file_is_a_soft_404(self):
        status, detail = check_downloads.probe(self.base + "/soft404.pdf", timeout=5)
        self.assertEqual(status, "broken")
        self.assertIn("HTML", detail)

    def test_server_that_refuses_head_is_retried_with_get(self):
        self.assertEqual(self.status("/no-head.pdf"), "ok")

    def test_nobody_listening_is_unreachable_not_broken(self):
        self.assertEqual(check_downloads.probe("http://127.0.0.1:1/x.pdf", timeout=2)[0], "unreachable")

    def test_exit_codes(self):
        row = lambda s: ("d", "u", s, "")
        self.assertEqual(check_downloads.summarise([row("ok"), row("ok")]), 0)
        self.assertEqual(check_downloads.summarise([row("ok"), row("broken")]), 1)
        self.assertEqual(check_downloads.summarise([row("unreachable"), row("unreachable")]), 2)
        self.assertEqual(check_downloads.summarise([row("ok"), row("unreachable")]), 1)

    def test_check_runs_many_urls_and_keeps_order(self):
        pairs = [("a", self.base + "/ok.pdf"), ("b", self.base + "/gone.pdf"), ("c", self.base + "/ok.zip")]
        results = check_downloads.check(pairs, timeout=5, workers=3)
        self.assertEqual([r[0] for r in results], ["a", "b", "c"])
        self.assertEqual([r[2] for r in results], ["ok", "broken", "ok"])

    def test_offline_mode_validates_without_the_network(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(check_downloads.main(["--offline"]), 0)
            self.assertEqual(check_downloads.main(["--offline", "--subject", "maths"]), 0)
            self.assertEqual(check_downloads.main(["--offline", "--subject", "klingon"]), 1)
        self.assertIn("not probed", out.getvalue())
        self.assertIn("no files for subject 'klingon'", out.getvalue())

    def test_every_manifest_url_is_collected(self):
        data = downloads.load()
        urls = {u for _, u in check_downloads.collect(data)}
        self.assertEqual(urls, {u for _, u in downloads.file_urls(data) + downloads.list_urls(data)})
        maths = {d for d, _ in check_downloads.collect(data, "maths") if d.startswith("maths")}
        self.assertTrue(maths)


if __name__ == "__main__":
    unittest.main()
