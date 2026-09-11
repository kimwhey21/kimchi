"""검색어 태그는 글에서 뽑는다 (2026-09-12, 사용자: "검색어 태그가 너무 부족한 것 아닌가" → "진행").

전에는 한국어 시황이 워드프레스에 세 개(코스피·코스닥·원달러 환율)로 매일 같았고, Checkpoint는 네이버에
세 개뿐·워드프레스에 0개였다. 이제 고정어 + 원고의 tags + 종목 + 주제어 + 달, 12개까지.
"""
from __future__ import annotations

import unittest

from src import post_tags

DAILY = {
    "market": "kr", "date": "2026-09-11",
    "price_data": {"watchlist": {
        "042700": {"name": "한미반도체", "change_pct": -8.70, "source": "core"},
        "005930": {"name": "삼성전자", "change_pct": -3.53, "source": "core"},
        "105560": {"name": "KB금융", "change_pct": 1.2, "source": "core"},
        "047040": {"name": "대우건설", "change_pct": 6.1, "source": "dynamic"},
    }},
    "ko": {"title": "코스피 1.76% 하락, 원인은 유가 100달러 재돌파에 있었습니다",
           "narrative": [{"heading": "1. 외국인은 팔았다", "body": "외국인이 순매도로 돌아섰습니다. 한미반도체가 8.70% 내렸고 삼성전자도 밀렸습니다. KB금융은 올랐습니다."},
                         {"heading": "2. 금리와 환율", "body": "국채금리가 올랐고 원/달러 환율은 1,344원입니다."}],
           "closing": {"heading": "Fermata's Take", "body": "우리는 유가를 봅니다."}},
}

FEATURE = {
    "kind": "feature", "series": "기준표", "date": "2026-09-06", "tags": ["인텔"],
    "ko": {"title": "인텔 CEO의 매수는 진짜일까, 10월 실적 전에 볼 것 세 가지",
           "narrative": [{"heading": "1. 내부자 매수 공시", "body": "CEO가 직접 매수했습니다. 목표주가는 그대로입니다."}],
           "closing": {"heading": "Fermata's Take", "body": "10월 실적 발표까지 봅니다."}},
}


class BuildTagsTest(unittest.TestCase):
    def test_daily_post_gets_fixed_stock_theme_and_month_tags(self) -> None:
        tags = post_tags.build_tags(DAILY)
        for fixed in ("코스피", "주식시황", "코스피마감", "페르마타"):
            self.assertIn(fixed, tags)
        self.assertIn("한미반도체", tags)
        self.assertIn("삼성전자", tags)
        self.assertNotIn("KB금융", tags, "2% 미만 움직인 종목은 태그가 아니다")
        self.assertNotIn("대우건설", tags, "본문에 이름이 없는 종목은 태그가 아니다")
        self.assertIn("유가", tags)
        self.assertIn("외국인순매수", tags)
        self.assertIn("9월증시", tags)
        self.assertLessEqual(len(tags), post_tags.LIMIT)
        self.assertEqual(len(tags), len(set(tags)))

    def test_title_themes_come_before_body_themes(self) -> None:
        tags = post_tags.build_tags(DAILY)
        self.assertLess(tags.index("유가"), tags.index("금리"))

    def test_feature_keeps_manual_tags_and_finds_themes(self) -> None:
        tags = post_tags.build_tags(FEATURE)
        self.assertEqual(tags[:3], ["주식", "투자체크포인트", "페르마타"])
        self.assertIn("인텔", tags)
        self.assertIn("내부자매수", tags)
        self.assertIn("실적발표", tags)
        self.assertIn("목표주가", tags)

    def test_tags_are_letters_and_digits_only(self) -> None:
        doc = dict(FEATURE, tags=["원/달러 환율", "S&P 500", "a"])
        tags = post_tags.build_tags(doc)
        self.assertIn("원달러환율", tags)
        self.assertIn("SP500", tags)
        self.assertNotIn("a", tags)

    def test_short_names_need_a_word_boundary(self) -> None:
        """'소비자물가'에서 '비자'가 종목으로 잡혔다(2026-09-12 시험 실행)."""
        self.assertFalse(post_tags.mentioned("비자", "8월 소비자물가가 올랐습니다"))
        self.assertTrue(post_tags.mentioned("비자", "비자가 올랐습니다"))
        self.assertTrue(post_tags.mentioned("디어", "디어의 실적은"))
        self.assertFalse(post_tags.mentioned("디어", "코디어스"))
        self.assertTrue(post_tags.mentioned("삼성전자", "삼성전자가 3% 내렸다"))
        self.assertFalse(post_tags.mentioned("전자", "삼성전자가 내렸다"))

    def test_weekend_series_have_their_own_fixed_tags(self) -> None:
        review = {"series": "주간 결산", "date": "2026-09-12", "ko": {"title": "이번 주 증시", "narrative": []}}
        ahead = {"series": "다음 주 일정", "date": "2026-09-13", "ko": {"title": "다음 주 증시", "narrative": []}}
        self.assertIn("주간증시", post_tags.build_tags(review))
        self.assertIn("증시일정", post_tags.build_tags(ahead))


if __name__ == "__main__":
    unittest.main()
