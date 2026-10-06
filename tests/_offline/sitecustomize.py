"""시험은 바깥에 접속하지 않는다(2026-10-06) — tests.yml이 PYTHONPATH에 이 폴더를 넣어 켠다.

시험이 실제 원천(야후·다음·나스닥 등)에 몰래 접속해 통과하면, 원천 응답에 기대는 결함을 시험이 가린다(10/6: 다음 장애 시험과
거래정지 시험이 실제 야후 값으로 통과하고 있었다). 이 맥(localhost)만 허용한다.
"""
import socket

_real_connect = socket.socket.connect


def _guarded_connect(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if isinstance(host, str) and (host.startswith("127.") or host in ("localhost", "::1") or host.startswith("/")):
        return _real_connect(self, address)
    raise OSError(f"시험 중 바깥 접속 금지: {address} — 가짜 응답(mock)으로 바꾸십시오")


socket.socket.connect = _guarded_connect

# 텔레그램 '보낸 기록'(notify_telegram.SENT_LEDGER)을 시험이 이 맥의 실제 기록에 쓰지 않게 — 실행마다 새 임시 파일
import os as _os
import tempfile as _tempfile

_os.environ.setdefault("TELEGRAM_SENT_LEDGER", _os.path.join(_tempfile.mkdtemp(prefix="tg_sent_"), "sent.json"))
