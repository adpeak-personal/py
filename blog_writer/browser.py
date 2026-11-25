"""프로필 하나로 크롬을 띄운다 (IP 한 쌍).

프로필 폴더에 쿠키가 남으므로 **두 번째 실행부터는 로그인이 유지된다.**
프록시는 Playwright 의 context 단위 설정이라, 프로필마다 다른 IP 로 나간다.
"""
from __future__ import annotations

from contextlib import contextmanager

from playwright.sync_api import BrowserContext, sync_playwright

from config import Account, Profile

# 자동화 티가 나는 기본값만 되돌린다 (navigator.webdriver 등)
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}};
"""

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800

LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-default-browser-check",
    "--no-first-run",
    f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
    "--window-position=0,0",
]


@contextmanager
def launch(profile: Profile, account: Account, headless: bool = False):
    """그 아이디의 크롬 폴더를, 그 프로필의 IP 로 연다.

    폴더는 아이디마다 따로고 IP 는 프로필 단위로 같다 (`Profile.dir_for` 참고).

    ⚠️ 같은 폴더를 두 번 동시에 열면 크롬이 폴더를 잠가서 두 번째가 죽는다.
    한 아이디는 **한 번에 하나씩** 돌린다.
    """
    user_dir = profile.dir_for(account)
    user_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context: BrowserContext = p.chromium.launch_persistent_context(
            user_data_dir=str(user_dir),
            headless=headless,
            args=LAUNCH_ARGS,
            proxy=profile.proxy,
            user_agent=profile.agent,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            no_viewport=True,
        )
        context.add_init_script(STEALTH_JS)
        try:
            yield context
        finally:
            context.close()


def current_ip(context: BrowserContext) -> str:
    """지금 이 프로필이 어떤 IP 로 나가는지 확인한다.

    프록시가 제대로 물렸는지 눈으로 보려고 쓴다. 실패해도 작업은 계속한다.
    """
    page = context.new_page()
    try:
        page.goto("https://api.ipify.org?format=json", wait_until="domcontentloaded", timeout=15000)
        import json

        return str(json.loads(page.inner_text("pre, body"))["ip"])
    except Exception as error:  # 네트워크·형식 무엇이든 확인용이라 치명적이지 않다
        return f"확인 실패 ({type(error).__name__})"
    finally:
        page.close()
