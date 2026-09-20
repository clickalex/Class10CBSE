"""Regression tests for the pre-merge reliability audit."""
from datetime import datetime
from email.message import Message
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_admissions as monitor

URL = 'https://example.edu/'
FILLER = '<p>Official portal: please check the latest course, eligibility and admission session before completing your application.</p>'


class AuditTests(unittest.TestCase):
    def analyse(self, html, terms=()):
        return monitor.analyse(FILLER + html, URL, '2027-28', terms)

    def test_changes_beyond_display_limit_are_detected(self):
        html = ''.join(f'<a href="/{i:02}.pdf">Class XI admission notice {i:02}</a>' for i in range(35))
        before = self.analyse(html)
        after = self.analyse(html.replace('notice 34', 'notice 34 extended'))
        self.assertEqual(len(before['evidence']), 30)
        self.assertEqual(before['evidence_count'], 35)
        self.assertNotEqual(before['fingerprint'], after['fingerprint'])

    def test_dates_and_changes_beyond_snippet_limit(self):
        html = '<p>Class XI admission ' + 'instructions ' * 80 + 'deadline 20 March 2027</p>'
        before = self.analyse(html)
        after = self.analyse(html.replace('20 March', '25 March'))
        self.assertTrue(before['evidence'][0]['text_truncated'])
        self.assertLessEqual(len(before['evidence'][0]['text']), 700)
        self.assertEqual(before['evidence'][0]['date_mentions'], ['20 March 2027'])
        self.assertNotEqual(before['fingerprint'], after['fingerprint'])

    def test_ordinal_dates_and_abbreviations(self):
        result = self.analyse('<p>Class XI admission closes 21st Sept. 2026, test 2nd October 2026.</p>')
        self.assertEqual(result['evidence'][0]['date_mentions'], ['21st Sept. 2026', '2nd October 2026'])

    def test_custom_class_xi_terms_do_not_match_class_xii(self):
        self.assertEqual(self.analyse('<p>Class XII admission now open.</p>', ['class xi'])['evidence'], [])
        self.assertEqual(self.analyse('<p>Class 110 admission now open.</p>', ['class 11'])['evidence'], [])

    def test_corrupt_cache_becomes_new_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'state.json'
            self.assertEqual(monitor.load_state(path), {})
            for invalid in ('{', '[]', '{"sources": []}', '{"sources": {"url": null}}',
                            '{"sources": {"url": {"evidence": [null]}}}'):
                path.write_text(invalid)
                with patch('sys.stderr', new_callable=StringIO) as stderr:
                    self.assertEqual(monitor.load_state(path), {})
                self.assertIn('Warning', stderr.getvalue())
            path.write_text(json.dumps({'sources': {}}))
            self.assertEqual(monitor.load_state(path), {'sources': {}})

    def test_old_monitor_version_resets_baseline(self):
        fetch = lambda _: (FILLER + '<p>Class XI admission notice 2027</p>', URL)
        old = monitor.check_source(URL, {}, '2027-28', 'now', fetch)
        old['monitor_version'] = 1
        new = monitor.check_source(URL, old, '2027-28', 'later', fetch)
        self.assertEqual(new['check_status'], 'first_check')
        self.assertFalse(new['changed'])

    def test_fetch_retry_and_timeout(self):
        with patch.object(monitor, 'urlopen', side_effect=URLError('timeout')) as call, patch.object(monitor.time, 'sleep'):
            with self.assertRaises(URLError):
                monitor.fetch(URL)
            self.assertEqual(call.call_count, 2)
            self.assertEqual(call.call_args.kwargs['timeout'], 20)

    def response(self, content_type='text/html; charset=utf-8', body=b'<p>ok</p>'):
        response = MagicMock()
        response.__enter__.return_value = response
        headers = Message()
        headers['Content-Type'] = content_type
        response.headers = headers
        response.read.return_value = body
        response.geturl.return_value = URL
        return response

    def test_fetch_success(self):
        response = self.response(body='Class XI — notice'.encode('utf-8'))
        with patch.object(monitor, 'urlopen', return_value=response):
            text, url = monitor.fetch(URL)
        self.assertEqual(text, 'Class XI — notice')
        self.assertEqual(url, URL)
        response.read.assert_called_once_with(monitor.MAX_BYTES + 1)

    def test_fetch_rejects_pdf_and_oversize_responses(self):
        for response in (self.response('application/pdf'),
                         self.response(body=b'x' * (monitor.MAX_BYTES + 1))):
            with patch.object(monitor, 'urlopen', return_value=response), patch.object(monitor.time, 'sleep'):
                with self.assertRaises(ValueError):
                    monitor.fetch(URL)

    def test_utc_cron_is_nine_pm_india(self):
        moment = datetime(2026, 9, 20, 15, 30, tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Asia/Kolkata'))
        self.assertEqual((moment.hour, moment.minute), (21, 0))
        workflow = ROOT / '.github/workflows/admission-watch.yml'
        self.assertTrue(workflow.is_file(), f"workflow not found at {workflow}")
        self.assertIn("cron: '30 15 * * *'", workflow.read_text())


if __name__ == '__main__':
    unittest.main()
