"""네이버 로그인.

기존 n_blog_writer 의 로그인 코드를 가져와, 계정을 밖에서 받도록만 고쳤다.

⚠️ **캡차·2단계 인증은 프로그램이 풀지 않는다.** 뜨면 멈추고 사람을 부른다.
   그게 맞기도 하고, 자동으로 뚫으려 들면 계정이 더 빨리 막힌다.
"""
from __future__ import annotations

import time
from typing import Callable

import pyperclip
from playwright.sync_api import BrowserContext, Page, TimeoutError as PWTimeout

from config import Account

LogFn = Callable[[str], None]

NAVER_URL = "https://www.naver.com"
LOGIN_URL = "https://nid.naver.com/nidlogin.login?mode=form&url=https://www.naver.com"

# 네이버 메인 우측 상단 로그인 영역.
# 클래스명 뒤의 해시(___HpHMW 등)는 빌드마다 바뀌므로 접두사로만 매칭한다.
LOGOUT_LINK = "[class^='MyView-module__btn_logout'], [class*=' MyView-module__btn_logout']"

# 로그인 결과
OK = "ok"
NEED_HUMAN = "need_human"  # 캡차·기기등록·2단계 인증
FAILED = "failed"  # 아이디/비번이 틀렸거나 막힌 계정


def logged_in(page: Page, timeout: float = 10.0) -> bool:
    """로그아웃 버튼이 보이면 로그인된 것으로 본다.

    캡차 화면을 건드리지 않도록 **페이지를 옮기지 않고** 지금 페이지만 들여다본다.
    """
    deadline = time.time() + timeout
    while True:
        try:
            if "nidlogin" not in page.url and page.locator(LOGOUT_LINK).count() > 0:
                return True
        except Exception:
            # 화면 전환 중이면 잠시 뒤 다시 본다
            pass
        if time.time() >= deadline:
            return False
        time.sleep(0.5)


def _paste(page: Page, selector: str, value: str) -> None:
    """클립보드 붙여넣기로 넣는다.

    keyboard.type 처럼 일정한 간격의 타이핑은 사람이 아닌 티가 난다.
    """
    page.click(selector)
    pyperclip.copy(value)
    page.keyboard.press("Control+V")
    time.sleep(0.4)


def login(context: BrowserContext, account: Account, timeout: int = 15, log: LogFn = print) -> str:
    """OK / NEED_HUMAN / FAILED 중 하나를 돌려준다."""
    page = context.pages[0] if context.pages else context.new_page()

    log(f"  {account.login_id}: 네이버를 여는 중...")
    page.goto(NAVER_URL, wait_until="domcontentloaded")
    if logged_in(page, timeout=5):
        log(f"  {account.login_id}: 이미 로그인되어 있음 (쿠키 유지)")
        return OK

    log(f"  {account.login_id}: 로그인 시도")
    page.goto(LOGIN_URL, wait_until="domcontentloaded")

    _paste(page, "#id", account.login_id)
    _paste(page, "#pw", account.password)

    # '로그인 상태 유지' — 다음 실행부터 이 폴더의 쿠키로 그냥 들어간다
    try:
        keep = page.locator("#loginStay")
        if keep.count() and not keep.is_checked():
            page.click("label[for='loginStay']")
    except PWTimeout:
        pass

    # 반응형이라 로그인 버튼이 두 개 있다 (보이는 쪽만 누른다)
    page.locator("#loginBtn_row, #loginBtn_column").locator("visible=true").first.click()

    if logged_in(page, timeout=timeout):
        log(f"  {account.login_id}: 로그인 성공")
        return OK

    # 아직 로그인 페이지면 왜 막혔는지 화면 글자로 가늠한다
    body = ""
    try:
        body = page.inner_text("body")[:2000]
    except Exception:
        pass

    if any(word in body for word in ("아이디 또는 비밀번호", "다시 확인", "등록되지 않은")):
        log(f"  {account.login_id}: 아이디·비밀번호가 맞지 않음")
        return FAILED

    log(f"  {account.login_id}: 사람 확인이 필요합니다 (캡차·기기등록 등). 창을 보세요")
    return NEED_HUMAN
