"""영어 시황 끝 'Previous close' 링크 제목이 두 번 이스케이프되지 않는지 (2026-09-27 전수 점검에서 찾음).

워드프레스 REST의 title.rendered는 이미 'We&#8217;re'처럼 이스케이프돼 온다. 그대로 템플릿에 넘기면 Jinja가 다시
이스케이프해 화면에 'We&#8217;re'가 글자 그대로 보였다(영어 시황 7편).
"""
from __future__ import annotations

import unittest
from unittest import mock

from src import publish_editorial as pe


class PreviousPostTitleTest(unittest.TestCase):
    def test_title_is_unescaped(self):
        post = {"status": "publish", "title": {"rendered": "Why We&#8217;re Not Buying Today&#8217;s Drop"}, "link": "https://x/p/"}
        env = {"WORDPRESS_URL": "https://x", "WORDPRESS_USERNAME": "u", "WORDPRESS_APP_PASSWORD": "p"}
        with mock.patch.dict("os.environ", env), \
                mock.patch.object(pe.publish_wordpress, "is_configured", return_value=True), \
                mock.patch.object(pe.publish_wordpress, "_find_existing_post_by_slug", return_value=post):
            got = pe._previous_daily_post("us", "2099-01-01", "en")
        self.assertEqual(got["title"], "Why We’re Not Buying Today’s Drop")


if __name__ == "__main__":
    unittest.main()
