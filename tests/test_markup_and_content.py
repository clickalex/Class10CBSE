"""Markup, content and documentation invariants found by the 2 Oct 2026 audit.

Each class pins one defect so it cannot come back:

  * inline markup nests (bold-italic used to render <strong><em>x</strong></em>);
  * published pages are valid where it matters - no paragraph inside a
    paragraph, one <title> per page escaped exactly once, typed buttons;
  * the written Q&A carry no doubled sentence punctuation pasted in from the
    templates ("decimals..", "(…).)." );
  * the numbers the READMEs quote are the numbers the content has.

The HTML checks read the committed docs/ folder, like test_site_structure.py.

Run with:  python3 -m unittest tests.test_markup_and_content -v
"""
import collections
import importlib.util
import json
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DOCS = ROOT / "docs"
sys.path.insert(0, str(SITE))

_spec = importlib.util.spec_from_file_location("build", SITE / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

VOID = set("area base br col embed hr img input link meta param source track wbr".split())
BLOCKS = set("address article aside blockquote details div dl fieldset figure footer form "
             "h1 h2 h3 h4 h5 h6 header hr main nav ol p pre section table ul".split())


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_strings(item)
    elif isinstance(obj, dict):
        for item in obj.values():
            yield from _walk_strings(item)


def _content_strings(pattern="*.json", folder="content"):
    for path in sorted((SITE / folder).rglob(pattern)):
        for s in _walk_strings(json.loads(path.read_text(encoding="utf-8"))):
            yield path, s


def _pages():
    for path in sorted(DOCS.rglob("*.html")):
        yield path.relative_to(DOCS).as_posix(), path.read_text(encoding="utf-8")


class _Balance(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.ok = [], True

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.ok = False


class InlineMarkupTests(unittest.TestCase):
    def test_bold_and_italic_nest_instead_of_crossing(self):
        cases = {
            "***x***": "<strong><em>x</em></strong>",
            "**the book *Title***": "<strong>the book <em>Title</em></strong>",
            "*it **b** it*": "<em>it <strong>b</strong> it</em>",
            "**a *b* c**": "<strong>a <em>b</em> c</strong>",
            "**a** and **b**": "<strong>a</strong> and <strong>b</strong>",
            "plain *i* and `c`": "plain <em>i</em> and <code>c</code>",
            "5 < 6 & 7 > 2": "5 &lt; 6 &amp; 7 &gt; 2",
        }
        for src, want in cases.items():
            self.assertEqual(build.inline(src), want, src)

    def test_every_content_string_renders_balanced_html(self):
        bad = []
        for path, s in _content_strings():
            parser = _Balance()
            parser.feed(build.inline(s))
            if not parser.ok or parser.stack:
                bad.append(f"{path.name}: {s[:70]!r}")
        self.assertEqual(bad, [])


class _BlockInParagraph(HTMLParser):
    def __init__(self):
        super().__init__()
        self.open, self.found = [], []

    def handle_starttag(self, tag, attrs):
        if tag in BLOCKS and "p" in self.open:
            self.found.append(tag)
        if tag not in VOID:
            self.open.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID or tag not in self.open:
            return
        while self.open and self.open[-1] != tag:
            self.open.pop()
        self.open.pop()


class PublishedMarkupTests(unittest.TestCase):
    def test_no_block_element_inside_a_paragraph(self):
        """A <p> inside a <p> is closed by the browser and leaves empty paragraphs behind."""
        bad = {}
        for rel, text in _pages():
            parser = _BlockInParagraph()
            parser.feed(text)
            if parser.found:
                bad[rel] = sorted(set(parser.found))
        self.assertEqual(bad, {})

    def test_every_page_has_its_own_title_escaped_once(self):
        titles = collections.defaultdict(list)
        for rel, text in _pages():
            title = re.search(r"<title>(.*?)</title>", text, re.S).group(1)
            self.assertNotIn("&amp;amp;", text, f"{rel}: double-escaped entity")
            titles[title].append(rel)
        shared = {t: pages for t, pages in titles.items() if len(pages) > 1}
        self.assertEqual(shared, {}, "pages share a <title>")

    def test_practical_pages_name_their_subject(self):
        for path in sorted(DOCS.glob("*/practical.html")):
            title = re.search(r"<title>(.*?)</title>", path.read_text(encoding="utf-8")).group(1)
            self.assertIn("Practical &amp; internal assessment", title)
            self.assertNotIn("&amp;amp;", title)
            self.assertNotEqual(title.split(" \u2014 ")[0], "Practical &amp; internal assessment", path.parent.name)

    def test_buttons_state_their_type(self):
        bad = []
        for rel, text in _pages():
            for tag in re.findall(r"<button\b[^>]*>", text):
                if " type=" not in tag:
                    bad.append(f"{rel}: {tag}")
        self.assertEqual(bad[:5], [])
        for name in ("header.html", "navigation.html", "footer.html"):
            partial = (SITE / "partials" / name).read_text(encoding="utf-8")
            for tag in re.findall(r"<button\b[^>]*>", partial):
                self.assertIn('type="button"', tag, name)


class FormulaListTests(unittest.TestCase):
    """A table object in a chapter's formulas used to be printed as a Python dict."""

    def test_strings_become_items_and_tables_become_tables(self):
        table = {"table": {"head": ["Port", "Use"], "rows": [["80", "HTTP"]]}}
        out = build.formula_list(["**Memorise** this", table, "and *this*"])
        self.assertEqual(out.count('<ul class="formula">'), 2, "the list is closed around the table")
        self.assertIn("<li><strong>Memorise</strong> this</li>", out)
        self.assertIn("<table><thead><tr><th>Port</th><th>Use</th></tr></thead>", out)
        self.assertIn("<td>HTTP</td>", out)
        self.assertLess(out.index("<table"), out.index("and <em>this</em>"))
        self.assertNotIn("{'", out)
        self.assertNotIn("&#x27;table", out)

    def test_plain_formula_lists_are_unchanged(self):
        self.assertEqual(build.formula_list(["a = b", "c = d"]),
                         '<ul class="formula"><li>a = b</li><li>c = d</li></ul>')

    def test_published_pages_print_no_python_dict(self):
        bad = [rel for rel, text in _pages()
               if re.search(r"\{(&#x27;|')(table|head|rows|h)(&#x27;|')\s*:", text)]
        self.assertEqual(bad, [])

    def test_every_table_in_a_formula_list_is_published_as_a_table(self):
        subjects = json.loads((SITE / "content" / "subjects.json").read_text(encoding="utf-8"))
        checked = 0
        for subj in subjects:
            for ch in build.load_chapters(subj["slug"]):
                tables = [f for f in ch.get("formulas") or [] if isinstance(f, dict)]
                if not tables:
                    continue
                page = (DOCS / subj["slug"] / "chapters" / f"{ch['id']}.html").read_text(encoding="utf-8")
                formulas = page.split('id="formulas"')[1].split('id="steps"')[0]
                self.assertEqual(formulas.count("<table"), len(tables), ch["id"])
                checked += 1
        self.assertGreaterEqual(checked, 6)


class ContentPunctuationTests(unittest.TestCase):
    # '.).' is a sentence-final full stop pasted inside a bracket; a '..' that
    # ends a sentence is the same thing. ('..' before '/' or a backtick is a
    # real relative path in the IT chapters and is left alone.)
    BAD = re.compile(r"\.\)\.|(?<=[^\s.`/])\.\.(?=\s|$)|[?;!,]\.(?=\s|$)")

    def test_no_doubled_sentence_punctuation_in_chapter_content(self):
        bad = []
        for path, s in _content_strings(folder="content/chapters"):
            m = self.BAD.search(s)
            if m:
                bad.append(f"{path.name}: ...{s[max(0, m.start() - 40):m.end() + 10]!r}")
        self.assertEqual(bad[:5], [], f"{len(bad)} strings")

    def test_real_relative_paths_are_untouched(self):
        joined = " ".join(p.read_text(encoding="utf-8")
                          for p in (SITE / "content" / "chapters").rglob("*.json"))
        self.assertIn("`..`", joined, "the HTML chapters teach '..' as 'parent folder'")
        self.assertIn("../index.html", joined)


class DocumentedNumbersTests(unittest.TestCase):
    """The READMEs quote counts; they must be the counts the content has."""

    @classmethod
    def setUpClass(cls):
        subjects = json.loads((SITE / "content" / "subjects.json").read_text(encoding="utf-8"))
        cls.chapters = [c for s in subjects for c in build.load_chapters(s["slug"])]
        cls.n = len(cls.chapters)
        cls.qa = sum(len(c["qa"]) for c in cls.chapters)
        cls.mcq = sum(len(c["mcq"]) for c in cls.chapters)
        cls.formulas = sum(1 for c in cls.chapters if c.get("formulas"))
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        cls.site_readme = (SITE / "README.md").read_text(encoding="utf-8")

    @staticmethod
    def _int(text):
        return int(text.replace(",", ""))

    def test_root_readme_quotes_the_real_totals(self):
        m = re.search(r"(\d+) chapter\s+pages, \*\*([\d,]+) written Q&A and ([\d,]+) MCQs\*\*", self.readme)
        self.assertIsNotNone(m, "headline sentence not found")
        self.assertEqual((self._int(m.group(1)), self._int(m.group(2)), self._int(m.group(3))),
                         (self.n, self.qa, self.mcq))

    def test_site_readme_coverage_table_total(self):
        m = re.search(r"\| \*\*Total\*\* \| \*\*(\d+)\*\* \| \*\*([\d,]+)\*\* \| \*\*([\d,]+)\*\* \|", self.site_readme)
        self.assertIsNotNone(m)
        self.assertEqual((self._int(m.group(1)), self._int(m.group(2)), self._int(m.group(3))),
                         (self.n, self.qa, self.mcq))

    def test_site_readme_section_coverage_uses_the_real_chapter_count(self):
        self.assertIn(f"An audit of all {self.n} chapters", self.site_readme)
        rows = re.findall(r"\| [^|\n]+ \| (\d+) / (\d+)\b", self.site_readme)
        self.assertGreaterEqual(len(rows), 3)
        for have, of in rows:
            self.assertEqual(int(of), self.n, "every coverage row is out of the real chapter total")
        formulas = re.search(r"Formulas to memorise \| (\d+) / \d+", self.site_readme)
        self.assertEqual(int(formulas.group(1)), self.formulas)

    def test_nobody_still_claims_the_old_chapter_count(self):
        for name, text in (("README.md", self.readme), ("site/README.md", self.site_readme)):
            self.assertNotRegex(text, r"\b174\b", f"{name} still says 174")


if __name__ == "__main__":
    unittest.main()
