"""Structure and publishing audit for the study hub.

The repository keeps its source in site/ and its published output in docs/
(that is the folder GitHub Pages serves), so this module pins down the
guarantees that separation depends on:

  * docs/ is pure build output - a fresh build equals the committed folder
    byte for byte, which is what proves nobody hand-edited the live site;
  * every page ships the shared shell from site/partials/: favicon, canonical
    URL, Open Graph tags, the stylesheet and the theme script;
  * the document outline never skips a heading level (a11y + SEO);
  * sitemap.xml lists every published page and robots.txt points at it;
  * the committed raster icons still match scripts/make_icons.py output;
  * the reusable components live in partials/buttons.html and nothing internal
    (template comments, component markers) leaks into published HTML;
  * temp-workflow/ holds workflow files that are still installable.

Run with:  python3 -m unittest tests.test_site_structure -v
"""
import importlib.util
import re
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DOCS = ROOT / "docs"
PARTIALS = SITE / "partials"

sys.path.insert(0, str(SITE))
import layout  # noqa: E402

SPEC = importlib.util.spec_from_file_location("build", SITE / "build.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)

ICON_SPEC = importlib.util.spec_from_file_location(
    "make_icons", ROOT / "scripts" / "make_icons.py")
make_icons = importlib.util.module_from_spec(ICON_SPEC)
ICON_SPEC.loader.exec_module(make_icons)

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def _pages():
    for path in sorted(DOCS.rglob("*.html")):
        yield path.relative_to(DOCS).as_posix(), path.read_text(encoding="utf-8")


class SourceLayoutTests(unittest.TestCase):
    """The source tree is organised by file type, like a normal web project."""

    def test_theme_is_split_into_css_and_js(self):
        self.assertTrue((SITE / "theme" / "css" / "style.css").is_file())
        self.assertTrue((SITE / "theme" / "js" / "app.js").is_file())
        self.assertTrue((SITE / "theme" / "js" / "mock.js").is_file())
        loose = [p.name for p in (SITE / "theme").iterdir() if p.is_file()]
        self.assertEqual(loose, [], "theme/ should only hold css/ and js/")

    def test_brand_images_live_in_the_repo_assets_folder(self):
        images = ROOT / "assets" / "images"
        for name in ("favicon.svg", "logo.svg", "icon-180.png",
                     "icon-192.png", "icon-512.png"):
            self.assertTrue((images / name).is_file(), name)

    def test_partials_define_the_shared_components(self):
        for name in ("page.html", "head.html", "header.html",
                     "navigation.html", "footer.html", "buttons.html",
                     "notfound.html"):
            self.assertTrue((PARTIALS / name).is_file(), name)
        names = set(layout.components())
        self.assertLessEqual(
            {"button", "button-row", "chip", "chip-row", "chapter-nav", "callout"},
            names)

    def test_component_markup_matches_the_stylesheet(self):
        css = (SITE / "theme" / "css" / "style.css").read_text(encoding="utf-8")
        self.assertIn('class="btn primary"', layout.button("x.html", "Go", primary=True))
        self.assertIn('class="chip"', layout.chip("#a", "A"))
        self.assertIn('class="callout"', layout.callout("note"))
        self.assertIn('class="chapnav"', layout.component("chapter-nav", ITEMS=""))
        for cls in (".btn", ".btn.primary", ".chip", ".chips", ".chapnav", ".callout"):
            self.assertIn(cls, css, f"component class {cls} missing from style.css")


class PublishedShellTests(unittest.TestCase):
    """Every published page carries the shared head/header/footer shell."""

    def test_every_page_has_favicon_canonical_and_og(self):
        missing = []
        for rel, text in _pages():
            if rel == "404.html":
                continue
            for needle in ('rel="icon" type="image/svg+xml"',
                           'rel="apple-touch-icon"',
                           'rel="canonical" href="%s/' % layout.SITE_URL,
                           'property="og:title"',
                           'assets/css/style.css',
                           'assets/js/app.js'):
                if needle not in text:
                    missing.append(f"{rel}: {needle}")
        self.assertEqual(missing, [])

    def test_document_outline_never_skips_a_level(self):
        bad = []
        for rel, text in _pages():
            levels = [int(m.group(1)) for m in re.finditer(r"<h([1-6])", text)]
            if not levels or levels[0] != 1:
                bad.append(f"{rel}: first heading {levels[:1]}")
                continue
            if any(b > a + 1 for a, b in zip(levels, levels[1:])):
                bad.append(rel)
        self.assertEqual(bad, [])

    def test_devanagari_subjects_declare_their_language(self):
        cases = {"hindi": "hi", "sanskrit": "sa", "maths": "en"}
        for slug, lang in cases.items():
            folder = DOCS / slug / "chapters"
            page = next(folder.glob("*.html"))
            head = page.read_text(encoding="utf-8").split("</head>")[0]
            self.assertIn(f'<html lang="{lang}">', head, slug)

    def test_no_template_internals_leak_into_published_html(self):
        for rel, text in _pages():
            self.assertNotIn("partials/", text, rel)
            self.assertNotIn("@component", text, rel)

    def test_404_page_is_self_describing(self):
        text = (DOCS / "404.html").read_text(encoding="utf-8")
        self.assertIn('name="description"', text)
        self.assertIn('name="robots" content="noindex"', text)
        self.assertIn('href="%s/index.html"' % layout.BASE, text)
        self.assertIn("assets/img/favicon.svg", text)


class DiscoveryFilesTests(unittest.TestCase):
    def test_sitemap_lists_every_page_but_the_404(self):
        tree = ET.parse(DOCS / "sitemap.xml")
        locs = {u.find(f"{SITEMAP_NS}loc").text for u in tree.getroot()}
        published = {f"{layout.SITE_URL}/{rel}" for rel, _ in _pages()
                     if rel != "404.html"}
        self.assertEqual(locs, published)

    def test_robots_points_at_the_sitemap(self):
        text = (DOCS / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("User-agent: *", text)
        self.assertIn(f"Sitemap: {layout.SITE_URL}/sitemap.xml", text)


class GeneratedOutputTests(unittest.TestCase):
    """docs/ must equal a fresh build: source edits require a rebuild."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="c10-drift-"))
        saved = build.DIST
        build.DIST = cls.tmp
        try:
            cls.written, _ = build.build()
        finally:
            build.DIST = saved

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_committed_docs_match_a_fresh_build(self):
        fresh = {p.relative_to(self.tmp).as_posix(): p.read_bytes()
                 for p in self.tmp.rglob("*") if p.is_file()}
        committed = {p.relative_to(DOCS).as_posix(): p.read_bytes()
                     for p in DOCS.rglob("*") if p.is_file()}
        self.assertEqual(set(fresh), set(committed),
                         "docs/ has files a fresh build does not produce, or vice versa")
        differ = [name for name in fresh if fresh[name] != committed[name]]
        self.assertEqual(differ, [], "docs/ is stale: rebuild with python3 site/build.py")

    def test_published_asset_bundle_is_typed(self):
        for rel in ("assets/css/style.css", "assets/js/app.js",
                    "assets/js/mock.js", "assets/img/favicon.svg",
                    "assets/img/icon-192.png"):
            self.assertTrue((self.tmp / rel).is_file(), rel)


class IconTests(unittest.TestCase):
    def test_committed_icons_match_the_generator(self):
        for name, data in make_icons.render_all().items():
            committed = (ROOT / "assets" / "images" / name).read_bytes()
            self.assertEqual(committed, data,
                             f"{name} is stale: run scripts/make_icons.py")


class TempWorkflowTests(unittest.TestCase):
    """temp-workflow/ holds workflows the owner copies in when they want them."""

    def test_staged_workflows_are_installable(self):
        folder = ROOT / "temp-workflow"
        self.assertTrue((folder / "README.md").is_file())
        for name in ("checks.yml", "deploy-pages.yml"):
            text = (folder / name).read_text(encoding="utf-8")
            for key in ("name:", "on:", "jobs:", "runs-on:"):
                self.assertIn(key, text, f"{name} missing {key}")
        checks = (folder / "checks.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/check_all.sh", checks)
        deploy = (folder / "deploy-pages.yml").read_text(encoding="utf-8")
        self.assertIn("docs/", deploy)


if __name__ == "__main__":
    unittest.main()
