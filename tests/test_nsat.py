import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'site'))
import nsat

spec = importlib.util.spec_from_file_location('study_build', ROOT / 'site/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class NSATTests(unittest.TestCase):
    def test_official_source_and_snapshot(self):
        data = json.loads((ROOT / 'site/content/pw-nsat.json').read_text())
        self.assertEqual(data['official_url'], 'https://www.pw.live/scholarship/vidyapeeth/nsat')
        body = nsat.nsat_body()
        self.assertIn(data['official_url'], body)
        self.assertIn(data['checked_on'], body)
        self.assertIn('not a live registration tracker', body)
        self.assertIn('included in the daily 9 PM IST', body)
        self.assertIn('Class 10', body)

    def test_navigation_at_each_depth(self):
        for root, expected in (('.', 'pw-nsat/index.html'), ('..', '../pw-nsat/index.html'),
                               ('../..', '../../pw-nsat/index.html')):
            nav = build.sidebar(root, active='pw-nsat')
            self.assertIn(f'href="{expected}" aria-current="page"', nav)
            self.assertNotIn('pw-nsat/chapters.html', nav)

    def test_home_card(self):
        _, body = build.portal_body([], {})
        self.assertIn('href="pw-nsat/index.html"', body)
        self.assertIn('href="after-10th/index.html"', body)

    def test_snapshot_text_is_escaped(self):
        data = json.loads((ROOT / 'site/content/pw-nsat.json').read_text())
        data['details'].append(['<script>', '<img src=x onerror=alert(1)>'])
        with patch.object(nsat.json, 'loads', return_value=data):
            body = nsat.nsat_body()
        self.assertNotIn('<script>', body)
        self.assertIn('&lt;script&gt;', body)

    def test_generated_page_and_links(self):
        with tempfile.TemporaryDirectory() as out:
            with patch.object(build, 'DIST', Path(out)):
                build.build()
                self.assertEqual(build.validate()[0], 0)
            page = (Path(out) / 'pw-nsat/index.html').read_text()
            self.assertIn('Open official PW NSAT website / registration', page)
            self.assertIn('href="../assets/css/style.css"', page)
            self.assertIn('href="../pw-nsat/index.html" aria-current="page"', page)


if __name__ == '__main__':
    unittest.main()
