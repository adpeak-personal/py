"""네이버 로그인 처리."""
import time
from typing import Callable

import pyautogui as pg
import pyperclip
from playwright.sync_api import BrowserContext, Page, TimeoutError as PWTimeout

from config import Account

LogFn = Callable[[str], None]

LOGIN_URL = "https://nid.naver.com/nidlogin.login?mode=form&url=https://www.naver.com"
NAVER_URL = "https://www.naver.com"

# 네이버 메인 우측 상단 로그인 영역.
# 클래스명 뒤의 해시(___HpHMW 등)는 빌드마다 바뀌므로 접두사로만 매칭한다.
LOGIN_AREA = "#account"
LOGIN_LINK = "[class^='MyView-module__link_login'], [class*=' MyView-module__link_login']"
LOGOUT_LINK = "[class^='MyView-module__btn_logout'], [class*=' MyView-module__btn_logout']"

def wait_logged_in(page: Page, timeout: float = 10.0) -> bool:
    """로그아웃 버튼이 보이면 로그인된 것으로 본다.

    캡차/2단계 인증 화면을 건드리지 않도록 페이지 이동은 하지 않고
    현재 페이지만 폴링한다.
    """
    deadline = time.time() + timeout
    while True:
        try:
            # 로그인 페이지에 머무는 동안은 아직 판정할 수 없다.
            if "nidlogin" not in page.url and page.locator(LOGOUT_LINK).count() > 0:
                return True
        except Exception:
            # 화면 전환 중이면 잠시 뒤 다시 본다.
            pass

        if time.time() >= deadline:
            return False
        time.sleep(0.5)


def _paste(page: Page, selector: str, value: str) -> None:
    """클립보드 붙여넣기로 입력한다.

    네이버는 keyboard.type 같은 균일한 타이핑을 봇으로 판단하는 경우가 있어
    복사-붙여넣기 방식을 쓴다.
    """
    page.click(selector)
    pyperclip.copy(value)
    page.keyboard.press("Control+V")
    time.sleep(0.4)


def login(
    context: BrowserContext,
    account: Account,
    timeout: int = 15,
    log: LogFn = print,
) -> Page:
    """로그인된 페이지를 돌려준다. 이미 로그인 상태면 그대로 재사용한다."""
    page = context.pages[0] if context.pages else context.new_page()

    page.goto(NAVER_URL, wait_until="domcontentloaded")
    if wait_logged_in(page, timeout=5):
        log("기존 세션으로 로그인 유지 중")
        return page

    log("로그인 시도")
    page.goto(LOGIN_URL, wait_until="domcontentloaded")

    _paste(page, "#id", account.user_id)
    _paste(page, "#pw", account.password)

    # 로그인 상태 유지 체크 -> 다음 실행부터 프로필에 세션 재사용
    try:
        keep = page.locator("#loginStay")
        if keep.count() and not keep.is_checked():
            page.click("label[for='loginStay']")
    except PWTimeout:
        pass

    # 반응형 레이아웃이라 로그인 버튼이 두 개 존재한다 (보이는 쪽만 클릭)
    page.locator("#loginBtn_row, #loginBtn_column").locator(
        "visible=true"
    ).first.click()

    # 로그아웃 버튼이 뜨면 그대로 통과, 아니면 캡차/2단계 인증을 사람이 처리한다.
    if wait_logged_in(page, timeout=timeout):
        log("로그인 성공")
        return page

    log("캡차 등 확인이 필요합니다. 처리 후 확인을 눌러 주세요.")
    pg.alert(text="캡챠 등 문제를 해결해 주세요", title="네이버 로그인")

    # 확인을 누르면 곧바로 다음 단계로 넘어간다. 메인이 아니면 메인으로 보내 둔다.
    if not page.url.startswith(NAVER_URL):
        page.goto(NAVER_URL, wait_until="domcontentloaded")
    return page
