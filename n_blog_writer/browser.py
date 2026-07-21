"""독립 프로필 기반 Playwright 브라우저 실행기."""
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import BrowserContext, sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 자동화 탐지 회피용 최소 패치 (navigator.webdriver 등)
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}};
"""

# 창 크기/위치 고정 (직접 클릭해서 조작할 수 있도록)
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
WINDOW_X = 0
WINDOW_Y = 0

LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-default-browser-check",
    "--no-first-run",
    f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
    f"--window-position={WINDOW_X},{WINDOW_Y}",
]


@contextmanager
def launch_context(profile_dir: Path, headless: bool = False):
    """프로필 디렉터리 하나에 묶인 persistent context 를 연다.

    프로필 폴더에 쿠키/세션이 남으므로 다음 실행부터는 로그인이 유지된다.
    """
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context: BrowserContext = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            args=LAUNCH_ARGS,
            user_agent=USER_AGENT,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport=None,
            no_viewport=True,
        )
        context.add_init_script(STEALTH_JS)
        try:
            yield context
        finally:
            context.close()
