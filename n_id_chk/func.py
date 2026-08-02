"""공용 기능 모음 (DB / ADB / Playwright 헬퍼).

작업 흐름은 workspace.py 에 있고, 여기에는 재사용 가능한 도구 함수만 둔다.
"""

import os
import random
import shutil
import subprocess
import time
import urllib.request

import pymysql
from dotenv import load_dotenv

load_dotenv()


# ==========================================================================
# ADB (연결된 휴대폰 제어)
# ==========================================================================

# adb 실행 파일 경로 (PATH 에 있으면 그걸, 없으면 기본 설치 경로)
ADB = shutil.which("adb") or r"C:\platform-tools\adb.exe"


def _adb(*args, serial=None, timeout=20):
    """adb 명령 실행 후 (returncode, stdout, stderr) 반환."""
    cmd = [ADB]
    if serial:
        cmd += ["-s", serial]
    cmd += [str(a) for a in args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return -1, "", f"adb 를 찾을 수 없습니다: {ADB}"
    except subprocess.TimeoutExpired:
        return -1, "", "adb 명령 시간 초과"


def adb_devices():
    """연결되어 있고 'device' 상태인 시리얼 목록."""
    _, out, _ = _adb("devices")
    devices = []
    for line in out.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) == 2 and parts[1].strip() == "device":
            devices.append(parts[0].strip())
    return devices


def airplane_mode(on, serial=None, log=print):
    """비행기모드 켜기(on=True)/끄기(on=False).

    최신 방식(cmd connectivity)을 먼저 쓰고, 안 되면 settings+broadcast 로 폴백.
    폴백은 기기에 따라 root/권한이 필요할 수 있음.
    """
    state = "enable" if on else "disable"
    rc, out, err = _adb("shell", "cmd", "connectivity", "airplane-mode", state,
                        serial=serial)
    combined = (out + err).lower()
    if rc == 0 and "error" not in combined and "exception" not in combined \
            and "unknown" not in combined:
        return True

    # 폴백: 전역 설정 변경 + 브로드캐스트
    val = "1" if on else "0"
    _adb("shell", "settings", "put", "global", "airplane_mode_on", val, serial=serial)
    b = "true" if on else "false"
    rc2, _, err2 = _adb("shell", "am", "broadcast",
                        "-a", "android.intent.action.AIRPLANE_MODE",
                        "--ez", "state", b, serial=serial)
    if rc2 != 0:
        log(f"  [경고] 비행기모드 변경 실패 가능: {err or err2}")
    return rc2 == 0


def airplane_mode_cycle(off_seconds=3, serial=None, log=print):
    """비행기모드를 켰다가 끈다 → 모바일 IP 재할당(인터넷 재연결) 목적."""
    if not serial:
        devs = adb_devices()
        if not devs:
            log("연결된 휴대폰이 없습니다. (adb devices 확인)")
            return False
        serial = devs[0]
    log(f"대상 기기: {serial}")

    log("비행기모드 ON (인터넷 차단)...")
    airplane_mode(True, serial, log)
    time.sleep(off_seconds)

    log("비행기모드 OFF (재연결)...")
    airplane_mode(False, serial, log)
    time.sleep(off_seconds)

    log("비행기모드 토글 완료.")
    return True


def get_public_ip(timeout=5):
    """외부에서 보이는 공인 IP 조회 (여러 서비스 폴백)."""
    urls = (
        "https://api.ipify.org",
        "https://ipv4.icanhazip.com",
        "https://ifconfig.me/ip",
    )
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                ip = r.read().decode().strip()
                if ip:
                    return ip
        except Exception:
            continue
    return None


def rotate_ip(serial=None, off_seconds=3, log=print):
    """비행기모드 토글로 IP 변경 + 변경 여부 확인.

    반환 dict: {changed, before, after, no_device}
    - changed  : 변경 전/후 공인 IP 가 실제로 달라졌는지
    - no_device: 연결된 휴대폰이 없어 수행 못함
    """
    if not serial:
        devs = adb_devices()
        if not devs:
            log("연결된 휴대폰이 없습니다. (adb devices)")
            return {"changed": False, "before": None, "after": None, "no_device": True}
        serial = devs[0]

    before = get_public_ip()
    log(f"변경 전 IP: {before}")

    log("비행기모드 ON...")
    airplane_mode(True, serial, log)
    time.sleep(off_seconds)
    log("비행기모드 OFF (재연결 대기)...")
    airplane_mode(False, serial, log)
    time.sleep(off_seconds)

    # 테더링 재연결이 늦을 수 있어 몇 번 재시도하며 확인
    after = None
    for _ in range(6):
        after = get_public_ip()
        if after:
            break
        time.sleep(2)
    log(f"변경 후 IP: {after}")

    changed = bool(before and after and before != after)
    return {"changed": changed, "before": before, "after": after, "no_device": False}


# ==========================================================================
# DB
# ==========================================================================

def connect_db(retries=4, delay=2.0):
    """.env 설정으로 MySQL 접속. IP 변경 직후 재연결을 위해 재시도 포함."""
    last = None
    for _ in range(retries):
        try:
            return pymysql.connect(
                host=os.getenv("DB_HOST"),
                port=int(os.getenv("DBPORT", "3306")),
                user=os.getenv("DB_USER"),
                password=os.getenv("DBPWD"),
                database=os.getenv("DB_SCHEMA"),
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10,
            )
        except pymysql.MySQLError as e:
            last = e
            time.sleep(delay)
    raise last


def fetch_login_targets(before):
    """로그인 체크 대상 조회.

    - last_login_chk 가 비어있거나(첫 기록)
    - before 시각보다 오래된 계정만
    (사용 가능 use_status=1 인 것 대상)
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT n_idx, n_id, n_pwd FROM nwork "
                "WHERE use_status=1 AND (last_login_chk IS NULL "
                "   OR last_login_chk < %s) "
                "ORDER BY n_idx",
                (before,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def fetch_user_agents():
    """사용중인 user_agent 목록(문자열 리스트)."""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT ua_content FROM user_agent WHERE ua_use=1")
            return [r["ua_content"] for r in cur.fetchall()]
    finally:
        conn.close()


def update_login_result(n_idx, success):
    """성공 → last_login_chk=NOW(). 실패 → use_status=0(비활성). (자체 연결)"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            if success:
                cur.execute(
                    "UPDATE nwork SET last_login_chk=NOW() WHERE n_idx=%s",
                    (n_idx,),
                )
            else:
                cur.execute(
                    "UPDATE nwork SET use_status=0 WHERE n_idx=%s",
                    (n_idx,),
                )
        conn.commit()
    finally:
        conn.close()


# ==========================================================================
# Playwright 헬퍼
# ==========================================================================

def human_delay(log=None, lo=1.0, hi=3.0):
    """사람처럼 1~3초(기본) 랜덤 대기."""
    sec = random.uniform(lo, hi)
    if log:
        log(f"  ...{sec:.1f}초 대기")
    time.sleep(sec)
    return sec


def paste_into(page, selector, value):
    """클립보드에 값을 넣고 해당 필드에 포커스 후 Ctrl+V 로 붙여넣는다."""
    page.evaluate("(t) => navigator.clipboard.writeText(t)", value)
    field = page.locator(selector)
    field.click()          # 포커스
    field.fill("")         # 기존 내용 비우기
    page.keyboard.press("Control+V")


def click_login(page):
    """반응형 레이아웃에서 보이는 로그인 버튼을 클릭."""
    for sel in ("#loginBtn_row", "#loginBtn_column"):
        loc = page.locator(sel)
        if loc.count() and loc.first.is_visible():
            loc.first.click()
            return sel
    # 폴백: 텍스트로 찾기
    page.get_by_role("button", name="로그인").first.click()
    return "role=button[name=로그인]"
