"""네이버 로그인.

기존 n_blog_writer 의 로그인 코드를 가져와, 계정을 밖에서 받도록만 고쳤다.

⚠️ **캡차·2단계 인증은 프로그램이 풀지 않는다.** 뜨면 멈추고 사람을 부른다.
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

NAVER_URL = "https://www.naver.com"
LOGIN_URL = "https://nid.naver.com/nidlogin.login?mode=form&url=https://www.naver.com"

# 네이버 메인 우측 상단 로그인 영역.
# 클래스명 뒤의 해시(___HpHMW 등)는 빌드마다 바뀌므로 접두사로만 매칭한다.
LOGOUT_LINK = "[class^='MyView-module__btn_logout'], [class*=' MyView-module__btn_logout']"

# 로그인 결과
OK = "ok"
NEED_HUMAN = "need_human"  # 캡차·기기등록·2단계 인증·보호조치
FAILED = "failed"  # 아이디/비번이 틀렸거나 막힌 계정

# 보호조치 화면에만 뜨는 상자. 글자는 바뀌어도 이건 잘 안 바뀐다
PROTECT_BOX = "#divWarning"
# 캡차·추가 확인 상자
MESSAGE_BOX = ".message_wrap"

# 화면 글자로 가늠하는 단서들
WRONG_WORDS = ("아이디 또는 비밀번호", "다시 확인", "등록되지 않은")
# 보호조치는 캡차와 다르다 — 계정이 이미 찍혔다는 뜻이라, 더 두드리면 안 된다
PROTECT_WORDS = ("보호조치", "보호 조치", "새로운 기기", "기기 등록", "본인 확인", "이용 제한")


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


def _fill(page: Page, selector: str, value: str, log: LogFn) -> bool:
    """칸 하나를 채운다 — **진짜 마우스로 옮겨 가서 누르고, 붙여넣는다.**

    Playwright 의 click/type 은 브라우저가 만들어 내는 가짜 사건이라 커서가
    순간이동하고 글자 간격이 고르다. 보호조치에 걸린 뒤로 실제 입력으로 바꿨다.

    ⚠️ **넣고 나서 칸이 실제로 찼는지 확인한다.** 붙여넣기는 조용히 실패할 수 있다
    (클립보드를 다른 프로그램이 가져갔다든가, 창이 뒤로 밀렸다든가).
    확인 없이 보내면 빈 칸으로 로그인을 시도하게 되고, 그건 그대로 실패 횟수로 쌓인다.

    마우스를 쓰지 못하면(창이 가려졌거나 좌표가 이상하면) 평범한 클릭으로 돌아간다.
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

    # 사람처럼 — 창을 앞으로 두고, 페이지를 한 박자 보고, 칸마다 쉬어 가며 넣는다
    human.focus_window(page)
    human.rest(1.2, 2.2)

    if not _fill(page, "#id", account.login_id, log):
        log(f"  {account.login_id}: 아이디 칸을 채우지 못했습니다. 보내지 않습니다")
        return NEED_HUMAN
    human.rest(1.0, 2.0)

    if not _fill(page, "#pw", account.password, log):
        log(f"  {account.login_id}: 비밀번호 칸을 채우지 못했습니다. 보내지 않습니다")
        return NEED_HUMAN
    human.rest(1.2, 2.2)

    # '로그인 상태 유지' — 다음 실행부터 이 폴더의 쿠키로 그냥 들어간다
    try:
        keep = page.locator("#loginStay")
        if keep.count() and not keep.is_checked():
            if not human.move_and_click(page, "label[for='loginStay']", log):
                page.click("label[for='loginStay']")
            human.rest(0.8, 1.6)
    except PWTimeout:
        pass

    # 반응형이라 로그인 버튼이 두 개 있다 (보이는 쪽만 누른다)
    button = page.locator("#loginBtn_row, #loginBtn_column").locator("visible=true").first
    # 보이는 쪽의 id 를 알아내 그 버튼으로 마우스를 옮긴다
    button_id = button.get_attribute("id") or ""
    human.rest(0.8, 1.6)   # 다 채우자마자 누르지 않는다
    if not (button_id and human.move_and_click(page, f"#{button_id}", log)):
        button.click()

    if logged_in(page, timeout=timeout):
        log(f"  {account.login_id}: 로그인 성공")
        return OK

    # 아직 로그인 페이지면 왜 막혔는지 화면 글자로 가늠한다
    body = ""
    try:
        body = page.inner_text("body")[:2000]
    except Exception:
        pass

    if any(word in body for word in WRONG_WORDS):
        log(f"  {account.login_id}: 아이디·비밀번호가 맞지 않음")
        return FAILED

    # 글자보다 상자를 먼저 본다 — 문구는 바뀌어도 상자는 잘 안 바뀐다
    try:
        if page.locator(PROTECT_BOX).count() > 0:
            log(f"  {account.login_id}: 보호조치 화면입니다 ({PROTECT_BOX})")
            log("     네이버가 이 접속을 낯설게 본 것입니다. 풀고 나서 하루쯤 쉬게 두세요.")
            human.call_human()
            return NEED_HUMAN
        if page.locator(MESSAGE_BOX).count() > 0:
            log(f"  {account.login_id}: 추가 확인 상자가 떴습니다 ({MESSAGE_BOX})")
            human.call_human()
            return NEED_HUMAN
    except Exception:
        pass

    if any(word in body for word in PROTECT_WORDS):
        # 캡차와 달리 계정이 이미 찍힌 상태다. 풀고 나서도 바로 또 돌리지 말 것
        log(f"  {account.login_id}: 보호조치·기기 등록 화면입니다")
        log("     이건 '사람인지 확인' 이 아니라 네이버가 이 접속을 낯설게 본 것입니다.")
        log("     풀고 나서 그 아이디는 하루쯤 쉬게 두세요. 바로 또 돌리면 더 세게 걸립니다.")
        human.call_human()
        return NEED_HUMAN

    log(f"  {account.login_id}: 사람 확인이 필요합니다 (캡차 등). 창을 보세요")
    human.call_human()
    return NEED_HUMAN
