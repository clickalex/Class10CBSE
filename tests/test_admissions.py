import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'site'))
import check_admissions as monitor
import admissions

FILLER = '<p>Official school information portal. Please consult the current prospectus and check all eligibility conditions before applying.</p>'
HTML = FILLER + '<a href="/xi.pdf">Class XI admission registration 2027 opens 15 February 2027; last date 20 March 2027</a>'
NOW = '2026-09-20T21:00:00+05:30'
URL = 'https://example.edu/'


class MonitorTests(unittest.TestCase):
    def check(self, body=HTML, old=None, session='2027-28'):
        return monitor.check_source(URL, old or {}, session, NOW, lambda _: (body, URL))

    def test_first_check_is_not_open_confirmation(self):
        result = self.check()
        self.assertEqual(result['check_status'], 'first_check')
        self.assertIn('Unknown', result['registration_status'])
        self.assertFalse(result['changed'])
        evidence = result['evidence'][0]
        self.assertEqual(evidence['date_mentions'], ['15 February 2027', '20 March 2027'])
        self.assertTrue(evidence['target_year_mentioned'])
        self.assertEqual(evidence['url'], URL + 'xi.pdf')

    def test_repeated_page_is_unchanged(self):
        first = self.check()
        self.assertEqual(self.check(old=first)['check_status'], 'unchanged')

    def test_deadline_change_detected(self):
        result = self.check(HTML.replace('20 March', '25 March'), self.check())
        self.assertTrue(result['changed'])

    def test_script_and_unrelated_news_do_not_change_fingerprint(self):
        extra = '<script>Class XI admission 2027</script><p>UG registration 2027 is open</p>'
        self.assertEqual(self.check(HTML + extra, self.check())['check_status'], 'unchanged')

    def test_class_xii_not_misidentified(self):
        result = self.check(FILLER + '<p>Class XII registration 2027 open</p>')
        self.assertEqual(result['evidence'], [])

    def test_old_year_not_current(self):
        result = self.check(HTML.replace('2027', '2026'))
        self.assertTrue(all(not e['target_year_mentioned'] for e in result['evidence']))
        self.assertIn('Unknown', result['registration_status'])

    def test_no_notice_still_unknown(self):
        result = self.check(FILLER)
        self.assertEqual(result['evidence'], [])
        self.assertIn('Unknown', result['registration_status'])

    def test_failed_request_preserves_success(self):
        old = self.check()
        def fail(_):
            raise TimeoutError('timed out')
        result = monitor.check_source(URL, old, '2027-28', NOW, fail)
        self.assertEqual(result['check_status'], 'error')
        self.assertEqual(result['fingerprint'], old['fingerprint'])
        self.assertEqual(result['last_success_at'], NOW)
        self.assertEqual(result['evidence'], old['evidence'])
        self.assertIn('Unknown', result['registration_status'])

    def test_new_session_resets_baseline(self):
        result = self.check(old=self.check(), session='2028-29')
        self.assertEqual(result['check_status'], 'first_check')

    def test_antibot_is_error_not_closed(self):
        result = self.check(FILLER + '<h1>Verify you are human</h1>')
        self.assertEqual(result['check_status'], 'error')

    def test_registration_link_alone_is_not_a_match(self):
        result = self.check(FILLER + '<a href="/login">Apply now</a>')
        self.assertEqual(result['evidence'], [])

    def test_report_errors_and_escaping(self):
        self.assertEqual(monitor.safe_md('<script>@user</script>'), '&lt;script&gt;&#64;user&lt;/script&gt;')
        config = {'target_session': '2027-28', 'institutions': [
            {'name': 'Test school', 'route': 'Class XI', 'expected_window': 'Unknown', 'sources': [URL]}]}
        report = monitor.report_markdown(config, {'checked_at': NOW, 'sources': {URL: self.check()}})
        self.assertIn('registration: **unknown**', report)
        self.assertIn('Unverified date mentions', report)


class SiteTests(unittest.TestCase):
    def test_directory_and_configuration(self):
        config = json.loads((ROOT / 'site/content/admissions.json').read_text())
        ids = [i['id'] for i in config['institutions']]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertTrue({'jmi', 'amu', 'bhu', 'nvs', 'kvs'} <= set(ids))
        body = admissions.admissions_body()
        for inst in config['institutions']:
            self.assertIn(f'id="{inst["id"]}"', body)
            for url in inst['sources']:
                self.assertTrue(url.startswith('https://'))
                self.assertIn(url, body)
        self.assertIn('Setup required', body)
        self.assertIn('2027-28', body)

    def test_navigation_from_nested_pages(self):
        spec = importlib.util.spec_from_file_location('site_build', ROOT / 'site/build.py')
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        self.assertIn('../../after-10th/index.html', build.sidebar('../..'))
        self.assertIn('aria-current="page"', build.sidebar('..', active='admissions'))
        self.assertNotIn('after-10th/chapters.html', build.sidebar('..', active='admissions'))


if __name__ == '__main__':
    unittest.main()
