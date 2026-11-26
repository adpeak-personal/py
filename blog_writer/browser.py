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

# 창 크기는 **PC 로 열고, 로그인할 때만 폰 크기로 줄인다** (`to_mobile`/`to_pc`).
# ⚠️ 모바일 쪽을 너무 좁히지 않는다 — 마우스를 실제로 움직이므로 칸이 보일 만큼은 넓어야 한다.
PC_WINDOW = (1280, 900)
MOBILE_WINDOW = (500, 900)

LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-default-browser-check",
    "--no-first-run",
    f"--window-size={PC_WINDOW[0]},{PC_WINDOW[1]}",
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


# 페이지마다 CDP 창구를 하나만 쓴다. 바꿀 때마다 새로 열면 쌓인다
_CDP: dict[int, object] = {}

#: **PC 일 때의 UA.** 크롬이 스스로 보내는 것을 켤 때 받아 적어 둔다.
#  프로필의 UA(안드로이드)는 로그인할 때만 덮어 쓰고, 끝나면 이걸로 되돌린다.
#  ⚠️ 이 프로그램은 한 번에 브라우저 하나만 돌린다(아이디 하나씩). 그래서 전역 하나로 둔다.
_PC_AGENT = ""
#: 켤 때의 `navigator.userAgentData` 그대로. PC 로 되돌릴 때 이걸 다시 깐다
_PC_HINTS: dict = {}

# 크롬이 켤 때 읽어 가는 것들. 저엔트로피는 바로, 나머지는 물어서 받는다
HINT_JS = """(async () => {
  const d = navigator.userAgentData;
  if (!d) return null;
  let hi = {};
  try {
    hi = await d.getHighEntropyValues(['platformVersion', 'architecture', 'uaFullVersion']);
  } catch (e) {}
  return {
    brands: d.brands.map(b => ({brand: b.brand, version: b.version})),
    mobile: d.mobile,
    platform: d.platform,
    platformVersion: hi.platformVersion || '',
    architecture: hi.architecture || '',
    fullVersion: hi.uaFullVersion || '',
  };
})()"""


def _brands(version: str) -> list[dict]:
    """브랜드 목록.

    ⚠️ **크롬이 끼워 넣는 가짜 브랜드를 직접 만들지 않는다.** 진짜 크롬은 켤 때마다
    `Not/A)Brand 8` 처럼 이름·순서가 조금씩 다른 것을 하나 섞는데, 늘 똑같은 값을
    박아 두면 그게 오히려 표가 된다. 그래서 켤 때 받아 둔 목록을 그대로 쓰고,
    버전 숫자만 지금 쓰는 UA 에 맞춰 갈아 준다.
    """
    native = _PC_HINTS.get("brands") or []
    if native:
        out = []
        for item in native:
            name = str(item.get("brand", ""))
            # 가짜 하나는 손대지 않는다. 나머지(Chromium·Google Chrome)만 버전을 맞춘다
            keep = "Not" in name and "Brand" in name
            out.append(item if keep else {"brand": name, "version": version})
        return out
    return [
        {"brand": "Not;A=Brand", "version": "99"},
        {"brand": "Google Chrome", "version": version},
        {"brand": "Chromium", "version": version},
    ]


def _cdp(context: BrowserContext, page):
    key = id(page)
    if key not in _CDP:
        _CDP[key] = context.new_cdp_session(page)
    return _CDP[key]


def _apply_ua(context: BrowserContext, page, ua: str) -> None:
    """그 페이지의 UA 와 **클라이언트 힌트를 같이** 덮는다 (CDP)."""
    part = _ua_parts(ua)
    try:
        cdp = _cdp(context, page)
        cdp.send(
            "Emulation.setUserAgentOverride",
            {
                "userAgent": ua,
                "acceptLanguage": "ko-KR,ko;q=0.9",
                "platform": "Linux armv8l" if part["mobile"] else "Win32",
                "userAgentMetadata": {
                    "brands": _brands(part["version"]),
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


def capture_pc(page) -> None:
    """지금 페이지에서 **크롬 본래의 UA·힌트**를 받아 적는다 (한 번만).

    ⚠️ `navigator.userAgentData` 는 보안 컨텍스트에서만 나오므로 `about:blank` 에서는
    비어 있을 수 있다. 그래서 켤 때가 아니라 **PC 로 진짜 페이지를 한 번 띄운 뒤**,
    폰으로 바꾸기 직전에 부른다.
    """
    global _PC_AGENT, _PC_HINTS
    if _PC_HINTS:
        return
    try:
        if not _PC_AGENT:
            _PC_AGENT = page.evaluate("navigator.userAgent")
        hints = page.evaluate(HINT_JS)
        if hints and hints.get("brands"):
            _PC_HINTS = hints
    except Exception:
        pass


def _touch(context: BrowserContext, page, on: bool) -> None:
    """손가락으로 만지는 기기인 척할지. UA 는 폰인데 터치가 없으면 어긋나 보인다."""
    try:
        _cdp(context, page).send(
            "Emulation.setTouchEmulationEnabled",
            {"enabled": on, "maxTouchPoints": 5 if on else 1},
        )
    except Exception:
        pass


def _resize(context: BrowserContext, page, size: tuple[int, int]) -> None:
    """창 크기를 바꾼다.

    ⚠️ `set_viewport_size` 가 아니라 **진짜 창**을 움직인다(`Browser.setWindowBounds`).
    마우스를 실제로 움직여 누르기 때문에, 창과 화면 좌표가 맞아야 한다.
    """
    try:
        cdp = _cdp(context, page)
        window = cdp.send("Browser.getWindowForTarget")
        cdp.send(
            "Browser.setWindowBounds",
            {
                "windowId": window["windowId"],
                "bounds": {"left": 0, "top": 0, "width": size[0], "height": size[1]},
            },
        )
    except Exception:
        pass


def to_mobile(context: BrowserContext, page, ua: str) -> None:
    """**폰으로 바꾼다** — UA·클라이언트 힌트·터치·창 크기까지 같이.

    로그인 직전에만 쓴다. PC 로그인 화면에서 보호조치가 자꾸 걸려서 옛 프로그램이
    쓰던 길(m.naver.com)로 들어가되, 들어가기 전까지는 PC 로 있는다.
    """
    capture_pc(page)  # 덮기 전에 본래 모습을 적어 둔다 (되돌릴 때 쓴다)
    if ua:
        _apply_ua(context, page, ua)
    _touch(context, page, True)
    _resize(context, page, MOBILE_WINDOW)


def to_pc(context: BrowserContext, page) -> None:
    """**PC 로 되돌린다.** 켤 때 받아 적어 둔 크롬 본래 모습 그대로 돌아간다.

    글쓰기는 PC 화면에서 하므로, 로그인이 끝나면 반드시 이쪽으로 돌려 둔다.

    ⚠️ CDP 에는 '덮은 걸 치운다' 가 없다. 켤 때 적어 둔 UA 와 힌트를 **다시 깔아서**
    되돌린다 — 그래서 켤 때 그걸 받아 두는 게 중요하다.
    """
    if _PC_AGENT and _PC_HINTS:
        try:
            _cdp(context, page).send(
                "Emulation.setUserAgentOverride",
                {
                    "userAgent": _PC_AGENT,
                    "acceptLanguage": "ko-KR,ko;q=0.9",
                    "platform": "Win32",
                    "userAgentMetadata": {
                        "brands": _PC_HINTS.get("brands") or [],
                        "fullVersion": _PC_HINTS.get("fullVersion", ""),
                        "platform": _PC_HINTS.get("platform", "Windows"),
                        "platformVersion": _PC_HINTS.get("platformVersion", ""),
                        "architecture": _PC_HINTS.get("architecture", ""),
                        "model": "",
                        "mobile": False,
                    },
                },
            )
        except Exception:
            pass
    elif _PC_AGENT:
        _apply_ua(context, page, _PC_AGENT)
    _touch(context, page, False)
    _resize(context, page, PC_WINDOW)


@contextmanager
def launch(profile: Profile, account: Account, headless: bool = False):
    """그 아이디의 크롬 폴더를, 그 프로필의 IP 로 연다.

    폴더는 아이디마다 따로고 IP 는 프로필 단위로 같다 (`Profile.dir_for` 참고).

    ⚠️ 같은 폴더를 두 번 동시에 열면 크롬이 폴더를 잠가서 두 번째가 죽는다.
    한 아이디는 **한 번에 하나씩** 돌린다.
    """
    global _PC_AGENT

    user_dir = profile.dir_for(account)
    user_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # ⚠️ **PC 로 켠다.** UA 를 여기서 덮지 않는다 — 크롬이 스스로 보내는 윈도우
        #    UA 가 클라이언트 힌트까지 저절로 맞아서 제일 깔끔하다.
        #    폰으로 바꾸는 건 로그인 직전에 `to_mobile` 이 한다.
        context: BrowserContext = p.chromium.launch_persistent_context(
            user_data_dir=str(user_dir),
            headless=headless,
            args=LAUNCH_ARGS,
            proxy=profile.proxy,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            no_viewport=True,
        )
        context.add_init_script(STEALTH_JS)

        # 지난 실행이 남긴 것들을 치운다 (전역이라 한 번에 하나만 돈다)
        _CDP.clear()
        _PC_AGENT = ""
        _PC_HINTS.clear()
        try:
            probe = context.pages[0] if context.pages else context.new_page()
            _PC_AGENT = probe.evaluate("navigator.userAgent")
        except Exception:
            pass
        # 힌트는 PC 로 진짜 페이지를 띄운 뒤에 받는다 — `capture_pc` 참고

        try:
            yield context
        finally:
            _CDP.clear()
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
