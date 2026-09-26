"""`scripts/routine_precheck` — 루틴의 첫 명령이 결론을 맞게 내는지 (2026-09-25).

2026-09-25 루틴 실행 감사: 첫 탐색 7턴, 어제 원고 JSON 통째 읽기 4만~8만 자, 예비 실행이 지시문 19K자를 읽은
뒤에야 '원고 있음'을 알았다. 이 테스트는 임시 디렉터리에 가짜 `data/`·`editorial/`을 만들어 세 결론 —
`종료: 원고 있음`·`계속:`·`종료: 새 거래일 시세 없음` — 과 어제 원고 요약·재료·그래픽·낱말 항목을 확인한다.
시각은 `now`로 고정한다(kr은 KST 오늘, us는 KST 어제가 다루는 거래일).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import routine_precheck as rp


def _kst(text: str) -> dt.datetime:
    return rp.parse_now(text)


def _price(date: str, n: int = 5, dynamic: int = 2, flows: bool = True) -> dict:
    watch = {}
    for i in range(n):
        entry = {"ticker": f"00{i}", "name": f"종목{i}", "price": 100 + i, "change_pct": 1.0,
                 "source": "dynamic" if i < dynamic else "core"}
        if flows:
            entry["foreign_net"] = 1000 * i
        watch[entry["ticker"]] = entry
    return {"macro": {"KS11": {"price": 7000, "change_pct": 0.1}}, "watchlist": watch,
            "trading_date": date, "missing": []}


def _doc(market: str, date: str, title: str, of_date: str = "2026-09-01", *, series: str | None = None) -> dict:
    doc = {"market": market, "date": date,
           "review": {"of_date": of_date, "verdict": "mixed", "result": "외국인은 순매도, 기관은 순매수였습니다."},
           "ko": {"title": title,
                  "narrative": [{"heading": "오늘 투자심리", "body": "본문"},
                                {"heading": "반도체가 올랐습니다", "body": "본문"}],
                  "outlook": {"heading": "내일 볼 것", "body": "<p>" + "가" * 500 + "</p>"},
                  "closing": {"heading": "Fermata's Take", "body": "판단",
                              "check": {"due": "2026-09-24", "what": "외국인 순매수 복귀"}}}}
    if series:
        doc["series"] = series
        doc.pop("market")
        doc["ko"].pop("outlook")
        doc.pop("review")
    return doc


class _Repo:
    """임시 저장소 — data/·editorial/previews/만 있는 빈 뼈대."""

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / "data").mkdir()
        (self.root / "editorial" / "previews").mkdir(parents=True)

    def price(self, key: str, date: str, **kw) -> None:
        (self.root / "data" / f"price_{key}_{date}.json").write_text(json.dumps(_price(date, **kw)), encoding="utf-8")

    def engines(self, key: str, date: str, text: str | bytes) -> Path:
        path = self.root / "data" / f"engines_{key}_{date}.txt"
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
            path.write_text(text, encoding="utf-8")
        return path

    def doc(self, market: str, date: str, title: str, **kw) -> Path:
        path = rp.manuscript_path(self.root, market, date)
        series = "프리뷰" if market == "preview" else None
        path.write_text(json.dumps(_doc("us" if market == "preview" else market, date, title, series=series, **kw),
                                   ensure_ascii=False), encoding="utf-8")
        return path


class RoutinePrecheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = _Repo()
        self.addCleanup(self.repo.tmp.cleanup)
        self.root = self.repo.root
        # ⑩은 매체 피드를 받는다(네트워크) — 테스트에서는 바꿔 끼우고, 무엇을 넘겼는지 본다.
        self.media_calls: list[tuple] = []

        def fake_media(market, now, names):
            self.media_calls.append((market, now, list(names)))
            return f"(시험 헤드라인 {market})"

        patcher = mock.patch.object(rp, "media_text", side_effect=fake_media)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _build(self, market: str, now: str, **kw) -> str:
        return rp.build(market, root=self.root, now=_kst(now), **kw)

    # ── 결론 셋 ─────────────────────────────────────────────────────────────
    def test_kr_stops_when_manuscript_exists(self) -> None:
        """예비 실행(17:40)의 정상 종료 — 첫 줄만 읽고 끝낼 수 있어야 하므로 뒤 항목은 붙이지 않는다."""
        self.repo.price("kr", "2026-09-23")
        self.repo.doc("kr", "2026-09-23", "오늘 제목")
        text = self._build("kr", "2026-09-23T17:40")
        self.assertEqual(text.splitlines()[0], "종료: 원고 있음 editorial/kr_2026-09-23.json")
        self.assertNotIn("## ⑤", text)
        self.assertIn("원고 editorial/kr_2026-09-23.json: 있음 → 종료", text)

    def test_kr_continues_and_summarizes_yesterday(self) -> None:
        self.repo.price("kr", "2026-09-23")
        self.repo.doc("kr", "2026-09-22", "어제 제목입니다", of_date="2026-09-21")
        self.repo.engines("kr", "2026-09-23", "[밸류에이션] KR · 2026-09-23\n  ⚠ 2건을 받지 못했습니다.\n[수급 엇갈림]\n")
        text = self._build("kr", "2026-09-23T16:25")
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("계속: kr 거래일 2026-09-23 — 시세 있음(5종목·수급 5), 원고 없음(editorial/kr_2026-09-23.json)"), lines[0])
        self.assertLessEqual(len(text), rp.MAX_CHARS)
        # ① ② ③④
        self.assertIn("KST 2026-09-23 16:25 (수)", text)
        self.assertIn("종목 5 (코어 3 · 편입 2) · 수급(foreign_net) 있는 종목 5", text)
        self.assertIn("커밋 이력 없음", text)          # 임시 디렉터리는 git 저장소가 아니다 — 이유가 찍힌다
        self.assertIn("새 거래일 시세: 있음(거래일 2026-09-23 = 다루는 거래일)", text)
        # ⑤ 재료
        self.assertIn("data/engines_kr_2026-09-23.txt: 3줄 · ⚠ 1건", text)
        self.assertIn("절: [밸류에이션] [수급 엇갈림]", text)
        self.assertIn("2행: ⚠ 2건을 받지 못했습니다.", text)
        # ⑥ 어제 원고 요약 — 통째가 아니라 다섯 줄
        self.assertIn("[editorial/kr_2026-09-22.json]", text)
        self.assertIn("제목: 어제 제목입니다", text)
        self.assertIn("소제목 2개: 1.오늘 투자심리 / 2.반도체가 올랐습니다", text)
        self.assertIn("확인 지점(closing.check): 2026-09-24까지 — 외국인 순매수 복귀", text)
        self.assertIn("어제 판정(review): 2026-09-21 글 판정 mixed — 외국인은 순매도", text)
        self.assertIn("전망(outlook) 「내일 볼 것」: " + "가" * 299 + "…", text)   # 300자에서 잘리고 태그는 벗겨진다
        self.assertNotIn("가" * 300, text)
        self.assertNotIn("<p>", text)
        self.assertNotIn("본문", text.split("## ⑥")[1].split("## ⑦")[0])   # 본문은 읽지 않는다
        # ⑦ 최근 제목 — 임시 루트에서는 피드의 제목만
        self.assertIn("[09-22 16:20 한국장] 어제 제목입니다", text)
        # ⑧ 그래픽 — 시황은 data_graphics만
        self.assertIn("- number_cards: 필수 없음 → 선택 tickers·items·title·subtitle·note·period_days·period", text)
        self.assertIn("- price_history: 필수 ticker → 선택 title·subtitle·guide·guide_label", text)
        self.assertIn("- fact_table: 필수 rows·source", text)
        self.assertNotIn("valuation_bars", text)
        # ⑨ 낱말
        self.assertIn("반대편", text)
        self.assertIn("내렸/내린/내려→하락했습니다", text)
        self.assertNotIn("확인 실패", text)

    def test_kr_stale_price_stops_unless_allowed(self) -> None:
        """휴장(추석 2026-09-24)이나 수집 실패 — 최신 시세가 어제 것이면 종료, --allow-stale이면 경고만."""
        self.repo.price("kr", "2026-09-23")
        self.repo.doc("kr", "2026-09-23", "어제 제목")
        text = self._build("kr", "2026-09-24T16:25")
        self.assertEqual(text.splitlines()[0], "종료: 새 거래일 시세 없음(거래일 2026-09-23)")
        self.assertIn("원고 editorial/kr_2026-09-24.json: 없음", text)
        text = self._build("kr", "2026-09-24T17:40", allow_stale=True)
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("계속: kr 거래일 2026-09-24 — 시세 없음(최신 2026-09-23, --allow-stale)"), lines[0])
        self.assertTrue(lines[1].startswith("경고: 시세 파일 거래일 2026-09-23 ≠ 다루는 거래일 2026-09-24"), lines[1])
        self.assertIn("--fetch-only", lines[1])
        self.assertIn("[editorial/kr_2026-09-23.json]", text)     # 어제 원고 요약은 그대로 나온다

    def test_no_price_file_at_all(self) -> None:
        text = self._build("kr", "2026-09-23T16:25")
        self.assertEqual(text.splitlines()[0], "종료: 시세 파일 없음(data/price_kr_*.json)")

    # ── 미국장: 다루는 거래일은 KST 어제 ─────────────────────────────────────
    def test_us_trading_day_is_kst_yesterday(self) -> None:
        self.repo.price("us", "2026-09-24", flows=False)
        text = self._build("us", "2026-09-25T07:30")
        self.assertTrue(text.splitlines()[0].startswith("계속: us 거래일 2026-09-24 — 시세 있음(5종목·수급 0)"), text.splitlines()[0])
        self.assertIn("다루는 거래일 2026-09-24(미국 현지 = KST 어제)", text)
        self.repo.doc("us", "2026-09-24", "오늘 미국장")
        text = self._build("us", "2026-09-25T08:40")
        self.assertEqual(text.splitlines()[0], "종료: 원고 있음 editorial/us_2026-09-24.json")

    def test_us_monday_morning_has_no_new_session(self) -> None:
        """월요일 아침 KST: 어제(일)는 미국장이 없다 — 최신 파일은 금요일 → 종료."""
        self.repo.price("us", "2026-09-25")
        text = self._build("us", "2026-09-28T07:30")
        self.assertEqual(text.splitlines()[0], "종료: 새 거래일 시세 없음(거래일 2026-09-25)")

    # ── 프리뷰 ───────────────────────────────────────────────────────────────
    def _preview_fixture(self) -> None:
        self.repo.price("us", "2026-09-24", flows=False)
        self.repo.doc("us", "2026-09-24", "어제 미국장 제목")
        prev = self.repo.doc("preview", "2026-09-24", "어젯밤 프리뷰 제목")
        doc = json.loads(prev.read_text(encoding="utf-8"))
        doc["ko"]["closing"]["check"] = {"due": "2026-09-25", "what": "청구 건수가 어느 쪽으로 갔는지"}
        prev.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        self.repo.engines("us", "2026-09-25", "[월가 리포트] 2026-09-25\n")

    def test_preview_continues_with_both_yesterday_pieces(self) -> None:
        self._preview_fixture()
        text = self._build("preview", "2026-09-25T21:35")
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("계속: preview 2026-09-25 — 어젯밤 미국장 시세 2026-09-24(5종목), "
                                            "오늘 밤 프리뷰 없음(editorial/previews/us_2026-09-25.json)"), lines[0])
        self.assertIn("어젯밤 미국장 시세: 있음(거래일 2026-09-24)", text)
        self.assertIn("오늘 한국장 종가 data/price_kr_2026-09-25.json: 없음", text)
        self.assertIn("오늘 밤 미국 휴장 여부는 이 도구가 모른다", text)
        self.assertIn("data/engines_us_2026-09-25.txt: 1줄 · ⚠ 0건", text)
        self.assertIn("[어제 미국장 editorial/us_2026-09-24.json]", text)
        self.assertIn("제목: 어제 미국장 제목", text)
        self.assertIn("[어제 프리뷰 editorial/previews/us_2026-09-24.json]", text)
        self.assertIn("2026-09-25까지 — 청구 건수가 어느 쪽으로 갔는지", text)
        self.assertIn("- calendar_strip: 필수 events → 선택 title·subtitle", text)
        self.assertIn("- valuation_bars: 필수 rows", text)
        self.assertIn("- number_cards:", text)
        self.assertIn("[09-24 21:30 프리뷰] 어젯밤 프리뷰 제목", text)
        self.assertLessEqual(len(text), rp.MAX_CHARS)
        self.assertNotIn("확인 실패", text)

    def test_preview_stops_when_tonight_exists(self) -> None:
        self._preview_fixture()
        self.repo.doc("preview", "2026-09-25", "오늘 밤 프리뷰")
        text = self._build("preview", "2026-09-25T21:35")
        self.assertEqual(text.splitlines()[0], "종료: 원고 있음 editorial/previews/us_2026-09-25.json")

    def test_preview_warns_when_last_night_prices_missing(self) -> None:
        """화요일 밤인데 월요일 미국장 파일이 없다 — 종료가 아니라 경고(휴장이었을 수 있다)."""
        self.repo.price("us", "2026-09-25", flows=False)
        text = self._build("preview", "2026-09-29T21:35")
        self.assertTrue(text.splitlines()[0].startswith("계속: preview 2026-09-29"))
        self.assertIn("경고: 어젯밤 미국장(마지막 평일 2026-09-28) 시세가 없음 — 최신은 2026-09-25", text)
        self.assertIn("경고: 어제 미국장 원고도 재료 파일도 없음", text)
        # 월요일 밤은 금요일 파일이 '어젯밤'이다 — 경고가 없어야 한다.
        text = self._build("preview", "2026-09-28T21:35")
        self.assertNotIn("어젯밤 미국장(마지막 평일", text)
        self.assertIn("어젯밤 미국장 시세: 있음(거래일 2026-09-25)", text)

    # ── 조용한 실패 금지 ─────────────────────────────────────────────────────
    def test_section_failure_is_counted_not_swallowed(self) -> None:
        self.repo.price("kr", "2026-09-23")
        self.repo.engines("kr", "2026-09-23", b"\xff\xfe\x00")   # utf-8이 아니다
        text = self._build("kr", "2026-09-23T16:25")
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("계속:"))
        self.assertTrue(lines[1].startswith("확인 실패 1건: ⑤ 재료: UnicodeDecodeError"), lines[1])
        self.assertIn("## ⑤ 재료\n확인 실패 — UnicodeDecodeError", text)
        self.assertIn("## ⑥", text)                               # 나머지 항목은 계속 나온다

    def test_run_section_reports_reason(self) -> None:
        failures: list[str] = []

        def boom() -> str:
            raise RuntimeError("이유")

        out = rp._run_section("시험", boom, failures)
        self.assertEqual(out, "## 시험\n확인 실패 — RuntimeError: 이유")
        self.assertEqual(failures, ["시험: RuntimeError: 이유"])

    # ── ⑩ 검색에 막힌 매체의 헤드라인(2026-09-26) ─────────────────────────────
    def test_daily_markets_get_blocked_media_headlines(self) -> None:
        """시황 둘에만 붙는다 — 프리뷰는 시황 매체 목록을 쓰지 않는다. 종목 이름을 넘겨 관련 제목을 앞에 세운다."""
        self.repo.price("kr", "2026-09-23")
        text = self._build("kr", "2026-09-23T16:25")
        self.assertIn("## ⑩ 검색에 막힌 매체의 헤드라인", text)
        self.assertIn("(시험 헤드라인 kr)", text)
        market, now, names = self.media_calls[-1]
        self.assertEqual(market, "kr")
        self.assertEqual(now, _kst("2026-09-23T16:25"))
        self.assertTrue(names, "시세 파일의 종목 이름을 넘겨야 한다")
        self._preview_fixture()
        before = len(self.media_calls)
        text = self._build("preview", "2026-09-25T21:35")
        self.assertNotIn("## ⑩", text)
        self.assertEqual(len(self.media_calls), before)

    def test_headlines_are_skipped_when_the_routine_stops(self) -> None:
        """종료 날은 피드를 받지 않는다 — 첫 줄만 읽고 끝나는 실행에 네트워크를 쓰지 않는다."""
        self.repo.price("kr", "2026-09-23")
        self.repo.doc("kr", "2026-09-23", "오늘 제목")
        self._build("kr", "2026-09-23T17:40")
        self.assertEqual(self.media_calls, [])

    def test_headline_failure_is_counted(self) -> None:
        self.repo.price("us", "2026-09-25")
        with mock.patch.object(rp, "media_text", side_effect=RuntimeError("헤드라인 피드를 하나도 받지 못했습니다")):
            text = self._build("us", "2026-09-26T07:25")
        self.assertIn("확인 실패 1건: ⑩ 검색에 막힌 매체의 헤드라인", text)
        self.assertTrue(text.startswith("계속:"))

    def test_watchlist_names_reads_both_languages(self) -> None:
        data = {"watchlist": {"005930": {"name": "삼성전자", "name_en": "Samsung Electronics"},
                              "NVDA": {"name": "엔비디아", "name_en": "NVIDIA"}, "X": "깨진 줄"}}
        self.assertEqual(rp.watchlist_names(data), ["삼성전자", "Samsung Electronics", "엔비디아", "NVIDIA"])
        self.assertEqual(rp.watchlist_names({}), [])

    def test_dynamic_missing_is_a_warning(self) -> None:
        self.repo.price("kr", "2026-09-23", dynamic=0)
        text = self._build("kr", "2026-09-23T16:25")
        self.assertIn("경고: 시세 파일에 편입(dynamic) 종목이 없음", text)

    # ── 상한·CLI·루트 ────────────────────────────────────────────────────────
    def test_output_is_clipped_at_limit_with_note(self) -> None:
        self.repo.price("kr", "2026-09-23")
        self.repo.doc("kr", "2026-09-22", "어제 제목")
        with mock.patch.object(rp, "MAX_CHARS", 1500):
            text = self._build("kr", "2026-09-23T16:25")
        self.assertLessEqual(len(text), 1500)
        self.assertTrue(text.endswith("위에 다 있습니다)"), text[-80:])
        self.assertTrue(text.startswith("계속:"))

    def test_cli_main_prints_and_returns_zero(self) -> None:
        self.repo.price("kr", "2026-09-23")
        self.repo.doc("kr", "2026-09-23", "오늘 제목")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = rp.main(["kr", "--root", str(self.root), "--now", "2026-09-23T17:40"])
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue().splitlines()[0], "종료: 원고 있음 editorial/kr_2026-09-23.json")

    def test_env_root(self) -> None:
        with mock.patch.dict(os.environ, {"MARKET_BRIEF_ROOT": str(self.root)}):
            self.assertEqual(rp.default_root(), self.root)
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(rp.default_root(), rp.REPO_ROOT)

    def test_rejects_unknown_market(self) -> None:
        with self.assertRaises(ValueError):
            rp.build("jp", root=self.root, now=_kst("2026-09-23T16:25"))


class CodeDerivedTablesTest(unittest.TestCase):
    """⑧·⑨는 코드에서 읽는다 — 실제 src/와 어긋나면 여기서 잡힌다."""

    def test_graphic_kinds_match_real_builders(self) -> None:
        daily = {k: (req, opt) for k, req, opt in rp.graphic_kinds(
            rp.SRC / "data_graphics.py", registry="BUILDERS", skip=frozenset({"price_data", "output_path", "lang"}))}
        self.assertEqual(daily["price_history"][0], ["ticker"])
        self.assertIn("guide", daily["price_history"][1])
        self.assertEqual(daily["fact_table"][0], ["rows", "source"])
        self.assertEqual(daily["investor_flows"][0], ["values", "source"])
        self.assertEqual(daily["number_cards"][0], [])
        self.assertTrue({"fact_table", "investor_flows"} <= rp.priceless_kinds())
        feature = {k: (req, opt) for k, req, opt in rp.graphic_kinds(
            rp.SRC / "feature_graphics.py", registry=None, skip=frozenset({"output_path"}))}
        self.assertEqual(feature["calendar_strip"][0], ["events"])
        self.assertEqual(feature["checklist"][0], ["items"])
        self.assertEqual(feature["cover"][0], ["kicker", "subject"])
        self.assertNotIn("_canvas", feature)
        # 실제 빌더와 대조 — 코드에서 읽은 표가 함수 서명과 같아야 한다.
        import inspect
        from src import data_graphics
        for kind, fn in data_graphics.BUILDERS.items():
            params = [p for p in inspect.signature(fn).parameters if p not in {"price_data", "output_path", "lang"}]
            self.assertEqual(daily[kind][0] + daily[kind][1], params, kind)

    def test_graphic_kinds_fails_loudly_without_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.py"
            path.write_text("def a(rows, output_path):\n    pass\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                rp.graphic_kinds(path, registry="BUILDERS", skip=frozenset())
            self.assertEqual(rp.graphic_kinds(path, registry=None, skip=frozenset({"output_path"})), [("a", ["rows"], [])])

    def test_vocabulary_cards_come_from_editorial_quality(self) -> None:
        from src import editorial_quality as eq
        cards = rp.vocabulary_cards()
        self.assertLessEqual(len(cards), rp.MAX_VOCAB)
        joined = "\n".join(cards)
        for word in eq._NEVER_USED:
            self.assertIn(word, joined, word)
        self.assertIn("눌렸/눌리→", joined)          # 같은 안내문은 한 장
        self.assertIn("내렸/내린/내려→하락했습니다", joined)
        self.assertIn("워치리스트", joined)
        self.assertIn("자리입니다", joined)
        text = rp.vocabulary_text(width=60)
        for line in text.splitlines():
            self.assertTrue(any(line.startswith(c[:10]) for c in cards), line)   # 카드 경계에서만 줄을 바꾼다


if __name__ == "__main__":
    unittest.main()
