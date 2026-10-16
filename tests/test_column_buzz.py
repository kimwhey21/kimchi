"""칼럼 소재 후보(scripts/column_buzz, 2026-10-16) — 한 사건에 몰린 기사를 묶어 세고, 못 받은 것은 센다(바깥 접속 없음)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

from scripts import column_buzz as cb


class StoryTest(unittest.TestCase):
    def test_same_event_in_different_words_is_one_story(self):
        titles = (["테슬라 '하늘 나는 차' 성공… 차량 5대 넘어"] * 30 + ["진짜 하늘을 날았다… 테슬라 로드스터 공개"] * 20
                  + ["테슬라 로드스터 2028년 양산"] * 20 + ["테슬라 중국 판매 감소"] * 5)
        word, size, sample = cb.story("테슬라", titles)
        self.assertGreaterEqual(size, 70)
        self.assertTrue(sample)

    def test_variety_is_higher_for_varied_headlines(self):
        copied = ["효성중공업, 창원 초고압차단기 신공장 준공"] * 20 + ["효성중공업, 초고압차단기 공장 준공 생산 확대"] * 20
        varied = [f"{h} 테슬라 로드스터 하늘" for h in ("진짜 날았다", "공중회전까지", "차량 5대 넘어", "9년 만에", "환호 터졌다",
                                                    "2028년 양산", "가격은 얼마", "[영상] 시연", "머스크 장담", "광화문서 공중회전?")] * 2
        self.assertLess(cb.variety("효성중공업", copied), cb.variety("테슬라", varied))

    def test_scattered_day_is_small(self):
        syl = lambda k: chr(0xAC00 + (k * 397) % 11000)   # noqa: E731 — 겹치지 않는 가짜 낱말
        titles = [f"삼성전자 {syl(i)}{syl(i + 100)} {syl(i + 200)}{syl(i + 300)}" for i in range(60)]
        self.assertLess(cb.story("삼성전자", titles)[1], 10)


class RankTest(unittest.TestCase):
    def _root(self):
        tmp = Path(tempfile.mkdtemp()); (tmp / "data").mkdir()
        (tmp / "data" / "price_kr_2026-10-16.json").write_text(json.dumps({"watchlist": {"1": {"name": "대한항공", "change_pct": -10.5}}, "macro": {}}), encoding="utf-8")
        (tmp / "data" / "price_us_2026-10-15.json").write_text(json.dumps({"watchlist": {"T": {"name": "테슬라", "change_pct": -1.29}}, "macro": {}}), encoding="utf-8")
        return tmp

    def test_candidates_from_both_markets(self):
        names = [c["name"] for c in cb.candidates("2026-10-16", self._root())]
        self.assertEqual(names, ["대한항공", "테슬라"])

    def test_too_many_failures_stop(self):
        with mock.patch.object(cb, "candidates", return_value=[{"name": "A", "market": "한국", "pct": 1, "file": "price_kr_x"}] * 3), \
                mock.patch.object(cb, "count", side_effect=requests.ConnectionError("x")):
            with self.assertRaises(SystemExit):
                cb.rank("2026-10-16", pause=0)

    def test_weekend_uses_friday_korea_file(self):
        names = [c["name"] for c in cb.candidates("2026-10-17", self._root())]   # 토요일 — 금요일 한국장 파일이 대신
        self.assertEqual(names, ["대한항공", "테슬라"])

    def test_no_price_files_stop(self):
        with self.assertRaises(SystemExit):
            cb.candidates("2027-03-01", Path(tempfile.mkdtemp()))


if __name__ == "__main__":
    unittest.main()
