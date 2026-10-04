"""통합 실행기의 작업 목록과 스케줄 엔진.

노트북 한 대에서 두 프로그램을 하나의 프로세스로 돌린다.
  - dgn/ : 당근광고 스프레드시트 → 각 사이트 서버 (5분마다)      ← 원본 ../dgn_scrap/daagn
  - atb/ : 부동산 공공데이터 → 공용 DB (하루 1번씩, 시각 지정)   ← 원본 ../atb-program 의 수집 CLI
원본 두 폴더는 건드리지 않고, 필요한 파일만 복사해 와서 독립적으로 돈다.

각 작업은 자식 프로세스로 실행한다 — 실행기가 자기 자신을 `--job <키>` 로 다시 띄운다
(worker.py). exe 로 묶어도 파이썬 없이 돌고, K-apt 처럼 몇 시간 걸리는 작업이
당근 전송을 막지 않으며, 한 작업이 죽어도 실행기는 살아 있다.
atb 작업끼리는 DB·API 한도를 나눠 쓰므로 한 번에 하나씩만 돈다.

노트북이 예약 시각에 꺼져 있었으면 켜진 뒤 바로 따라잡는다
(오늘 아직 안 돌았고 예약 시각이 지났으면 실행).

로그: logs/<작업>-YYYYMMDD.log (30일 지난 것은 지운다)
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

# exe 로 묶였으면 exe 옆 폴더가 기준 (.env·토큰·로그를 exe 밖에 둔다)
FROZEN = getattr(sys, "frozen", False)
ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
DGN_DIR = ROOT / "dgn"
ATB_DIR = ROOT / "atb"
LOG_DIR = ROOT / "logs"
STATE_FILE = LOG_DIR / "state.json"

KEEP_LOGS = timedelta(days=30)
TICK_SEC = 20
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

# 일일 작업 실패 시 재시도. 0(성공)·2(API 일일 한도 초과 — 다시 해봐야 소용없음)는 오늘 끝으로 본다.
DONE_CODES = {0, 2}
RETRY_AFTER = timedelta(hours=1)
MAX_TRIES = 3


def _recent_months() -> str:
    """지난달~이번달 'YYYYMM-YYYYMM'. 실거래 신고는 계약 후 30일 이내라 지난달도 계속 채워진다."""
    today = date.today()
    prev = (today.replace(day=1) - timedelta(days=1))
    return f"{prev:%Y%m}-{today:%Y%m}"


@dataclass
class Job:
    key: str
    label: str
    group: str                        # "dgn" | "atb" — 같은 그룹은 동시에 하나만
    args: Callable[[], list[str]]     # 스크립트 main(argv) 인자. 실행 시점에 만든다 (날짜 의존)
    every_min: int | None = None      # 주기 실행
    daily_at: str | None = None       # "HH:MM" 매일 실행
    timeout_min: int | None = None

    # 실행 상태 (GUI 표시용)
    running: bool = False
    last_start: datetime | None = None
    last_end: datetime | None = None
    last_code: int | None = None
    queued: bool = field(default=False)

    @property
    def schedule_text(self) -> str:
        return f"{self.every_min}분마다" if self.every_min else f"매일 {self.daily_at}"


JOBS: list[Job] = [
    Job("dgn", "당근광고 시트 → 서버", "dgn",
        lambda: [], every_min=5, timeout_min=10),
    # 실거래 → 좌표 → 분양 → K-apt(매칭) 순. 새로 생긴 단지가 같은 날 좌표·매칭까지 이어진다.
    #
    # timeout_min 은 반드시 둔다. atb 는 한 번에 하나만 도는데, 한 작업이 네트워크에서
    # 멈추면 proc.wait() 가 영구히 기다리고 그룹이 계속 '사용 중' 으로 남아 나머지 세
    # 작업도 그날부터 전부 멈춘다. 화면에는 '실행 중…' 만 떠 있어 알아채기 어렵다.
    # 실제 소요의 2~3배로 넉넉히 두되, 다음 날 03:00 전에는 끝나게 한다.
    Job("trades", "아파트 실거래가", "atb",
        lambda: ["--all", _recent_months()], daily_at="03:00", timeout_min=240),
    Job("geocode", "단지 좌표 변환", "atb",
        lambda: ["--delay", "0.3"], daily_at="04:00", timeout_min=180),
    Job("presale", "청약홈 분양공고", "atb",
        lambda: ["--recent"], daily_at="06:00", timeout_min=120),
    # K-apt 포털이 새벽엔 전부 HTTP_ERROR 를 돌려줘서 낮에 돌린다.
    # 30일 캐시가 만료되는 날은 전국을 다시 받아 몇 시간이 걸린다 — 7시간을 준다.
    Job("kapt", "K-apt 단지 동기화", "atb",
        lambda: ["--all"], daily_at="09:00", timeout_min=420),
]


def _read_env(path: Path) -> dict[str, str]:
    """atb/config.py 와 같은 규칙의 단순 .env 파서."""
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        data[key.strip()] = val.strip().strip('"').strip("'")
    return data


def _port_open(port: int) -> bool:
    import socket
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _listening_pids(port: int) -> set[str]:
    """127.0.0.1:port 를 LISTEN 중인 프로세스 PID."""
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True,
                             creationflags=_no_window()).stdout
    except OSError:
        return set()
    pids = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "TCP" and parts[3] == "LISTENING" \
                and parts[1].endswith(f":{port}"):
            pids.add(parts[4])
    return pids


def _kill_stale_ssh(port: int) -> bool:
    """포트를 쥔 ssh 를 끈다. 하나라도 껐으면 True.

    실행기를 작업관리자로 끄거나 전원이 나가면 stop() 이 못 돌아 자식 ssh 가 남는다.
    ssh.exe 일 때만 끈다 — 남의 프로세스는 건드리지 않는다.
    """
    killed = False
    for pid in _listening_pids(port):
        try:
            info = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                                  capture_output=True, text=True, creationflags=_no_window()).stdout
        except OSError:
            continue
        if "ssh.exe" not in info.lower():
            continue
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True,
                       creationflags=_no_window())
        killed = True
    return killed


class SshTunnel:
    """공용 DB 로 가는 SSH 포트 포워딩. atb/.env 에 SSH_HOST 가 있을 때만 쓴다.

    DB 서버는 3306 을 앱 서버 IP 에만 열어두므로, IP 가 바뀌는 노트북은
    열려 있는 22 로 터널을 뚫고 127.0.0.1:SSH_LOCAL_PORT 로 MySQL 에 붙는다.
    """

    def __init__(self, env: dict[str, str]):
        self.host = env.get("SSH_HOST", "")
        self.user = env.get("SSH_USER", "root")
        self.key = env.get("SSH_KEY", "")
        self.local_port = int(env.get("SSH_LOCAL_PORT", "3307"))
        self.proc: subprocess.Popen | None = None
        self._err = None

    @property
    def enabled(self) -> bool:
        return bool(self.host)

    def _log(self, msg: str):
        LOG_DIR.mkdir(exist_ok=True)
        with open(LOG_DIR / "ssh-tunnel.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")

    def _reclaim_port(self) -> bool:
        """앞선 실행이 남긴 ssh 가 쥔 포트를 되찾는다. 비었으면 True.

        정리하지 않으면 ExitOnForwardFailure 로 새 터널이 바로 죽고, ensure() 는
        포트가 열려 있는데도 계속 False 를 돌려준다 — 수집이 영구히 멈춘다.
        """
        if not _kill_stale_ssh(self.local_port):
            self._log(f"127.0.0.1:{self.local_port} 를 ssh 아닌 프로그램이 쓰고 있다 — 터널 불가")
            return False
        end = time.time() + 5
        while time.time() < end:
            if not _port_open(self.local_port):
                self._log("앞선 실행이 남긴 ssh 를 정리했다")
                return True
            time.sleep(0.3)
        self._log("ssh 를 끝냈지만 포트가 아직 열려 있다")
        return False

    def ensure(self, timeout: float = 15) -> bool:
        """터널이 살아 있으면 True. 죽어 있으면 다시 띄우고 포트가 열릴 때까지 기다린다."""
        if not self.enabled:
            return True
        if self.proc and self.proc.poll() is None and _port_open(self.local_port):
            return True
        self.close()
        # 내 자식이 아닌데 포트가 열려 있다 = 앞선 실행이 남긴 ssh
        if _port_open(self.local_port) and not self._reclaim_port():
            return False
        cmd = ["ssh", "-N", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
               "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
               "-o", "StrictHostKeyChecking=accept-new",
               "-L", f"127.0.0.1:{self.local_port}:127.0.0.1:3306"]
        if self.key:
            cmd += ["-i", self.key]
        cmd.append(f"{self.user}@{self.host}")
        LOG_DIR.mkdir(exist_ok=True)
        self._err = open(LOG_DIR / "ssh-tunnel.log", "a", encoding="utf-8")
        self._err.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} 터널 연결 =====\n")
        self._err.flush()
        self.proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=self._err, stderr=self._err,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        end = time.time() + timeout
        while time.time() < end:
            if self.proc.poll() is not None:
                return False            # 인증 실패·포트 충돌 등 — logs/ssh-tunnel.log
            if _port_open(self.local_port):
                return True
            time.sleep(0.5)
        return False

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
            try:
                self.proc.wait(timeout=5)   # 포트가 풀린 뒤에 다시 띄우도록
            except subprocess.TimeoutExpired:
                pass
        self.proc = None
        if self._err:
            self._err.close()
            self._err = None


def _worker_cmd(job: Job, log_path: Path) -> list[str]:
    """작업을 돌릴 자식 프로세스 명령 — 실행기 자신을 `--job` 모드로 다시 띄운다."""
    tail = ["--job", job.key, "--log", str(log_path), "--", *job.args()]
    if FROZEN:
        return [sys.executable, *tail]
    # 개발 중: `python main.py` 처럼 시스템 파이썬으로 띄워도 패키지가 있는 venv 로 돌린다
    py = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)
    if py.name.lower() == "pythonw.exe":
        py = py.with_name("python.exe")
    return [str(py), str(ROOT / "main.py"), *tail]

class Scheduler:
    def __init__(self, on_event: Callable[[str], None] = print):
        self.jobs = {j.key: j for j in JOBS}
        self.on_event = on_event
        self._lock = threading.Lock()
        self._busy_groups: set[str] = set()
        self._procs: dict[str, subprocess.Popen] = {}
        self._stop = threading.Event()
        LOG_DIR.mkdir(exist_ok=True)
        self._state = self._load_state()
        self.tunnel = SshTunnel(_read_env(ATB_DIR / ".env"))
        self._tunnel_lock = threading.Lock()
        self._tunnel_ok: bool | None = None
        self._tunnel_retry_at = 0.0
        self._retry_at: dict[str, datetime] = {}
        self._tries: dict[str, tuple[date, int]] = {}

    # ─── 상태 파일: 일일 작업이 오늘 이미 돌았는지 ─────────────────────────
    def _load_state(self) -> dict:
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_state(self):
        STATE_FILE.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")

    def last_daily_run(self, key: str) -> str | None:
        return self._state.get(key)

    # ─── 스케줄 판정 ──────────────────────────────────────────────────────
    def _due(self, job: Job, now: datetime) -> bool:
        if job.every_min:
            return job.last_start is None or now - job.last_start >= timedelta(minutes=job.every_min)
        hh, mm = map(int, job.daily_at.split(":"))
        return now >= now.replace(hour=hh, minute=mm, second=0, microsecond=0) \
            and self._state.get(job.key) != now.date().isoformat() \
            and now >= self._retry_at.get(job.key, datetime.min)

    def tick(self):
        now = datetime.now()
        # 목록 순서대로 — atb 가 여러 개 밀려 있으면 위에 있는 것부터
        for job in self.jobs.values():
            if job.running:
                continue
            if job.queued or self._due(job, now):
                # atb 는 DB 터널이 붙어야 시작한다. 안 붙으면 시작 기록 없이 넘겨서 다음 tick 에 다시 본다
                if job.group == "atb" and "atb" not in self._busy_groups and not self._db_ready():
                    continue
                self._try_start(job)

    def _db_ready(self) -> bool:
        if not self.tunnel.enabled:
            return True
        with self._tunnel_lock:
            if self._tunnel_ok is False and time.time() < self._tunnel_retry_at:
                return False
            ok = self.tunnel.ensure()
            if ok != self._tunnel_ok:   # 상태가 바뀔 때만 알린다 (끊긴 동안 1분마다 도배 방지)
                self.on_event("DB 터널 연결됨" if ok else
                              "DB 터널 연결 실패 — 1분마다 재시도 (logs/ssh-tunnel.log)")
            self._tunnel_ok = ok
            self._tunnel_retry_at = time.time() + 60
            return ok

    def run_now(self, key: str):
        job = self.jobs[key]
        if job.running:
            return
        job.queued = True
        # 터널 연결이 최대 15초 걸릴 수 있어 GUI 스레드를 막지 않도록 따로 돌린다
        threading.Thread(target=self.tick, daemon=True).start()

    def _try_start(self, job: Job):
        with self._lock:
            if job.running:   # 다른 스레드가 먼저 시작함
                return
            if job.group in self._busy_groups:
                if not job.queued:
                    job.queued = True
                    self.on_event(f"{job.label}: 같은 그룹 작업이 도는 중이라 대기")
                return
            self._busy_groups.add(job.group)
            job.running = True
            job.queued = False
            job.last_start = datetime.now()
            if job.daily_at:
                # 시작 시점에 기록 — 도는 중에 실행기가 꺼져도 다시 켤 때 중복으로 돌지 않게.
                # 실패하면 _after_daily 가 기록을 지우고 재시도를 잡는다.
                self._state[job.key] = job.last_start.date().isoformat()
                day, n = self._tries.get(job.key, (None, 0))
                self._tries[job.key] = (job.last_start.date(), n + 1 if day == job.last_start.date() else 1)
                self._save_state()
        threading.Thread(target=self._run, args=(job,), daemon=True).start()

    # ─── 실행 ─────────────────────────────────────────────────────────────
    def _run(self, job: Job):
        log_path = LOG_DIR / f"{job.key}-{datetime.now():%Y%m%d}.log"
        self.on_event(f"{job.label} 시작")
        code = -1
        try:
            def mark(line: str):
                with open(log_path, "a", encoding="utf-8") as log:
                    log.write(line)

            mark(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} {job.key} 시작 =====\n")
            # 출력은 자식이 로그 파일에 직접 쓴다 (창 없는 exe 는 표준출력이 없어서 파이프로 못 받는다)
            proc = subprocess.Popen(
                _worker_cmd(job, log_path), cwd=ROOT,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._procs[job.key] = proc
            try:
                code = proc.wait(timeout=job.timeout_min * 60 if job.timeout_min else None)
            except subprocess.TimeoutExpired:
                proc.kill()
                code = proc.wait()
                mark(f"!!!!! {job.timeout_min}분 초과로 강제 종료 !!!!!\n")
            mark(f"===== {datetime.now():%Y-%m-%d %H:%M:%S} {job.key} 종료 (코드 {code}) =====\n")
        except Exception as e:
            self.on_event(f"{job.label} 실행 오류: {e}")
        finally:
            self._procs.pop(job.key, None)
            job.running = False
            job.last_end = datetime.now()
            job.last_code = code
            with self._lock:
                self._busy_groups.discard(job.group)
                if job.daily_at:
                    self._after_daily(job, code)
            self.on_event(f"{job.label} 종료 (코드 {code})")
            if not self._stop.is_set():
                try:
                    self.tick()   # 대기 중인 같은 그룹 작업을 다음 주기까지 기다리지 않고 바로 시작
                except Exception as e:
                    self.on_event(f"스케줄러 오류: {e}")

    def _after_daily(self, job: Job, code: int):
        """일일 작업이 실패하면(한도 초과 제외) 오늘 기록을 지우고 1시간 뒤 재시도. 하루 MAX_TRIES 번까지."""
        if code in DONE_CODES or self._stop.is_set():
            return
        _, tries = self._tries.get(job.key, (None, 0))
        if tries >= MAX_TRIES:
            self.on_event(f"{job.label}: 오늘 {tries}번 실패 — 내일 다시 돕니다")
            return
        self._state.pop(job.key, None)
        self._save_state()
        self._retry_at[job.key] = datetime.now() + RETRY_AFTER
        self.on_event(f"{job.label}: 실패 — {self._retry_at[job.key]:%H:%M} 에 다시 시도 ({tries}/{MAX_TRIES})")

    # ─── 루프 ─────────────────────────────────────────────────────────────
    def start(self):
        self._prune_logs()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        last_prune = date.today()
        while not self._stop.is_set():
            try:
                self.tick()
                if date.today() != last_prune:
                    self._prune_logs()
                    last_prune = date.today()
            except Exception as e:
                self.on_event(f"스케줄러 오류: {e}")
            self._stop.wait(TICK_SEC)

    def stop(self):
        """실행기를 끌 때 돌던 자식 프로세스도 같이 끈다."""
        self._stop.set()
        for proc in list(self._procs.values()):
            try:
                proc.kill()
            except OSError:
                pass
        self.tunnel.close()

    def _prune_logs(self):
        cutoff = time.time() - KEEP_LOGS.total_seconds()
        for f in LOG_DIR.glob("*.log"):
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)


def preflight() -> list[str]:
    """실행 전에 빠진 설정을 알려준다 (실행은 막지 않음)."""
    warns = []
    env = _read_env(ATB_DIR / ".env")
    if not env:
        warns.append("atb/.env 없음 — 부동산 수집이 DB 에 접속하지 못합니다 (.env.example 참고)")
    elif env.get("SSH_HOST") and env.get("MYSQL_HOST") not in ("127.0.0.1", "localhost"):
        warns.append("SSH 터널을 쓰는데 MYSQL_HOST 가 127.0.0.1 이 아닙니다 — "
                     "MYSQL_HOST=127.0.0.1, MYSQL_PORT=SSH_LOCAL_PORT 로 맞춰야 터널을 탑니다")
    elif env.get("MYSQL_USER") == "root":
        warns.append("MYSQL_USER 가 root 입니다 — 공용 DB 의 root 는 서버 안에서만 접속되니 atb 전용 계정을 쓰세요")
    for name in ("token-top.json", "token-rich.json", "token-with.json"):
        if not (DGN_DIR / name).exists():
            warns.append(f"dgn/{name} 없음 — 해당 계정은 처음 실행 때 브라우저 로그인이 뜹니다")
    # 예전 방식(작업 스케줄러)이 남아 있으면 같은 작업이 두 번 돈다
    r = subprocess.run(["schtasks", "/Query", "/TN", r"AllThat\KaptSync"], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode == 0:
        warns.append("작업 스케줄러에 AllThat 작업이 등록돼 있습니다 — "
                     "원본 atb-program/scheduler/unregister_tasks.bat 로 지워야 중복 실행이 안 됩니다")
    return warns
