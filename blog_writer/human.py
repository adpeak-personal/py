"""사람처럼 움직이기 — 진짜 마우스와 키보드로.

Playwright 의 `click()` · `type()` 은 브라우저 안에서 만들어 내는 가짜 사건이다.
페이지 입장에선 커서가 순간이동하고, 글자가 일정한 간격으로 꽂힌다. 여기서는
**운영체제의 실제 마우스를 움직이고 실제 키를 누른다.**

⚠️ **돌아가는 동안 PC 를 쓰면 안 된다.** 마우스가 진짜로 움직이므로 그 사이에
   다른 창을 누르면 클릭이 엉뚱한 곳에 꽂힌다.
⚠️ 급하면 **마우스를 화면 왼쪽 위 모서리로 밀어라.** pyautogui 가 즉시 중단시킨다
   (FAILSAFE). 이 안전장치를 끄지 말 것.

좌표 맞추기가 이 파일의 핵심이다. 브라우저가 알려주는 위치는 **페이지 안의 CSS 픽셀**이고,
마우스는 **화면의 물리 픽셀**로 움직인다. 둘 사이에 세 가지가 끼어 있다.

    화면 좌표 = (창 위치 + 주소창 높이 + 페이지 안 좌표) × 화면 배율

창 위치와 주소창 높이는 브라우저에게 물어보고(`window.screenX` 등), 배율은
`devicePixelRatio` 로 받는다. **배율을 빼먹으면 125% 화면에서 전부 어긋난다.**
"""
from __future__ import annotations

import random
import time

import pyautogui
import pygetwindow
import pyperclip
from playwright.sync_api import Page

# 사람이 버튼을 정가운데로 누르지는 않는다. 칸 안쪽에서 조금 흩어 놓는다
JITTER = 0.28
# 마우스가 목적지까지 가는 데 걸리는 시간
MOVE_SECONDS = (0.45, 1.15)

pyautogui.FAILSAFE = True
# pyautogui 가 동작마다 끼워 넣는 기본 쉼. 우리가 직접 쉬므로 0 으로 둔다
pyautogui.PAUSE = 0


def rest(low: float = 1.0, high: float = 2.0) -> float:
    """저마다 다른 시간을 쉰다 (초, 소수점)."""
    seconds = random.uniform(low, high)
    time.sleep(seconds)
    return seconds


def _frame_offset(page: Page) -> tuple[float, float, float]:
    """창 왼쪽 위 좌표와 화면 배율.

    `outerHeight - innerHeight` 가 주소창·탭바의 높이다. 가로쪽 테두리는
    요즘 크롬에서 0 이지만 계산에 넣어 둔다.
    """
    data = page.evaluate(
        """() => ({
            x: window.screenX,
            y: window.screenY,
            chromeY: window.outerHeight - window.innerHeight,
            chromeX: (window.outerWidth - window.innerWidth) / 2,
            dpr: window.devicePixelRatio || 1,
        })"""
    )
    return (
        float(data["x"]) + float(data["chromeX"]),
        float(data["y"]) + float(data["chromeY"]),
        float(data["dpr"]),
    )


def move_and_click(page: Page, selector: str, log=print) -> bool:
    """그 칸까지 마우스를 **부드럽게** 옮기고 누른다.

    칸을 못 찾거나 화면 밖이면 False 를 돌려준다 — 그때는 부르는 쪽이
    평범한 클릭으로 돌아가면 된다. 엉뚱한 곳을 누르는 것보다 낫다.
    """
    element = page.locator(selector).first
    try:
        element.wait_for(state="visible", timeout=10_000)
        element.scroll_into_view_if_needed()
        box = element.bounding_box()
    except Exception as error:
        log(f"     칸을 찾지 못했습니다 ({selector}): {type(error).__name__}")
        return False
    if not box:
        log(f"     칸이 화면에 없습니다 ({selector})")
        return False

    off_x, off_y, dpr = _frame_offset(page)

    # 칸 가운데를 기준으로 조금 흩어 놓는다 (늘 정가운데를 누르지 않게)
    cx = box["x"] + box["width"] / 2 + random.uniform(-1, 1) * box["width"] * JITTER
    cy = box["y"] + box["height"] / 2 + random.uniform(-1, 1) * box["height"] * JITTER

    screen_x = (off_x + cx) * dpr
    screen_y = (off_y + cy) * dpr

    width, height = pyautogui.size()
    if not (0 <= screen_x < width and 0 <= screen_y < height):
        log(f"     계산한 자리가 화면 밖입니다 ({screen_x:.0f}, {screen_y:.0f})")
        return False

    pyautogui.moveTo(
        screen_x,
        screen_y,
        duration=random.uniform(*MOVE_SECONDS),
        tween=pyautogui.easeInOutQuad,  # 출발·도착에서 느려지는 움직임
    )
    time.sleep(random.uniform(0.15, 0.45))  # 누르기 전 멈칫
    pyautogui.click()
    rest(0.3, 0.9)
    return True


def paste(text: str) -> None:
    """클립보드로 붙여넣는다.

    한 글자씩 치면 간격이 고르고, 한글은 조합 과정이 또 달라서 티가 난다.
    사람도 비밀번호는 붙여넣는다.

    ⚠️ **붙여넣기 전에 `ctrl+a` 로 칸을 비운다.** 칸에 뭔가 남아 있으면 뒤에 이어 붙어
    비밀번호가 엉뚱해진다. 자동완성이나 앞선 시도가 남긴 글자가 실제로 들어간다.

    동작 사이사이를 쉰다 — 복사·전체선택·붙여넣기가 한 호흡에 끝나면 사람 손이 아니다.
    """
    pyperclip.copy(text)
    rest(0.3, 0.9)
    pyautogui.hotkey("ctrl", "a")
    rest(0.3, 0.9)
    pyautogui.hotkey("ctrl", "v")
    rest(0.3, 0.9)


def focus_window(page: Page) -> None:
    """그 창을 맨 앞으로. **마우스를 움직이기 전에 반드시 부른다.**

    ⚠️ `page.bring_to_front()` 만으로는 모자라다 — 그건 크로미움 **안에서 탭만** 올린다.
    다른 프로그램 창이 앞에 있으면 클릭이 그쪽에 꽂힌다. 운영체제에게도 시켜야 한다.
    """
    try:
        page.bring_to_front()
    except Exception:
        pass

    # 창 제목은 "<페이지 제목> - Chromium" 꼴이다. 제목 앞부분으로 찾는다
    try:
        title = (page.title() or "").strip()
        for window in pygetwindow.getAllWindows():
            if title and title[:30] in window.title:
                if window.isMinimized:
                    window.restore()
                window.activate()
                break
    except Exception:
        # 창을 못 찾아도 멈추지 않는다 — 좌표가 화면 밖이면 어차피 클릭을 안 한다
        pass
    rest(0.5, 1.1)


def call_human() -> None:
    """사람을 부른다. 창을 보고 있지 않을 때 쓰라고 소리를 낸다."""
    try:
        import winsound

        for _ in range(3):
            winsound.Beep(1600, 400)
    except Exception:
        pass
