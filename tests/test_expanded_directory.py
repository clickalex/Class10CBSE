import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'site'))
import admissions
import check_admissions as monitor

URL = 'https://example.edu/'
FILLER = '<p>Official educational opportunities portal. Check the correct current course and admission cycle before applying to any programme.</p>'


class ExpandedDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'site/content/admissions.json').read_text())

    def test_categories_and_links(self):
        institutions = self.config['institutions']
        self.assertEqual(len(institutions), 15)
        self.assertEqual({c: sum(i['category'] == c for i in institutions) for c in ('school', 'diploma', 'scholarship')},
                         {'school': 7, 'diploma': 3, 'scholarship': 5})
        body = admissions.admissions_body()
        for inst in institutions:
            self.assertIn(f'id="{inst["id"]}"', body)
            self.assertIn(inst['selection'], ('test', 'merit', 'verify'))
            self.assertTrue(inst['cycle'])
            if inst['category'] != 'school':
                self.assertTrue(inst['monitor_terms'])
        for category in ('school', 'diploma', 'scholarship'):
            self.assertIn(f'href="#{category}"', body)
            self.assertIn(f'id="{category}"', body)
        self.assertIn('../pw-nsat/index.html', body)
        self.assertIn('not government cash scholarships', body)

    def test_scopes_cover_every_url(self):
        scopes = monitor.source_scopes(self.config)
        self.assertEqual(len(scopes), 17)
        for inst in self.config['institutions']:
            for url in inst['sources']:
                self.assertIn(url, scopes)
                self.assertTrue(set(inst.get('monitor_terms', [])) <= set(scopes[url]))

    def test_scholarship_and_diploma_notices(self):
        for term, notice in [('anthe', 'ANTHE registration last date 20 October 2026'),
                             ('diploma', 'Diploma registration closes 10 June 2027')]:
            text = FILLER + f'<a href="/notice.pdf">{notice}</a>'
            result = monitor.analyse(text, URL, '2027-28', [term])
            self.assertEqual(len(result['evidence']), 1)
            self.assertTrue(result['evidence'][0]['date_mentions'])
            self.assertEqual(monitor.analyse(text, URL, '2027-28')['evidence'], [])

    def test_scope_change_resets_baseline(self):
        fetch = lambda _: (FILLER + '<p>ANTHE registration 2026</p>', URL)
        old = monitor.check_source(URL, {}, '2027-28', 'now', fetch, terms=['anthe'])
        new = monitor.check_source(URL, old, '2027-28', 'later', fetch, terms=['scholarship'])
        self.assertEqual(new['check_status'], 'first_check')
        self.assertFalse(new['changed'])

    def test_soft_404_is_an_error(self):
        with self.assertRaises(ValueError):
            monitor.analyse(FILLER + 'The requested URL was not found', URL, '2027-28')

    def test_shared_url_preserves_school_and_custom_scopes(self):
        config = {'institutions': [{'sources': [URL]}, {'sources': [URL], 'monitor_terms': ['diploma']}]}
        scopes = monitor.source_scopes(config)
        self.assertIn('diploma', scopes[URL])
        self.assertIn('class xi', scopes[URL])

    def test_literal_scope_not_regex(self):
        data = monitor.analyse(FILLER + '<p>ANTHE registration</p>', URL, '2027-28', ['.*'])
        self.assertEqual(data['evidence'], [])

    def test_cycle_notes_in_daily_report(self):
        sources = {url: {'check_status': 'error', 'error': 'Timeout', 'evidence': [], 'last_success_at': None}
                   for url in monitor.source_scopes(self.config)}
        body = monitor.report_markdown(self.config, {'checked_at': 'now', 'sources': sources})
        for inst in self.config['institutions']:
            self.assertIn(inst['name'], body)
            self.assertIn(inst['cycle'], body)
        self.assertIn('registration: **unknown**', body)


if __name__ == '__main__':
    unittest.main()
