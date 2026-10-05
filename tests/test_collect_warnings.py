"""수집 경고·엔진 실패를 모아 운영 대화로(2026-10-06, 감사 F-012·F-064) — 보내기는 가짜로."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import collect_warnings as cw


class CollectWarningsTest(unittest.TestCase):
    def test_warnings_and_engine_failures_are_sent_once(self) -> None:
        log = "[1/4] kr 시세 수집 중...\n[경고] KOSPI: 일봉이 9/17에 머물러\n[경고] KOSPI: 일봉이 9/17에 머물러\n[안내] 그냥 안내\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data" / "engines_kr_2026-10-06.txt").write_text("[업종] [error] 업종 행을 하나도 읽지 못했습니다\n정상 줄\n",
                                                                     encoding="utf-8")
            (root / "fetch.log").write_text(log, encoding="utf-8")
            with mock.patch.object(cw, "ROOT", root), mock.patch("src.alert.send", return_value=True) as sent, \
                    mock.patch("builtins.print"):
                self.assertEqual(cw.main([str(root / "fetch.log"), "kr"]), 0)
        text = sent.call_args[0][0]
        self.assertEqual(text.count("일봉이 9/17에 머물러"), 1)
        self.assertIn("재료 엔진 실패 1줄", text)
        self.assertNotIn("그냥 안내", text)

    def test_nothing_to_send(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "fetch.log").write_text("[안내] 조용한 날\n", encoding="utf-8")
            with mock.patch.object(cw, "ROOT", root), mock.patch("src.alert.send") as sent, mock.patch("builtins.print"):
                self.assertEqual(cw.main([str(root / "fetch.log"), "us"]), 0)
        sent.assert_not_called()


if __name__ == "__main__":
    unittest.main()
