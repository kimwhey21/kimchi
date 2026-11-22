"""공식 문서 읽기 도구(2026-11-22) — 네트워크 없이 길 고르기만 본다."""
from __future__ import annotations

import unittest
from unittest import mock

from scripts import read_official as ro


def _resp(status=200, content=b"", text=""):
    r = mock.Mock(status_code=status, content=content or text.encode("utf-8"), text=text, encoding="utf-8")
    r.apparent_encoding = "utf-8"
    return r


class ReadOfficialTest(unittest.TestCase):
    def test_html_text_drops_scripts_and_keeps_lines(self) -> None:
        text = ro.html_text("<html><script>var x=1</script><p>세율 22%</p><div>기본공제&nbsp;250만원</div></html>")
        self.assertNotIn("var x", text)
        self.assertIn("세율 22%", text)
        self.assertIn("기본공제 250만원", text)

    def test_pdf_is_read_as_pdf_even_when_served_as_octet_stream(self) -> None:
        with mock.patch.object(ro.requests, "get", return_value=_resp(content=b"%PDF-1.4 ...")), \
             mock.patch.object(ro, "pdf_text", return_value="배당기준일 안내") as pdf:
            how, text = ro.read("https://x/getFile", ["배당기준일"])
        pdf.assert_called_once()
        self.assertIn("PDF", how)
        self.assertEqual(text, "배당기준일 안내")

    def test_static_html_with_the_words_skips_the_browser(self) -> None:
        with mock.patch.object(ro.requests, "get", return_value=_resp(text="<p>정기변경 12월 11일</p>")), \
             mock.patch.object(ro, "rendered_text") as browser:
            how, text = ro.read("https://x", ["정기변경"])
        browser.assert_not_called()
        self.assertIn("정기변경", text)

    def test_missing_words_open_the_browser_and_keep_both_texts(self) -> None:
        with mock.patch.object(ro.requests, "get", return_value=_resp(text="<p>메뉴 틀</p>")), \
             mock.patch.object(ro, "rendered_text", return_value="회신 본문") as browser:
            how, text = ro.read("https://x", ["회신"])
        browser.assert_called_once()
        self.assertIn("회신 본문", text)
        self.assertIn("메뉴 틀", text)

    def test_refused_site_is_not_worked_around(self) -> None:
        with mock.patch.object(ro.requests, "get", return_value=_resp(status=403, text="blocked")), \
             mock.patch.object(ro, "rendered_text") as browser:
            how, text = ro.read("https://x", ["무엇"])
        browser.assert_not_called()
        self.assertTrue(how.startswith("못 읽음"))
        self.assertEqual(text, "")

    def test_excerpts_show_context(self) -> None:
        found = ro.excerpts("a\nb\n세율 22%\nc\nd", "세율", around=1)
        self.assertEqual(found, ["b\n세율 22%\nc"])


if __name__ == "__main__":
    unittest.main()
