"""네이버 로그인 — **모바일(m.naver.com)에서 한다.**

옛 `blog_auto_server_mix` 가 쓰던 길을 그대로 옮겼다. 그쪽은 모바일 UA 로 크롬을 띄워
`m.naver.com` 에서 로그인하고, 끝난 뒤 `naver.com`(PC)으로 옮겨 가 작업한다.
PC 로그인 화면에서 보호조치가 계속 걸려서 바꾼 것이다.

⚠️ **캡차·보호조치는 프로그램이 풀지 않는다.** 뜨면 멈추고 사람을 부른다.
   그게 맞기도 하고, 자동으로 뚫으려 들면 계정이 더 빨리 막힌다.
"""
from __future__ import annotations

import random
import time
from typing import Callable

import pyperclip
from playwright.sync_api import BrowserContext, Page, TimeoutError as PWTimeout

import human
from config import Account

LogFn = Callable[[str], None]

MOBILE_HOME = "https://m.naver.com"
# 로그인이 끝나면 여기로 옮긴다. 글쓰기는 PC 화면에서 한다
PC_HOME = "https://www.naver.com"

# ── 모바일 네이버 선택자 (옛 프로그램에서 그대로) ──────────────
# 오른쪽 위 메뉴 버튼. 네이버가 두 이름을 섞어 쓴다
ASIDE_BUTTON = ".sch_ico_aside, .sha_ico_aside"
# 메뉴 안의 로그인 줄. 로그인돼 있으면 "○○님" 으로 바뀐다.
# ⚠️ 옛 프로그램의 `.link_user` 는 지금 없다 — 2026-11 기준 `.ah_link_user` 다.
#    네이버가 또 바꿀 수 있으니 둘 다 적어 둔다.
USER_LINK = ".ah_link_user, .link_user"
# 로그인된 상태에서만 뜨는 상자
LOGGED_IN_BOX = ".aside_header"
# 가끔 끼어드는 것들
RETRY_BUTTON = ".btn_retry"
POPUP_CLOSE = ".lst_btn_close"

CAPTCHA_BOX = ".captcha_wrap"
# "새로운 환경에서 로그인" 안내의 확인 버튼
NEW_DEVICE_BUTTON = ".btn_white"
# 보호조치·대량생성 안내가 이 버튼 글자에 담겨 온다
NOTICE_BUTTON = ".btn_next"
ERROR_MESSAGE = "#error_message"

# 로그인 결과
OK = "ok"
NEED_HUMAN = "need_human"  # 캡차·보호조치·사람 확인
FAILED = "failed"  # 아이디/비번이 틀렸거나 막힌 계정


def _text(page: Page, selector: str) -> str:
    """그 선택자의 글자. 없으면 빈 문자열"""
    try:
        target = page.locator(selector).first
        return target.inner_text(timeout=1500) if target.count() else ""
    except Exception:
        return ""


def _click(page: Page, selector: str, log: LogFn) -> bool:
    """**보이면** 누른다. 마우스를 못 쓰면 평범한 클릭으로.

    ⚠️ `count()` 만 보면 안 된다 — 숨어 있는 요소도 세어지는데, 그걸 누르러 가면
    `move_and_click` 이 '보일 때까지' 10초를 헛기다린다. 한 바퀴에 20초씩 샜다.
    """
    try:
        target = page.locator(selector).first
        if target.count() == 0 or not target.is_visible(timeout=1000):
            return False
    except Exception:
        return False
    if not human.move_and_click(page, selector, log):
        try:
            page.locator(selector).first.click()
        except Exception:
            return False
        human.rest(0.4, 1.0)
    return True


def logged_in(page: Page, timeout: float = 10.0) -> bool:
    """로그인돼 있는지.

    모바일은 메뉴 안의 `.link_user` 가 "로그인" → "○○님" 으로 바뀐다.
    캡차 화면을 건드리지 않도록 **페이지를 옮기지 않고** 지금 페이지만 들여다본다.
    """
    deadline = time.time() + timeout
    while True:
        try:
            if page.locator(LOGGED_IN_BOX).count() > 0:
                return True
            text = _text(page, USER_LINK)
            if text and "로그인" not in text:
                return True
        except Exception:
            pass  # 화면 전환 중이면 잠시 뒤 다시 본다
        if time.time() >= deadline:
            return False
        time.sleep(0.5)


def _fill(page: Page, selector: str, value: str, log: LogFn) -> bool:
    """칸 하나를 채운다 — **진짜 마우스로 옮겨 가서 누르고, 붙여넣는다.**

    ⚠️ **넣고 나서 칸이 실제로 찼는지 확인한다.** 붙여넣기는 조용히 실패할 수 있다
    (클립보드를 다른 프로그램이 가져갔다든가, 창이 뒤로 밀렸다든가).
    확인 없이 보내면 빈 칸으로 로그인을 시도하게 되고, 그건 그대로 실패 횟수로 쌓인다.
    """
    for attempt in (1, 2):
        if human.move_and_click(page, selector, log):
            human.paste(value)
        else:
            log("     마우스를 쓰지 못해 평범한 입력으로 넣습니다")
            page.click(selector)
            pyperclip.copy(value)
            page.keyboard.press("Control+A")
            time.sleep(random.uniform(0.3, 0.9))
            page.keyboard.press("Control+V")

        human.rest(0.4, 1.0)
        try:
            filled = page.input_value(selector)
        except Exception:
            filled = ""
        if filled == value:
            return True
        log(f"     {selector} 가 제대로 안 들어갔습니다 ({attempt}번째)")
        human.rest(0.8, 1.6)
    return False


def _open_login_form(page: Page, log: LogFn) -> bool:
    """모바일 메인에서 로그인 화면까지 간다. 이미 로그인돼 있으면 False."""
    for _ in range(6):
        if page.locator("#id").count() > 0:
            return True

        # 가끔 끼어드는 것들을 먼저 치운다
        _click(page, RETRY_BUTTON, log)
        _click(page, POPUP_CLOSE, log)

        if logged_in(page, timeout=2):
            return False

        # 오른쪽 위 메뉴 → 로그인
        _click(page, ASIDE_BUTTON, log)
        human.rest(1.0, 1.8)
        text = _text(page, USER_LINK)
        if text and "로그인" not in text:
            return False
        _click(page, USER_LINK, log)
        human.rest(1.2, 2.0)

    return page.locator("#id").count() > 0


def _after_submit(page: Page, account: Account, log: LogFn, timeout: int) -> str:
    """보낸 뒤 화면을 보고 결과를 가린다."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        # 캡차 — 사람이 풀어야 한다
        if page.locator(CAPTCHA_BOX).count() > 0:
            log(f"  {account.login_id}: 캡차가 떴습니다. 창에서 직접 풀어 주세요")
            human.call_human()
            return NEED_HUMAN

        # 보호조치·대량생성은 버튼 글자에 담겨 온다
        notice = _text(page, NOTICE_BUTTON)
        if "보호조치" in notice:
            log(f"  {account.login_id}: 보호조치입니다")
            log("     네이버가 이 계정을 묶어 둔 상태입니다. 풀고 나서 하루쯤 쉬게 두세요.")
            human.call_human()
            return NEED_HUMAN
        if "대량생성" in notice:
            log(f"  {account.login_id}: 대량생성으로 묶인 계정입니다")
            human.call_human()
            return NEED_HUMAN

        error = _text(page, ERROR_MESSAGE)
        if "비밀번호를 잘못" in error:
            log(f"  {account.login_id}: 아이디·비밀번호가 맞지 않음")
            return FAILED
        if "자동입력" in error:
            log(f"  {account.login_id}: 자동입력 방지 화면입니다. 창에서 직접 풀어 주세요")
            human.call_human()
            return NEED_HUMAN

        # "새로운 환경에서 로그인" — 내 기기를 등록하는 화면이라 눌러 준다
        if page.locator(NEW_DEVICE_BUTTON).count() > 0:
            log(f"  {account.login_id}: 새 기기 안내입니다. 확인을 누릅니다")
            _click(page, NEW_DEVICE_BUTTON, log)
            human.rest(1.0, 2.0)
            continue

        if logged_in(page, timeout=2):
            return OK

        time.sleep(0.6)

    log(f"  {account.login_id}: 결과를 알 수 없습니다. 창을 보세요")
    human.call_human()
    return NEED_HUMAN


def login(context: BrowserContext, account: Account, timeout: int = 25, log: LogFn = print) -> str:
    """OK / NEED_HUMAN / FAILED 중 하나를 돌려준다.

    끝에 **PC 화면으로 옮겨 둔다** — 글쓰기는 거기서 하기 때문이다.
    """
    page = context.pages[0] if context.pages else context.new_page()

    log(f"  {account.login_id}: 모바일 네이버를 여는 중...")
    page.goto(MOBILE_HOME, wait_until="domcontentloaded")
    human.focus_window(page)
    human.rest(1.2, 2.2)

    if logged_in(page, timeout=4):
        log(f"  {account.login_id}: 이미 로그인되어 있음 (쿠키 유지)")
        page.goto(PC_HOME, wait_until="domcontentloaded")
        return OK

    log(f"  {account.login_id}: 로그인 화면으로")
    if not _open_login_form(page, log):
        if logged_in(page, timeout=3):
            log(f"  {account.login_id}: 이미 로그인되어 있음")
            page.goto(PC_HOME, wait_until="domcontentloaded")
            return OK
        log(f"  {account.login_id}: 로그인 화면을 찾지 못했습니다")
        human.call_human()
        return NEED_HUMAN

    human.rest(1.0, 2.0)
    if not _fill(page, "#id", account.login_id, log):
        log(f"  {account.login_id}: 아이디 칸을 채우지 못했습니다. 보내지 않습니다")
        return NEED_HUMAN
    human.rest(1.0, 2.0)

    if not _fill(page, "#pw", account.password, log):
        log(f"  {account.login_id}: 비밀번호 칸을 채우지 못했습니다. 보내지 않습니다")
        return NEED_HUMAN
    human.rest(1.2, 2.2)

    # 모바일은 버튼 대신 Enter 로 보낸다 (옛 프로그램도 그랬다)
    log(f"  {account.login_id}: 로그인 시도")
    try:
        page.keyboard.press("Enter")
    except PWTimeout:
        pass
    human.rest(1.5, 2.5)

    result = _after_submit(page, account, log, timeout)
    if result == OK:
        log(f"  {account.login_id}: 로그인 성공")
        page.goto(PC_HOME, wait_until="domcontentloaded")
    return result
