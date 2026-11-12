"""작업 결과를 공용 DB(atb_db)의 job_runs 표에 남긴다 (2026-11-12).

노트북 로그 파일은 다른 PC 에서 볼 수 없다. 작업이 끝날 때마다 한 줄씩 DB 에 적어 두면
어디서든 "실거래가 왜 실패했지?" 를 바로 조회할 수 있다:

    SELECT job, started_at, minutes, status, code FROM job_runs ORDER BY id DESC LIMIT 20;
    SELECT log_tail FROM job_runs WHERE job = 'trades' ORDER BY id DESC LIMIT 1;

  - 일일 작업(atb)은 성공·실패 모두 적는다. 당근(5분마다)은 실패만 적는다 (하루 288줄 방지)
  - 로그는 이번 실행분의 마지막 100줄만 — 실패 원인은 거의 끝에 있다. 전화번호는 가운데를 가린다
  - KEEP_DAYS 가 지난 줄은 하루 한 번 지운다
  - DB 에 못 적어도(터널 끊김 등) 작업에는 아무 영향이 없다 — 로그 파일은 그대로 남는다

atb/ 는 원본과 바이트 단위로 같게 두므로 이 파일은 실행기 쪽(최상위)에 둔다.
"""
from __future__ import annotations

import re
import threading
from datetime import date, datetime
from pathlib import Path

KEEP_DAYS = 30
TAIL_LINES = 100
TAIL_MAX_CHARS = 20_000

_DDL = """
CREATE TABLE IF NOT EXISTS job_runs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  job VARCHAR(30) NOT NULL COMMENT '작업 키 (trades·rents·kapt·dgn …)',
  label VARCHAR(50) NOT NULL,
  started_at DATETIME NOT NULL,
  ended_at DATETIME NOT NULL,
  minutes DECIMAL(7,1) NOT NULL,
  code INT NOT NULL COMMENT '종료 코드 (0 성공, 2 API 한도, 그 밖은 실패)',
  status VARCHAR(10) NOT NULL COMMENT 'ok · quota · timeout · fail',
  attempt TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '오늘 몇 번째 시도',
  host VARCHAR(60) NULL COMMENT '돌린 PC',
  log_tail MEDIUMTEXT NULL COMMENT '이번 실행 로그의 마지막 부분',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_job_runs_job (job, started_at),
  KEY idx_job_runs_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='dgn-atb 실행기 작업 결과 (노트북)'
"""

_lock = threading.Lock()
_table_ready = False
_last_prune: date | None = None

# 010-1234-5678 / 01012345678 → 010-****-5678
_PHONE = re.compile(r"(01[016789])[-\s.]?(\d{3,4})[-\s.]?(\d{4})")


def mask(text: str) -> str:
    return _PHONE.sub(lambda m: f"{m.group(1)}-****-{m.group(3)}", text)


def tail_of_run(log_path: Path, start_marker: str) -> str:
    """하루 로그 파일에서 이번 실행분(마지막 시작 표시 뒤)의 마지막 TAIL_LINES 줄."""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    i = text.rfind(start_marker)
    if i >= 0:
        text = text[i:]
    lines = text.splitlines()[-TAIL_LINES:]
    return mask("\n".join(lines))[-TAIL_MAX_CHARS:]


def status_of(code: int, timed_out: bool) -> str:
    if timed_out:
        return "timeout"
    if code == 0:
        return "ok"
    if code == 2:
        return "quota"
    return "fail"


def _connect(env: dict[str, str]):
    import pymysql  # 실행기는 이미 atb 때문에 들고 있다

    return pymysql.connect(
        host=env.get("MYSQL_HOST", "127.0.0.1"),
        port=int(env.get("MYSQL_PORT", "3306")),
        user=env.get("MYSQL_USER", ""),
        password=env.get("MYSQL_PASSWORD", ""),
        database=env.get("MYSQL_DATABASE", ""),
        charset="utf8mb4",
        connect_timeout=5,
        read_timeout=15,
        write_timeout=15,
        autocommit=True,
    )


def record(env: dict[str, str], *, job: str, label: str, started: datetime, ended: datetime,
           code: int, timed_out: bool, attempt: int, log_tail: str, host: str | None) -> str | None:
    """한 줄 적는다. 못 적으면 이유를 돌려준다 (실행기는 화면에만 알린다)."""
    global _table_ready, _last_prune
    if not env.get("MYSQL_USER"):
        return "atb/.env 에 MySQL 설정이 없음"
    try:
        with _lock:
            conn = _connect(env)
            try:
                with conn.cursor() as cur:
                    if not _table_ready:
                        cur.execute(_DDL)
                        _table_ready = True
                    cur.execute(
                        "INSERT INTO job_runs (job, label, started_at, ended_at, minutes, code, status, attempt, host, log_tail)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (job, label[:50], started.replace(microsecond=0), ended.replace(microsecond=0),
                         round((ended - started).total_seconds() / 60, 1), code, status_of(code, timed_out),
                         min(attempt, 255), (host or "")[:60] or None, log_tail or None),
                    )
                    # 오래된 줄 지우기 — 하루 한 번
                    if _last_prune != date.today():
                        cur.execute("DELETE FROM job_runs WHERE created_at < NOW() - INTERVAL %s DAY", (KEEP_DAYS,))
                        _last_prune = date.today()
            finally:
                conn.close()
        return None
    except Exception as e:  # noqa: BLE001 — 기록 실패가 작업을 막으면 안 된다
        return str(e)[:200]
