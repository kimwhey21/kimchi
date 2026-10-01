"""카페24 봇 검사 화면 판정(src/site_block.py, 2026-10-01) — 200으로 오는 검사 화면을 '열렸다'로 읽지 않는다."""
import unittest
from unittest import mock

from scripts import site_crawl as sc
from scripts import site_health as sh
from src.site_block import is_bot_challenge

CUPID = ('<html><body><script type="text/javascript" src="/cupid.js" ></script><script>function toNumbers(d){var e=[];}'
         'var a=toNumbers("3d87");document.cookie="CUPID="+toHex(slowAES.decrypt(c,2,a,b));location.href="/?ckattempt=1";</script></body></html>')


class Challenge(unittest.TestCase):
    def test_detects_cupid_page(self):
        self.assertTrue(is_bot_challenge(CUPID))
        self.assertTrue(is_bot_challenge(CUPID.encode()))

    def test_normal_pages_pass(self):
        for body in ("", None, '[{"slug":"x"}]', "<html><title>Fermata</title><body>KOSPI</body></html>",
                     "<p>Array Testers and cupid arrows</p>"):
            self.assertFalse(is_bot_challenge(body), body)

    def test_site_health_says_it_in_one_line(self):
        class S:
            def get(self, url, **kw):
                return mock.Mock(status_code=200, text=CUPID, headers={})
        got = sh.check(session=S())
        self.assertEqual(len(got), 1)
        self.assertIn("봇 검사", got[0])


class CrawlerFalsePositives(unittest.TestCase):
    PAGE = ('<html><head><title>T</title><meta name="description" content="d"><link rel="canonical" href="https://fermata.it.kr/stocks/079810/">'
            '</head><body>{}</body></html>')

    def test_array_as_a_word_is_fine(self):
        page = self.PAGE.format("<p>display inspection equipment such as Array Testers, Aging Testers</p>")
        self.assertNotIn("이상한 값 'Array'", sc.page_checks("https://fermata.it.kr/stocks/079810/", page))

    def test_php_array_dump_is_caught(self):
        page = self.PAGE.format("<td>Array</td>")
        self.assertIn("이상한 값 'Array'", sc.page_checks("https://fermata.it.kr/stocks/079810/", page))

    def test_cloudflare_paths_are_skipped(self):
        self.assertTrue(sc.SKIP.search("https://fermata.it.kr/cdn-cgi/l/email-protection"))


class ProxyOff(unittest.TestCase):
    def test_proxy_off_is_one_clear_line(self):
        home = '<html><script src="https://www.googletagmanager.com/gtag/js?id=GT-1"></script><script src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1"></script></html>'

        class S:
            def get(self, url, **kw):
                if url.endswith("/cdn-cgi/trace"):
                    return mock.Mock(status_code=404, text="<html>404</html>", headers={})
                if url.endswith("/wp-sitemap.xml"):
                    return mock.Mock(status_code=200, text="<loc>https://fermata.it.kr/wp-sitemap-stocks-1.xml</loc>", headers={})
                return mock.Mock(status_code=200, text=home, headers={})
        with mock.patch.object(sh, "date_issues", return_value=[]):
            got = [i for i in sh.check(session=S()) if "프록시" in i or "관리자" in i or "로그인" in i]
        self.assertEqual(len(got), 1)
        self.assertIn("프록시가 꺼져", got[0])
