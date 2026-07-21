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
# 클래스명(MyView-module__link_login___xxxx)은 개편 때마다 해시가 바뀌므로
# 링크의 href 로 찾는다. 이쪽이 훨씬 오래 간다.
LOGIN_AREA = "#account"
LOGIN_LINK = "a[href*='nidlogin.login']"
LOGOUT_LINK = "a[href*='nidlogin.logout']"

# 세션 쿠키. 버튼을 둘 다 못 찾았을 때의 최종 판정 근거.
SESSION_COOKIES = ("NID_AUT", "NID_SES")

# 메인 화면에서 판정 결과를 확인용으로 띄운다. 확인 끝나면 False 로 둘 것.
DEBUG_ALERT = True


def _has_session_cookies(page: Page) -> bool:
    names = {c["name"] for c in page.context.cookies()}
    return all(name in names for name in SESSION_COOKIES)


def is_logged_in(page: Page, alert: bool = False) -> bool:
    """네이버 메인에서 로그인 상태를 판단한다.

    버튼이 하나라도 잡히면 그걸 따르고, 둘 다 0개인 애매한 경우
    (렌더링 전이거나 마크업이 또 바뀐 경우) 세션 쿠키로 판정한다.
    """
    if not page.url.startswith(NAVER_URL):
        page.goto(NAVER_URL, wait_until="domcontentloaded")

    # 로그인 영역이 그려질 때까지 기다린다. 못 기다려도 아래에서 판정은 한다.
    try:
        page.wait_for_selector(LOGIN_AREA, timeout=5000)
    except PWTimeout:
        pass

    logout = page.locator(LOGOUT_LINK).count()
    login_btn = page.locator(LOGIN_LINK).count()

    if logout > 0:
        result, basis = True, "로그아웃 버튼 발견"
    elif login_btn > 0:
        result, basis = False, "로그인 버튼 발견"
    else:
        result = _has_session_cookies(page)
        basis = "버튼 없음 -> 세션 쿠키로 판정"

    if alert and DEBUG_ALERT:
        pg.alert(
            text=(
                f"URL: {page.url}\n"
                f"로그아웃 버튼: {logout}개\n"
                f"로그인 버튼: {login_btn}개\n"
                f"세션 쿠키: {'있음' if _has_session_cookies(page) else '없음'}\n\n"
                f"판정: {'로그인됨' if result else '비로그인'} ({basis})"
            ),
            title="네이버 메인 로그인 상태 확인",
        )

    return result


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
    timeout: int = 180,
    log: LogFn = print,
) -> Page:
    """로그인된 페이지를 돌려준다. 이미 로그인 상태면 그대로 재사용한다."""
    page = context.pages[0] if context.pages else context.new_page()

    page.goto(NAVER_URL, wait_until="domcontentloaded")
    if is_logged_in(page, alert=True):
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

    # 캡차 / 2단계 인증 / 기기 등록 등은 사람이 처리하도록 대기
    deadline = time.time() + timeout
    warned = False
    last_report = 0.0
    while time.time() < deadline:
        # 로그인 페이지를 벗어났을 때만 메인에서 판정한다.
        if "nidlogin" not in page.url:
            if is_logged_in(page):
                log("로그인 성공")
                return page
        elif not warned:
            log("캡차/2단계 인증이 뜨면 브라우저에서 직접 처리해 주세요. 대기 중...")
            warned = True

        # 아무 로그도 없이 멈춘 것처럼 보이지 않도록 현재 상태를 주기적으로 알린다.
        if time.time() - last_report > 15:
            left = int(deadline - time.time())
            log(f"대기 중 ({left}초 남음) - {page.url}")
            last_report = time.time()

        time.sleep(2)

    raise TimeoutError("로그인에 실패했습니다 (시간 초과)")
