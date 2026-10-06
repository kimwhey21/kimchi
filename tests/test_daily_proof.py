"""밤 11시 반 증명서(src/daily_proof.py)와 그 둘레 — 워커 표·워크플로·맥 신호·사장님 승인 경로 (2026-10-05).

원칙 하나: 독자가 본 것을 다른 원천으로 매일 다시 계산하고, 증명서가 안 오면 그것이 경보다.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import mac_beats
from src import daily_proof, fetch_kr

ROOT = Path(__file__).resolve().parent.parent
UTC = dt.timezone.utc
JOBS = {"direct": [
    {"workflow": "krx_close.yml", "utc": ["06:31", "06:39", "06:47"], "days": "1-5"},
    {"workflow": "market_brief.yml", "inputs": {"market": "us"}, "utc": ["22:20"], "days": "1-5"},
    {"workflow": "stock_db.yml", "utc": ["22:50"], "days": "0-5"},
    {"workflow": "market_brief.yml", "inputs": {"market": "kr"}, "utc": ["07:20"], "days": "1-5"},
    {"workflow": "daily_proof.yml", "utc": ["14:30"], "days": "0-6"},
], "watch": []}


class ExpectedJobsTest(unittest.TestCase):
    def test_cron_dow(self) -> None:
        self.assertFalse(daily_proof.cron_dow_ok("1-5", 0))
        self.assertTrue(daily_proof.cron_dow_ok("0-6", 6))
        self.assertTrue(daily_proof.cron_dow_ok("5,6", 6))

    def test_a_kst_day_spans_two_utc_days_and_merges_the_close_presses(self) -> None:
        jobs = daily_proof.expected_workflow_jobs(dt.date(2026, 10, 6), JOBS)   # 화요일
        labels = [j["label"] for j in jobs]
        self.assertEqual(labels, ["market_brief.yml (us)", "stock_db.yml", "krx_close.yml", "market_brief.yml (kr)", "daily_proof.yml"])
        self.assertEqual(jobs[0]["first"], dt.datetime(2026, 10, 5, 22, 20, tzinfo=UTC))   # 전날 UTC = 오늘 07:20 KST
        krx = jobs[2]
        self.assertEqual((krx["first"].hour, krx["first"].minute, krx["last"].minute), (6, 31, 47))
        self.assertEqual(krx["window"][0], krx["first"] - dt.timedelta(minutes=10))

    def test_weekend_and_monday_follow_the_cron_days(self) -> None:
        sunday = [j["label"] for j in daily_proof.expected_workflow_jobs(dt.date(2026, 10, 11), JOBS)]
        self.assertEqual(sunday, ["daily_proof.yml"])
        monday = [j["label"] for j in daily_proof.expected_workflow_jobs(dt.date(2026, 10, 12), JOBS)]
        self.assertEqual(monday, ["stock_db.yml", "krx_close.yml", "market_brief.yml (kr)", "daily_proof.yml"])   # 일 22:50 UTC = 월 07:50 KST

    def test_job_status(self) -> None:
        job = daily_proof.expected_workflow_jobs(dt.date(2026, 10, 6), JOBS)[3]   # kr 07:20 UTC
        run = lambda minute, conclusion, status="completed": {   # noqa: E731
            "path": ".github/workflows/market_brief.yml", "created_at": f"2026-10-06T07:{minute:02d}:00Z",
            "conclusion": conclusion, "status": status}
        self.assertEqual(daily_proof.job_status(job, [run(21, "failure"), run(28, "success")]), "ok")
        self.assertEqual(daily_proof.job_status(job, [run(21, "failure")]), "실패")
        self.assertEqual(daily_proof.job_status(job, [run(21, None, "in_progress")]), "진행 중")
        self.assertEqual(daily_proof.job_status(job, []), "없음")
        other = {**run(21, "success"), "path": ".github/workflows/stock_db.yml"}
        self.assertEqual(daily_proof.job_status(job, [other]), "없음")


class BuildJobsTest(unittest.TestCase):
    def test_two_runs_of_the_same_workflow_are_judged_separately(self) -> None:
        """종목 DB는 07:50·17:05 두 번 — 아침 것이 성공했는데 저녁 것(아직 안 돈)에 덮여 '없음'이 나왔다(2026-10-05 시험)."""
        jobs = {"direct": [{"workflow": "stock_db.yml", "utc": ["22:50"], "days": "0-5"}, {"workflow": "stock_db.yml", "utc": ["08:05"], "days": "1-5"}], "watch": []}
        runs = [{"path": ".github/workflows/stock_db.yml", "created_at": "2026-10-05T22:51:07Z", "conclusion": "success", "status": "completed"}]
        now = dt.datetime(2026, 10, 6, 13, 17, tzinfo=daily_proof.KST)
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / "jobs.json"
            table.write_text(json.dumps(jobs), encoding="utf-8")
            with mock.patch.object(daily_proof, "JOBS", table), \
                    mock.patch.object(daily_proof, "github_runs", return_value=runs), \
                    mock.patch.object(daily_proof, "changed_today", return_value=set()), \
                    mock.patch.object(daily_proof, "expected_artifacts", return_value=[]), \
                    mock.patch.object(daily_proof, "mac_issues", return_value=([], 0, 0)), \
                    mock.patch.object(daily_proof.close_check, "check", return_value=[]), \
                    mock.patch.object(daily_proof.close_check, "pcv_day", return_value=None), \
                    mock.patch.object(daily_proof.close_check, "check_stocks", return_value=[]), \
                    mock.patch.object(daily_proof.close_check, "us_recheck", return_value=([], 30, [])), \
                    mock.patch.object(daily_proof.check_publication, "check_market", return_value=[]), \
                    mock.patch.dict(os.environ, {"ECOS_API_KEY": "k", "WORDPRESS_URL": ""}):
                text, issues, parts = daily_proof.build(dt.date(2026, 10, 6), now, screens=False)
        self.assertEqual(parts["작업"], "1/1")       # 17:05 것은 아직 창이 안 닫혀 세지 않는다
        self.assertFalse(any(i.startswith("작업 stock_db") for i in issues), issues)


class ExpectedArtifactsTest(unittest.TestCase):
    def _root(self, files: list[str]) -> Path:
        tmp = Path(tempfile.mkdtemp())
        for rel in files:
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_text("{}", encoding="utf-8")
        return tmp

    def test_weekday_expectations(self) -> None:
        root = self._root(["editorial/kr_2026-10-06.json", "data/price_us_2026-10-05.json", "editorial/previews/us_2026-10-06.json",
                           "editorial/magazine/2026-10-06_a.json", "editorial/magazine/2026-10-06_b.json"])
        arts = daily_proof.expected_artifacts(dt.date(2026, 10, 6), {"editorial/guides/ko_x.json"}, root)
        got = {name: ok for name, ok, _ in arts}
        self.assertEqual(got, {"한국장 시세": False, "종가 사진": False, "한국장 시황": True, "미국장 시황": False,
                               "미국장 프리뷰": True, "잡지 3편": False, "한국어 가이드": True, "영어 가이드": False})

    def test_not_yet_due_artifacts_are_not_missing(self) -> None:
        """13:17에 손으로 돌리면 프리뷰(22:30 뒤)·한국어 가이드(14:00 뒤)는 아직 없다고 하지 않는다."""
        root = self._root(["data/price_us_2026-10-05.json"])
        noon = dt.datetime(2026, 10, 6, 13, 17, tzinfo=daily_proof.KST)
        names = [n for n, _, _ in daily_proof.expected_artifacts(dt.date(2026, 10, 6), set(), root, noon)]
        self.assertEqual(names, ["미국장 시황", "잡지 3편", "영어 가이드"])
        night = dt.datetime(2026, 10, 6, 23, 30, tzinfo=daily_proof.KST)
        self.assertEqual(len(daily_proof.expected_artifacts(dt.date(2026, 10, 6), set(), root, night)), 8)
        self.assertEqual(len(daily_proof.expected_artifacts(dt.date(2026, 10, 6), set(), root, None)), 8)   # 다른 날짜 지정은 전부

    def test_skipped_or_noop_runs_are_not_success(self) -> None:
        """2026-10-06(감사 F-036·F-037): 건너뛴 예약 실행도 결론은 success다 — 본 작업이 실제로 돈 실행이 있어야 ok."""
        lo = dt.datetime(2026, 10, 6, 7, 0, tzinfo=dt.timezone.utc)
        job = {"workflow": "market_brief.yml", "window": (lo, lo + dt.timedelta(hours=3))}
        runs = [{"id": 1, "path": ".github/workflows/market_brief.yml", "created_at": "2026-10-06T07:20:00Z",
                 "conclusion": "success", "status": "completed"}]
        self.assertEqual(daily_proof.job_status(job, runs, real=lambda r: False), "건너뜀만")
        self.assertEqual(daily_proof.job_status(job, runs, real=lambda r: True), "ok")
        snap = {"close": {str(i): [1, 1] for i in range(2100)}}
        root = self._root(["data/price_kr_2026-10-06.json"])
        (root / "data" / "krx_close").mkdir(parents=True, exist_ok=True)
        (root / "data" / "krx_close" / "2026-10-06.json").write_text(json.dumps(snap), encoding="utf-8")
        got = {n: ok for n, ok, _ in daily_proof.expected_artifacts(dt.date(2026, 10, 6), set(), root)}
        self.assertTrue(got["한국장 시세"] and got["종가 사진"])

    def test_holiday_and_weekend(self) -> None:
        root = self._root([])
        names = [n for n, _, _ in daily_proof.expected_artifacts(dt.date(2026, 10, 9), set(), root)]   # 한글날(금)
        self.assertNotIn("한국장 시황", names)
        self.assertIn("미국장 프리뷰", names)
        sat = [n for n, _, _ in daily_proof.expected_artifacts(dt.date(2026, 10, 10), set(), root)]
        self.assertIn("주말 Checkpoint", sat); self.assertIn("주간 결산", sat); self.assertNotIn("한국장 시황", sat)
        sun = [n for n, _, _ in daily_proof.expected_artifacts(dt.date(2026, 10, 11), set(), root)]
        self.assertIn("다음 주 일정", sun); self.assertNotIn("미국장 시황", sun)
        mon = [n for n, _, _ in daily_proof.expected_artifacts(dt.date(2026, 10, 12), set(), root)]
        self.assertIn("주간 점검", mon)

    def test_us_holiday_expects_no_us_pieces(self) -> None:
        """추수감사절(11/26 목): 그날 밤 프리뷰도, 다음 날 아침 미국장 시세·시황도 기대하지 않는다."""
        root = self._root([])
        thu = [n for n, _, _ in daily_proof.expected_artifacts(dt.date(2026, 11, 26), set(), root)]
        self.assertNotIn("미국장 프리뷰", thu); self.assertIn("한국장 시황", thu)
        fri = [n for n, _, _ in daily_proof.expected_artifacts(dt.date(2026, 11, 27), set(), root)]
        self.assertFalse(any(n.startswith("미국장 시") for n in fri)); self.assertIn("미국장 프리뷰", fri)


class MacBeatsTest(unittest.TestCase):
    NOW = dt.datetime(2026, 10, 6, 23, 30, tzinfo=daily_proof.KST)

    def test_missing_or_stale_file_is_one_issue(self) -> None:
        issues, n, ok = daily_proof.mac_issues(None, self.NOW)
        self.assertEqual((len(issues), n, ok), (1, 1, 0))
        issues, _, _ = daily_proof.mac_issues({"generated_at": "2026-10-05T23:22:00+09:00", "beats": {}}, self.NOW)
        self.assertIn("오늘 것이 아닙니다", issues[0])

    def test_interval_and_daily_rules(self) -> None:
        beats = {"generated_at": "2026-10-06T23:22:00+09:00", "beats": {
            "naver_sync": "2026-10-06T23:10:00+09:00", "blogger_sync": "2026-10-06T21:00:00+09:00",
            "gsc_queries": "2026-10-06T10:35:00+09:00", "gsc_daily_index": "2026-10-05T15:12:00+09:00",
            "daily_summary": "2026-10-06T22:31:00+09:00", "bench_nightly": "2026-10-06T23:12:00+09:00"}}
        issues, n, ok = daily_proof.mac_issues(beats, self.NOW)
        self.assertEqual(n, 6)
        self.assertEqual(ok, 4)
        self.assertTrue(any(i.startswith("맥 blogger_sync") for i in issues))     # 30분 넘게 조용함
        self.assertTrue(any(i.startswith("맥 gsc_daily_index") for i in issues))  # 어제 신호

    def test_weekly_jobs_only_on_their_day(self) -> None:
        sunday = dt.datetime(2026, 10, 11, 23, 30, tzinfo=daily_proof.KST)
        beats = {"generated_at": "2026-10-11T23:22:00+09:00", "beats": {}}
        issues, n, _ = daily_proof.mac_issues(beats, sunday)
        self.assertEqual(n, 6 + 2)   # threads_refresh·search_snapshot
        self.assertTrue(any("threads_refresh" in i for i in issues))

    def test_uploader_counts_todays_posts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            naver = Path(tmp) / "posted.json"
            naver.write_text(json.dumps({"a": {"at": "2026-10-06T07:31:00"}, "b": {"at": "2026-10-05T19:31:00"}}), encoding="utf-8")
            blogger = Path(tmp) / "blogger_posted.json"
            blogger.write_text(json.dumps({"x": {"at": "2026-10-06T00:28:46"}}), encoding="utf-8")
            blocked = Path(tmp) / "blocked.json"
            blocked.write_text(json.dumps({"m": {"at": "2026-10-06T12:30:00", "why": "근거 없음"}}), encoding="utf-8")
            doc = mac_beats.build(dt.datetime(2026, 10, 6, 23, 22, tzinfo=daily_proof.KST), beats={"naver_sync": "t"}, naver=naver, blogger=blogger,
                                  naver_blocked=blocked, blogger_blocked=Path(tmp) / "none.json")
        self.assertEqual(doc["posted"], {"naver_today": 1, "blogger_today": 1, "naver_blocked_today": 1, "blogger_blocked_today": 0})
        self.assertEqual(doc["beats"], {"naver_sync": "t"})

    def test_state_file_is_tracked(self) -> None:
        self.assertIn("!state/mac_beats.json", (ROOT / ".gitignore").read_text(encoding="utf-8"))


class ScreenAndMessageTest(unittest.TestCase):
    def test_page_parse(self) -> None:
        html = '<div class="fs-price">₩1,841,000 <small>+8,000 ( +0.44% )</small></div><div class="fs-mute">At close: Oct 2, 2026 · KRW · Korea Exchange</div>'
        self.assertEqual(daily_proof.page_quote(html), (1841000.0, "2026-10-02"))
        self.assertEqual(daily_proof.page_quote("<p>nothing</p>"), (None, None))
        home = 'KOSPI · Oct 2 close</span><b>7,003.74</b>'
        self.assertEqual(daily_proof.home_kospi(home, 2026), ("2026-10-02", 7003.74))
        # 1월 초에 홈이 아직 지난해 12월 날짜면 지난해로 읽는다(감사 F-150)
        dec = home.replace("Oct 2", "Dec 30")
        self.assertEqual(daily_proof.home_kospi(dec, dt.date(2027, 1, 2))[0], "2026-12-30")

    def test_screen_issues_compare_page_with_daum(self) -> None:
        pages = {"/": 'KOSPI · Oct 2 close</span><b>7,003.74</b>',
                 "/stocks/000660/": '<div class="fs-price">₩1,841,000 <small></small></div>At close: Oct 2, 2026 ·',
                 "/stocks/207940/": '<div class="fs-price">₩1,366,000 <small></small></div>At close: Oct 2, 2026 ·'}
        session = mock.Mock()
        session.get.side_effect = lambda url, **kw: mock.Mock(status_code=200, text=pages[url.replace(daily_proof.BASE, "")])
        daum = {"000660": [("2026-10-02", 1841000.0)], "207940": [("2026-10-02", 1354000.0)]}
        with mock.patch.object(daily_proof.fetch_kr, "_fetch_naver_index_daily", return_value=[("2026-10-02", 7003.74)]), \
                mock.patch.object(daily_proof.fetch_kr, "_fetch_daum_days", side_effect=lambda c, rows=1: daum[c]):
            issues, n, _ok = daily_proof.screen_issues(session, ["000660", "207940"], dt.datetime(2026, 10, 2, 23, 30, tzinfo=daily_proof.KST))
        self.assertEqual(n, 3)
        self.assertEqual(len(issues), 1)
        self.assertIn("207940", issues[0])

    def test_compose(self) -> None:
        ok = daily_proof.compose(dt.date(2026, 10, 6), {"숫자": "2,800건", "작업": "9/9"}, [])
        self.assertTrue(ok.startswith("✅ 10/06 증명 — 숫자 2,800건 · 작업 9/9"))
        warn = daily_proof.compose(dt.date(2026, 10, 6), {"작업": "8/9"}, ["작업 stock_db.yml (17:05): 없음"])
        self.assertTrue(warn.startswith("⚠️ "))
        self.assertIn("- 작업 stock_db.yml", warn)
        self.assertLessEqual(len(daily_proof.compose(dt.date(2026, 10, 6), {}, ["x" * 500] * 20)), 3800)

    def test_source_tags(self) -> None:
        doc = {"watchlist": {"a": {"close_sources": ["daum", "naver_snapshot"]}, "b": {"close_sources": ["daum"]}},
               "macro": {"KS11": {"price": 1}}}
        self.assertEqual(daily_proof.source_tags(doc), (1, 2))
        self.assertEqual(daily_proof.source_tags(None), (0, 0))

    def test_sample_codes_are_six_digit_and_seeded(self) -> None:
        a = daily_proof.sample_codes(5, seed=1)
        self.assertEqual(a, daily_proof.sample_codes(5, seed=1))
        self.assertTrue(all(len(c) == 6 and c.isdigit() for c in a))


class WiringTest(unittest.TestCase):
    def test_worker_table_presses_and_watches_the_proof(self) -> None:
        jobs = json.loads((ROOT / "cloudflare/backup_cron/jobs.json").read_text(encoding="utf-8"))
        direct = [j for j in jobs["direct"] if j["workflow"] == "daily_proof.yml"]
        self.assertEqual(direct[0]["utc"], ["14:30"])
        watch = [j for j in jobs["watch"] if j["workflow"] == "daily_proof.yml"][0]
        self.assertTrue(watch["success"])
        self.assertIn("증명서가 오지 않았습니다", watch["alarm"])
        worker = (ROOT / "cloudflare/backup_cron/worker.js").read_text(encoding="utf-8")
        self.assertIn('run.conclusion === "success"', worker)
        self.assertIn("job.alarm ||", worker)

    def test_workflow_runs_daily_after_everything_else(self) -> None:
        text = (ROOT / ".github/workflows/daily_proof.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "30 14 * * 0-6"', text)
        self.assertIn("actions: read", text)


class CalendarTablesTest(unittest.TestCase):
    """해마다 사람이 채워야 하는 표 — 때가 되면 증명서가 매일 경고한다(2026-10-05)."""

    def test_reminders_come_at_the_right_time(self) -> None:
        c = lambda s: daily_proof.calendar_issues(dt.date.fromisoformat(s))   # noqa: E731
        self.assertEqual(c("2026-10-05"), [])
        self.assertTrue(any("수능일 장 시간" in x for x in c("2026-11-10")))
        self.assertTrue(any("2027년 휴장일(계산값)" in x for x in c("2026-12-01")))
        late = c("2027-12-02")
        self.assertTrue(any("2028년 휴장일이 stock_db" in x for x in late))
        self.assertTrue(any("뉴욕증시 2028년" in x for x in late))
        self.assertTrue(any("2027년 수능일이" in x for x in c("2027-07-01")))


class OwnerOverrideTest(unittest.TestCase):
    """막힌 날 사장님이 '내보내'라고 하면 — 지목한 원천 값에 꼬리표를 달아 내보낸다(KR_CLOSE_OVERRIDE)."""
    NAVER = {"nv": 286500, "cr": 3.62, "pcv": 276500}
    DAUM = {"date": "2026-10-06", "close": 286000.0, "base": 276500.0}

    def setUp(self) -> None:   # 셋째 원천(야후)도 가리지 못한 날 — 시험은 바깥에 접속하지 않는다
        patcher = mock.patch.object(fetch_kr, "yahoo_close", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_without_override_disagreement_stops(self) -> None:
        with mock.patch.dict(os.environ, {"KR_CLOSE_OVERRIDE": ""}):
            with self.assertRaises(ValueError):
                fetch_kr._resolve_krx_close("005930", "2026-10-06", self.NAVER, self.DAUM)

    def test_override_picks_the_named_source_and_tags_it(self) -> None:
        with mock.patch.dict(os.environ, {"KR_CLOSE_OVERRIDE": "naver_snapshot"}):
            out = fetch_kr._resolve_krx_close("005930", "2026-10-06", self.NAVER, self.DAUM)
        self.assertEqual(out["close"], 286500.0)
        self.assertEqual(out["sources"], ["naver_snapshot (owner override)"])
        with mock.patch.dict(os.environ, {"KR_CLOSE_OVERRIDE": "yahoo"}):     # 모르는 이름은 승인이 아니다
            with self.assertRaises(ValueError):
                fetch_kr._resolve_krx_close("005930", "2026-10-06", self.NAVER, self.DAUM)

    def test_workflow_passes_the_input_through(self) -> None:
        text = (ROOT / ".github/workflows/market_brief.yml").read_text(encoding="utf-8")
        self.assertIn("close_override:", text)
        self.assertIn("KR_CLOSE_OVERRIDE: ${{ github.event.inputs.close_override }}", text)


if __name__ == "__main__":
    unittest.main()


class WorkerHeartbeatTest(unittest.TestCase):
    """Cloudflare 워커가 멈추면 증명서도 함께 안 돈다 — 워커 밖의 맥이 하루 한 번 누른 실행 수를 센다(2026-10-06, 감사 F-037)."""

    def test_zero_presses_is_an_alarm(self) -> None:
        from scripts import mac_beats
        now = dt.datetime(2026, 10, 6, 23, 22, tzinfo=daily_proof.KST)
        self.assertIn("한 번도", mac_beats.check_worker(now, count=0))
        self.assertIsNone(mac_beats.check_worker(now, count=12))
        self.assertIn("세지 못했습니다", mac_beats.check_worker(now, count=None))


class RepeatedWarningTest(unittest.TestCase):
    """같은 경고가 이어지면 '🔁 N일째'를 붙여 맨 위로(2026-10-06, 감사 F-076)."""

    def test_streaks(self) -> None:
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "s.json"
            d1, d2 = dt.date(2026, 10, 6), dt.date(2026, 10, 7)
            issues1, st = daily_proof.mark_repeats(d1, ["글 없음: 미국장 프리뷰 (x)", "숫자 192건 중 3건 다름"], state)
            state.write_text(json.dumps(st), encoding="utf-8")
            issues2, _ = daily_proof.mark_repeats(d2, ["새 경고", "숫자 200건 중 4건 다름"], state)
        self.assertEqual(issues2[0], "🔁 2일째 · 숫자 200건 중 4건 다름")   # 숫자만 다른 같은 경고
        self.assertEqual(issues2[1], "새 경고")
