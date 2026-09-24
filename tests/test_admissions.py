import html
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
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
        self.assertNotIn('Setup required', body, "developer workflow setup instructions should not be shown to students")
        self.assertNotIn('github.com', body, "no GitHub links in student admissions body")
        self.assertIn('Daily admission &amp; scholarship watch', body)
        self.assertIn('2027-28', body)
        self.assertIn('href="report.html"', body, "should link to the HTML report instead of GitHub Issues")
        self.assertNotIn('issues?q=', body, "should not point users to GitHub Issues search")

    def test_report_body_renders_all_institutions_and_sources(self):
        config = json.loads((ROOT / 'site/content/admissions.json').read_text())
        report_html = admissions.report_body()
        for inst in config['institutions']:
            self.assertIn(f'id="report-{inst["id"]}"', report_html)
            self.assertIn(html.escape(inst['name']), report_html)
            for url in inst['sources']:
                self.assertIn(url, report_html)
        self.assertIn('href="index.html"', report_html, "report must link back to directory")
        self.assertNotIn('github.com', report_html, "no GitHub links in student watch report")
        self.assertIn('Daily admission &amp; scholarship watch report', report_html)
        self.assertIn('2027-28', report_html)

    def test_report_body_renders_published_results(self):
        # The same guarantees hold when the workflows publish real results.
        config = json.loads((ROOT / 'site/content/admissions.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            report_html = admissions.report_body(state_path=write_state(tmp, sample_state(config)))
        for inst in config['institutions']:
            self.assertIn(f'id="report-{inst["id"]}"', report_html)
            for url in inst['sources']:
                self.assertIn(url, report_html)
        self.assertNotIn('github.com', report_html, "no GitHub links in student watch report")

    def test_navigation_from_nested_pages(self):
        spec = importlib.util.spec_from_file_location('site_build', ROOT / 'site/build.py')
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        self.assertIn('../../after-10th/index.html', build.sidebar('../..'))
        self.assertIn('aria-current="page"', build.sidebar('..', active='admissions'))
        self.assertIn('after-10th/report.html', build.sidebar('..', active='admissions'))
        self.assertIn('aria-current="page"', build.sidebar('..', active='admissions', subactive='report'))
        self.assertNotIn('after-10th/chapters.html', build.sidebar('..', active='admissions'))


CHECKED = '2026-09-24T00:37:54+05:30'
EARLIER = '2026-09-23T00:30:12+05:30'


def sample_state(config, checked=CHECKED):
    """A state.json shaped like scripts/check_admissions.py output."""
    sources = {}
    for inst in config['institutions']:
        for url in inst['sources']:
            sources[url] = {
                'url': url, 'session': config['target_session'], 'checked_at': checked,
                'last_success_at': checked, 'check_status': 'unchanged', 'changed': False,
                'evidence': [], 'monitor_version': monitor.MONITOR_VERSION,
            }
    return {'checked_at': checked, 'session': config['target_session'], 'sources': sources}


def write_state(folder, state):
    path = Path(folder) / 'state.json'
    path.write_text(json.dumps(state), encoding='utf-8')
    return path


class WatchReportTests(unittest.TestCase):
    """The live report says when the check ran and when each source was fetched."""

    def setUp(self):
        self.config = json.loads((ROOT / 'site/content/admissions.json').read_text())
        self.url = self.config['institutions'][0]['sources'][0]
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def render(self, state):
        return admissions.report_body(state_path=write_state(self.tmp.name, state))

    def test_times_are_shown_in_india_time(self):
        self.assertEqual(admissions.format_time(CHECKED), '24 Sep 2026, 12:37 AM IST')
        self.assertEqual(admissions.format_time('2026-09-23T15:30:00+00:00'), '23 Sep 2026, 9:00 PM IST')
        self.assertEqual(admissions.format_time('2026-09-24T12:05:00+05:30'), '24 Sep 2026, 12:05 PM IST')
        self.assertEqual(admissions.format_time('2026-01-01T00:00:00+05:30'), '1 Jan 2026, 12:00 AM IST')

    def test_non_timestamps_are_not_turned_into_times(self):
        for value in (None, 'Never', '', '2026-09-24T00:37:54'):  # naive: zone unknown
            self.assertIsNone(admissions.format_time(value), value)
        self.assertEqual(admissions.time_tag('<soon>'), '&lt;soon&gt;')

    def test_report_shows_when_the_check_ran(self):
        report = self.render(sample_state(self.config))
        stamp = f'<time datetime="{CHECKED}">24 Sep 2026, 12:37 AM IST</time>'
        self.assertIn(f'Last check ran: <strong>{stamp}</strong>', report)
        self.assertIn(f'data-checked-at="{CHECKED}"', report, "app.js computes the age from this")
        self.assertIn('data-report-stale hidden', report, "stale warning is hidden until app.js shows it")
        self.assertIn('<span class="report-stat-val">12:37 AM IST</span>', report)
        self.assertIn('<span class="report-stat-sub">24 Sep 2026</span>', report)
        n = sum(len(inst['sources']) for inst in self.config['institutions'])
        self.assertIn(f'{n} sources monitored &middot; {n} unchanged &middot; 0 changed &middot; 0 fetch errors', report)
        self.assertEqual(report.count(f'<strong>Last successful fetch:</strong> {stamp}'), n)
        self.assertNotIn('not published yet', report.lower())

    def test_failed_fetch_keeps_the_last_successful_fetch_time(self):
        state = sample_state(self.config)
        state['sources'][self.url].update({
            'check_status': 'error', 'last_success_at': EARLIER,
            'error': 'URLError: <urlopen error timed out>',
            'evidence': [{'text': 'Admission notice 2027-28', 'url': self.url, 'signals': ['admission'],
                          'date_mentions': ['12 March 2027'], 'target_year_mentioned': True}],
        })
        report = self.render(state)
        self.assertIn('<span class="report-badge-err">Fetch Error</span>', report)
        self.assertIn(f'<strong>Last successful fetch:</strong> <time datetime="{EARLIER}">'
                      '23 Sep 2026, 12:30 AM IST</time>', report)
        self.assertIn(f'<strong>Fetch failed at <time datetime="{CHECKED}">24 Sep 2026, 12:37 AM IST</time>:'
                      '</strong> URLError: &lt;urlopen error timed out&gt;', report)
        self.assertIn('The notices below are from the last successful fetch.', report)
        self.assertIn('Admission notice 2027-28', report)
        self.assertIn('1 fetch errors', report)

    def test_source_that_never_loaded(self):
        state = sample_state(self.config)
        state['sources'][self.url].update(
            {'check_status': 'error', 'last_success_at': None, 'error': 'ValueError: blocked'})
        report = self.render(state)
        self.assertIn('<strong>Last successful fetch:</strong> None yet', report)
        self.assertNotIn('The notices below are from the last successful fetch.', report)

    def test_status_badges(self):
        state = sample_state(self.config)
        urls = [u for inst in self.config['institutions'] for u in inst['sources']]
        state['sources'][urls[0]].update({'check_status': 'changed', 'changed': True})
        state['sources'][urls[1]].update({'check_status': 'first_check'})
        del state['sources'][urls[2]]  # e.g. a portal added since the last check
        report = self.render(state)
        self.assertIn('Evidence Changed', report)
        self.assertIn('First Check Recorded', report)
        self.assertIn('Awaiting daily check', report)
        self.assertIn('1 changed', report)
        self.assertIn('1 first check', report)

    def test_without_results_the_report_says_so(self):
        report = admissions.report_body()
        self.assertIn('Last check ran: <strong>not published yet</strong>', report)
        self.assertIn('<strong>Last successful fetch:</strong> Not published yet', report)
        self.assertNotIn('<time', report)
        self.assertNotIn('data-checked-at', report)
        self.assertNotIn('Pending scheduled run', report)

    def test_results_for_another_session_are_ignored(self):
        state = sample_state(self.config)
        state['session'] = '2020-21'
        self.assertIn('not published yet', self.render(state))

    def test_unreadable_results_are_ignored(self):
        path = Path(self.tmp.name) / 'broken.json'
        path.write_text('{not json', encoding='utf-8')
        self.assertIn('not published yet', admissions.report_body(state_path=path))
        self.assertIn('not published yet', admissions.report_body(state_path=Path(self.tmp.name) / 'missing.json'))
        self.assertIn('not published yet', self.render({'checked_at': CHECKED, 'sources': []}))
        session = self.config['target_session']
        self.assertIn('not published yet', self.render({'checked_at': 5, 'session': session, 'sources': {}}))
        state = sample_state(self.config)
        state['sources'][self.url]['evidence'] = {'not': 'a list'}
        self.assertIn('Last check ran: <strong><time', self.render(state))

    def test_observed_text_is_escaped(self):
        state = sample_state(self.config)
        state['sources'][self.url].update({
            'check_status': 'error', 'error': '<script>alert(1)</script>',
            'evidence': [{'text': '<img src=x onerror=alert(1)>', 'url': self.url,
                          'date_mentions': ['<b>'], 'signals': ['<i>']}],
        })
        report = self.render(state)
        for raw in ('<script>alert(1)', '<img src=x', '<b>', '<i>'):
            self.assertNotIn(raw, report)


if __name__ == '__main__':
    unittest.main()
