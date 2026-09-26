"""발행 쪽 잠재 오류 셋 (2026-09-26 점검).

1. 한글이 섞이거나 빈 주소 → 빈 주소로 기존 글을 찾으면 워드프레스가 최근 글을 돌려줘 그 글을 덮어쓸 수 있었다.
2. 새 글·새 그림을 만드는 POST의 재시도 → 서버가 저장한 뒤 502가 나면 같은 글이 두 편 생긴다.
3. 시리즈 칸이 빠진 원고 → 관문은 Checkpoint로 보는데 발행만 공개로 올렸다.
"""
import unittest
from pathlib import Path
from unittest import mock

from src import publish_feature, publish_wordpress


class _Resp:
    def __init__(self, status: int, payload=None):
        self.status_code, self._payload, self.text = status, payload, str(payload)

    def json(self):
        return self._payload


class SlugTest(unittest.TestCase):
    def test_korean_or_empty_slug_stops(self) -> None:
        for bad in ("삼성전자-목표주가", "samsung-목표가"):
            with self.assertRaises(ValueError):
                publish_feature._slug({"slug": bad}, Path("x.json"))
        with self.assertRaises(ValueError):
            publish_feature._slug({"slug": "---"}, Path("x.json"))

    def test_normal_slugs_still_work(self) -> None:
        self.assertEqual(publish_feature._slug({}, Path("kr_2026-09-26_samsung_target_gap.json")),
                         "kr-2026-09-26-samsung-target-gap")
        self.assertEqual(publish_feature._slug({"slug": "us-2026-09-25-preview"}, Path("x.json")), "us-2026-09-25-preview")

    def test_empty_slug_lookup_is_refused_and_mismatch_is_none(self) -> None:
        with self.assertRaises(publish_wordpress.WordPressPublishError):
            publish_wordpress._find_existing_post_by_slug("https://x", ("u", "p"), "")
        with mock.patch.object(publish_wordpress.requests, "get", return_value=_Resp(200, [{"id": 1, "slug": "other"}])):
            self.assertIsNone(publish_wordpress._find_existing_post_by_slug("https://x", ("u", "p"), "mine"))


class RetryTest(unittest.TestCase):
    def test_create_is_not_sent_twice_when_the_first_one_landed(self) -> None:
        with mock.patch.object(publish_wordpress.requests, "post", return_value=_Resp(502, {})) as post, \
             mock.patch.object(publish_wordpress.time, "sleep"):
            response = publish_wordpress._request("post", "https://x/wp-json/wp/v2/posts",
                                                  before_retry=lambda: {"id": 42, "slug": "mine"})
        self.assertEqual(post.call_count, 1)
        self.assertEqual(response.json()["id"], 42)

    def test_without_a_finder_it_retries_as_before(self) -> None:
        with mock.patch.object(publish_wordpress.requests, "post",
                               side_effect=[_Resp(502, {}), _Resp(201, {"id": 7})]) as post, \
             mock.patch.object(publish_wordpress.time, "sleep"):
            response = publish_wordpress._request("post", "https://x/wp-json/wp/v2/posts/7")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(response.json()["id"], 7)


class SeriesTest(unittest.TestCase):
    def test_missing_series_is_blocked_before_commit(self) -> None:
        from src import feature_gate
        with self.assertRaises(feature_gate.FeatureGateError) as ctx:
            feature_gate.run({"ko": {"title": "제목", "narrative": []}}, graphics=0)
        self.assertIn("series가 없습니다", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
