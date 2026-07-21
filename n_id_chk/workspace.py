"""배치 작업: 테이블의 모든(대상) 아이디를 IP 변경하며 로그인 체크 후 기록.

흐름:
    DB에서 대상 목록 뽑기
    → (반복) IP 변경 → 로그인 → 성공여부 DB 저장

재사용 도구(DB/ADB/Playwright)는 func.py 에 있다.
로그는 log() 로 출력하며 기본은 print(터미널).
"""

import random

import pyautogui as pg
from playwright.sync_api import sync_playwright

import func



# --- 설정 ------------------------------------------------------------------

NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"
SUCCESS_SELECTOR = "#MM_SEARCH_FAKE"   # 로그인 성공 후 네이버 메인에 나타나는 요소
DEFAULT_DAYS = 30
HEADLESS = False                       # True 로 바꾸면 창 없이 실행
LOGIN_TIMEOUT_MS = 15000               # 성공 요소 대기 시간


# --- 계정 1건 로그인 체크 --------------------------------------------------

def _login_and_check(p, acc, ua, log):
    """크롬 하나 띄워 로그인 시도 → 성공여부(bool) 반환."""
    browser = p.chromium.launch(
        headless=HEADLESS,
        args=["--disable-blink-features=AutomationControlled"],
    )
    try:
        context = browser.new_context(user_agent=ua)   # 쿠키 없는 격리 세션
        context.grant_permissions(
            ["clipboard-read", "clipboard-write"],
            origin="https://nid.naver.com",
        )
        page = context.new_page()

        page.goto(NAVER_LOGIN_URL, wait_until="domcontentloaded")

        # 입력 전마다 1~3초 딜레이 + Ctrl+V 붙여넣기
        func.human_delay(log)
        func.paste_into(page, "input.input_text#id", acc["n_id"])
        func.human_delay(log)
        func.paste_into(page, "input.input_text#pw", acc["n_pwd"] or "")
        func.human_delay(log)

        func.click_login(page)

        # 엔터 후 로딩 잠깐 대기 → 캡챠 뜨면 사람이 풀도록 알럿 띄우고 대기
        page.wait_for_timeout(2000)
        captcha = page.locator("#captcha")
        if captcha.count() and captcha.first.is_visible():
            log("    [캡챠] 감지 — 수동 해결 대기 중...")
            pg.alert("캡챠를 해결해 주세요")   # OK 누를 때까지 대기
            page.wait_for_timeout(2000)        # 해결 후 잠깐 여유

        # 로딩 기다렸다가 성공 요소 확인
        try:
            page.wait_for_selector(SUCCESS_SELECTOR, timeout=LOGIN_TIMEOUT_MS)
            log(f"    [성공] {SUCCESS_SELECTOR} 감지 (URL: {page.url})")
            return True
        except Exception:
            log(f"    [실패] {SUCCESS_SELECTOR} 미검출 (URL: {page.url})")
            return False
    finally:
        try:
            browser.close()
        except Exception:
            pass


# --- 배치 실행 -------------------------------------------------------------

def run_batch(days=DEFAULT_DAYS, log=print):
    """대상 계정 전체를 IP 변경하며 로그인 체크."""
    log(f"=== 로그인 체크 배치 시작 (기준: {days}일) ===")

    # 1) 대상 목록 + UA 목록 미리 확보 (IP 변경 전, 네트워크 정상일 때)
    targets = func.fetch_login_targets(days)
    uas = func.fetch_user_agents()
    log(f"대상 계정: {len(targets)}건 / 사용 UA: {len(uas)}개")
    if not targets:
        log("체크할 대상이 없습니다.")
        return {"total": 0, "ok": 0, "fail": 0}
    if not uas:
        log("사용 가능한 user_agent 가 없습니다. 중단.")
        return {"total": len(targets), "ok": 0, "fail": 0}

    devices = func.adb_devices()
    if not devices:
        log("[경고] 연결된 휴대폰이 없어 IP 변경을 건너뜁니다. (adb devices)")

    ok = fail = 0
    with sync_playwright() as p:
        for i, acc in enumerate(targets, 1):
            log(f"\n[{i}/{len(targets)}] {acc['n_id']} "
                f"(idx={acc['n_idx']}, 상태={acc['n_status']})")

            # 2) IP 변경 (비행기모드 ON→OFF) + 변경 확인. 폰 없으면 스킵.
            if devices:
                info = func.rotate_ip(serial=devices[0], off_seconds=3, log=log)
                if not info["changed"]:
                    log(f"    [경고] IP 변경 안됨 "
                        f"(before={info['before']} / after={info['after']})")
                    pg.alert(
                        "IP 변경 안됨\n"
                        f"변경 전: {info['before']}\n변경 후: {info['after']}"
                    )

            # 3) 로그인 체크 (계정마다 랜덤 UA)
            ua = random.choice(uas)
            log(f"    UA: {ua[:60]}...")
            try:
                success = _login_and_check(p, acc, ua, log)
            except Exception as e:
                success = False
                log(f"    [오류] 로그인 중 예외: {e}")

            # 4) 결과 저장 (IP 변경 후이므로 네트워크 복구된 상태, 자체 재연결)
            try:
                func.update_login_result(acc["n_idx"], success)
                log(f"    DB 기록: login_chk={int(success)}, last_login_chk=NOW()")
            except Exception as e:
                log(f"    [오류] DB 기록 실패: {e}")

            ok += int(success)
            fail += int(not success)

    log(f"\n=== 완료: 총 {len(targets)}건 / 성공 {ok} / 실패 {fail} ===")
    return {"total": len(targets), "ok": ok, "fail": fail}
