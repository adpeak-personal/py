"""프로필 하나로 크롬을 띄운다 (IP 한 쌍).

프로필 폴더에 쿠키가 남으므로 **두 번째 실행부터는 로그인이 유지된다.**
프록시는 Playwright 의 context 단위 설정이라, 프로필마다 다른 IP 로 나간다.
"""
from __future__ import annotations

import json
import re
import time
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import BrowserContext, sync_playwright

from config import Account, Profile

# 자동화 티가 나는 기본값만 되돌린다 (navigator.webdriver 등)
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}};
"""

# 모바일 네이버를 띄우므로 창도 폰에 가깝게 둔다.
# ⚠️ 너무 좁히지 않는다 — 마우스를 실제로 움직이므로 칸이 보일 만큼은 넓어야 한다.
WINDOW_WIDTH = 500
WINDOW_HEIGHT = 900

LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-default-browser-check",
    "--no-first-run",
    f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
    "--window-position=0,0",
]


def _ua_parts(ua: str) -> dict:
    """UA 문자열에서 클라이언트 힌트에 넣을 값들을 뽑는다.

    ⚠️ **UA 문자열만 바꾸면 들통난다.** 크로미움은 `navigator.userAgentData` 로
    브랜드·버전·플랫폼·모바일 여부를 따로 알려주는데, Playwright 의 `user_agent` 는
    그걸 안 건드린다. 실측으로 UA 는 "Android 14 폰" 이라면서 platform 은 Win32,
    mobile 은 false, 브랜드는 Chromium 159 였다. 사이트에서 한눈에 보인다.
    """
    version = (re.search(r"Chrome/(\d+)", ua) or [None, "131"])[1]
    full = (re.search(r"Chrome/([\d.]+)", ua) or [None, f"{version}.0.0.0"])[1]
    android = re.search(r"Android (\d+)", ua)
    model = re.search(r"Android [\d.]+; ([^)]+)\)", ua)
    return {
        "version": version,
        "full": full,
        "platform": "Android" if android else "Windows",
        "platform_version": (android[1] if android else "10") + ".0.0",
        "model": model[1].strip() if model else "",
        "mobile": "Mobile" in ua,
    }


def _apply_ua(context: BrowserContext, page, ua: str) -> None:
    """그 페이지의 UA 와 **클라이언트 힌트를 같이** 덮는다 (CDP)."""
    part = _ua_parts(ua)
    try:
        cdp = context.new_cdp_session(page)
        cdp.send(
            "Emulation.setUserAgentOverride",
            {
                "userAgent": ua,
                "acceptLanguage": "ko-KR,ko;q=0.9",
                "platform": "Linux armv8l" if part["mobile"] else "Win32",
                "userAgentMetadata": {
                    "brands": [
                        {"brand": "Not;A=Brand", "version": "99"},
                        {"brand": "Google Chrome", "version": part["version"]},
                        {"brand": "Chromium", "version": part["version"]},
                    ],
                    "fullVersion": part["full"],
                    "platform": part["platform"],
                    "platformVersion": part["platform_version"],
                    "architecture": "",
                    "model": part["model"],
                    "mobile": part["mobile"],
                },
            },
        )
    except Exception:
        # 못 덮어도 멈추지는 않는다 — UA 문자열만이라도 바뀐 채로 돈다
        pass


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
            # 손가락으로 만지는 기기인 척한다 — UA 만 모바일이고 터치가 없으면 어긋나 보인다
            has_touch=True,
            no_viewport=True,
        )
        context.add_init_script(STEALTH_JS)

        # 이미 열린 탭과, 앞으로 열릴 탭 전부에 건다
        for opened in context.pages:
            _apply_ua(context, opened, profile.agent)
        context.on("page", lambda pg: _apply_ua(context, pg, profile.agent))

        try:
            yield context
        finally:
            context.close()


def measure_ip(context: BrowserContext) -> str | None:
    """지금 이 브라우저가 밖에서 어떤 IP 로 보이는지.

    **파이썬이 아니라 브라우저로 잰다** — 네이버가 실제로 보게 될 IP 가 이것이기 때문이다.
    프록시를 쓰면 PC 의 IP 와 다르다.
    """
    page = context.new_page()
    try:
        page.goto("https://api.ipify.org?format=json", wait_until="domcontentloaded", timeout=20000)
        return str(json.loads(page.inner_text("pre, body"))["ip"])
    except Exception as error:  # 네트워크·형식 무엇이든 — 모르면 작업하지 않는 게 맞다
        print(f"  IP 확인 실패 ({type(error).__name__})")
        return None
    finally:
        page.close()


# 찍은 화면이 쌓이는 곳 (git 에 올라가지 않는다)
SHOT_DIR = Path(__file__).resolve().parent / "shots"


def save_shot(context: BrowserContext, name: str) -> str | None:
    """지금 창을 사진으로 남긴다.

    막힌 자리를 눈으로 봐야 할 때 쓴다 — 캡차인지, 기기 등록인지, 비밀번호 오류인지는
    글자만으로는 구분이 안 된다.

    ⚠️ **로그인된 화면이 그대로 찍힌다.** 이 폴더는 이 PC 에만 두고 올리지 않는다.
    """
    # 빈 탭(about:blank)이 아니라 **실제로 뭘 띄우고 있는 탭**을 찍는다.
    # persistent context 는 시작할 때 빈 탭을 하나 들고 있어서, pages[0] 을 찍으면 흰 화면이 나온다.
    pages = [pg for pg in context.pages if not pg.url.startswith("about:")]
    page = pages[-1] if pages else (context.pages[0] if context.pages else None)
    if page is None:
        return None
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SHOT_DIR / f"{time.strftime('%m%d-%H%M%S')}-{name}.png"
    try:
        page.wait_for_timeout(400)  # 그리는 중에 찍히지 않게 잠깐 둔다
        page.screenshot(path=str(path), full_page=False)
        return str(path)
    except Exception as error:
        print(f"  화면을 찍지 못했습니다 ({type(error).__name__})")
        return None
