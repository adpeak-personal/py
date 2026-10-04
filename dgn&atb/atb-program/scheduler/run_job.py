"""예약 작업 실행기.

Windows 작업 스케줄러(register_tasks.bat)나 리눅스 cron 이 이 파일을 부른다.
등록은 PC 마다 따로지만, 실제로 무엇을 어떻게 돌리는지는 전부 여기 있어서
다른 PC·서버로 옮겨도 등록만 다시 하면 똑같이 돈다.

    python scheduler/run_job.py kapt      # 전국 K-apt (한도 걸리면 다음날 이어서)
    python scheduler/run_job.py geocode   # 좌표 없는 단지 채우기 + 오류 건 재시도
    python scheduler/run_job.py presale   # 청약홈 최신 공고

- 로그: atb-program/logs/<작업>-YYYYMMDD.log (30일 지난 것은 지운다)
- 겹침 방지: 같은 작업이 아직 돌고 있으면 새로 시작하지 않는다
  (전날 K-apt 가 길어져 다음 예약 시각을 넘기는 경우 등)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # atb-program
LOG_DIR = ROOT / "logs"

JOBS: dict[str, list[str]] = {
    "kapt": ["run_kapt.py", "--all"],
    "geocode": ["run_geocode.py", "--delay", "0.3"],
    "presale": ["run_presale.py", "--recent"],
}

# 이보다 오래된 잠금 파일은 비정상 종료의 흔적으로 보고 무시한다
LOCK_STALE = timedelta(hours=20)
KEEP_LOGS = timedelta(days=30)


def _python() -> str:
    """pythonw.exe 로 불려도 자식은 콘솔용 python.exe 로 돌린다(출력 캡처가 되도록)."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        cand = exe.with_name("python.exe")
        if cand.exists():
            return str(cand)
    return str(exe)


def _acquire(name: str) -> Path | None:
    lock = LOG_DIR / f"{name}.lock"
    if lock.exists():
        age = datetime.now() - datetime.fromtimestamp(lock.stat().st_mtime)
        if age < LOCK_STALE:
            return None
        lock.unlink(missing_ok=True)
    lock.write_text(str(os.getpid()), encoding="utf-8")
    return lock


def _prune_logs():
    cutoff = time.time() - KEEP_LOGS.total_seconds()
    for f in LOG_DIR.glob("*.log"):
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in JOBS:
        print(f"사용: run_job.py {{{'|'.join(JOBS)}}}")
        return 1
    name = argv[0]
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"{name}-{datetime.now():%Y%m%d}.log"

    with open(log_path, "a", encoding="utf-8") as log:
        stamp = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
        lock = _acquire(name)
        if lock is None:
            log.write(f"\n===== {stamp} {name} — 이전 실행이 아직 도는 중이라 건너뜀 =====\n")
            return 0
        try:
            log.write(f"\n===== {stamp} {name} 시작 =====\n")
            log.flush()
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)   # 새벽에 콘솔 창이 뜨지 않게
            rc = subprocess.call([_python(), *JOBS[name]], cwd=ROOT, env=env,
                                 stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
            log.write(f"===== {datetime.now():%Y-%m-%d %H:%M:%S} {name} 종료 (코드 {rc}) =====\n")
            return rc
        finally:
            lock.unlink(missing_ok=True)
            _prune_logs()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
