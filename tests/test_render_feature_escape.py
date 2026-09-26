"""기준표 계열 렌더의 이스케이프 (2026-09-26) — select_autoescape에 "j2"가 빠져 feature.html.j2가 날것으로 나갔다."""
import unittest

from src import render_feature


class EscapeTest(unittest.TestCase):
    def test_quotes_in_alt_do_not_break_the_tag_and_paragraph_html_stays(self) -> None:
        doc = {"ko": {"title": 'Before you assume a stock is "in the index"',
                      "narrative": [{"heading": "A & B", "body": "<b>굵게</b> 문단입니다."}],
                      "closing": {"heading": "Fermata's Take", "body": "끝."}}}
        html = render_feature.render(doc, "Checkpoint", {0: {"url": "https://x/a.png", "alt": '"7,000선" 실패'}})
        self.assertIn('alt="&#34;7,000선&#34; 실패"', html)
        self.assertIn("A &amp; B", html)
        self.assertIn("<b>굵게</b>", html)          # 본문 문단은 원래 HTML(|safe)


if __name__ == "__main__":
    unittest.main()
