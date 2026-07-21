"""네이버 블로그 진입 및 글 작성."""
import random
import time
from typing import Callable, Tuple
import pyautogui as pg
from playwright.sync_api import (
    BrowserContext,
    Frame,
    Page,
    TimeoutError as PWTimeout,
)

LogFn = Callable[[str], None]

SHORTCUT_ITEM = ".shortcut_item"
BLOG_INDEX = 2  # 메일 / 카페 / 블로그 순서
BLOG_HOST = "blog.naver.com"

MY_BLOG_MENU = ".menu_my_blog"
WRITE_INDEX = 1  # 내 블로그 / 글쓰기 순서 (0-based)
EDITOR_FRAME = "mainFrame"
WRITE_FORM_PATH = "PostWriteForm.naver"

# 글쓰기 탭은 로딩 화면을 한 번 거친 뒤 에디터로 바뀐다.
# 그 전에 프레임을 찾으면 로딩 화면 쪽을 잡아버리므로 먼저 좀 기다린다.
EDITOR_SETTLE_SEC = 3

# 에디터 진입 직후 뜨는 '이전 작성글 복구' 팝업
POPUP_CONTAINER = ".se-popup-container"
POPUP_CANCEL = ".se-popup-button.se-popup-button-cancel"
HELP_CLOSE = ".se-help-panel-close-button"

# 제목과 본문. 둘 다 se-component 지만 제목만 se-documentTitle 이 붙는다.
TITLE_AREA = ".se-component.se-documentTitle .se-text-paragraph"
BODY_AREA = ".se-component.se-text .se-text-paragraph"

# 글자 하나 사이의 대기 시간(초). 너무 균일하면 봇으로 본다.
TYPE_DELAY = (0.3, 0.9)


def go_to_blog(context: BrowserContext, page: Page, log: LogFn = print) -> Page:
    """네이버 메인의 바로가기에서 블로그로 진입한다 (새 탭으로 열림)."""
    # 바로가기 영역은 늦게 그려지므로 나타날 때까지 기다린다.
    page.wait_for_selector(SHORTCUT_ITEM, timeout=15000)
    item = page.locator(SHORTCUT_ITEM).nth(BLOG_INDEX)

    # 광고 등으로 순서가 밀릴 수 있어 실제 링크를 확인해 둔다.
    href = item.locator("a").get_attribute("href") or ""
    if BLOG_HOST not in href:
        log(f"[경고] {BLOG_INDEX + 1}번째 바로가기가 블로그가 아닙니다: {href}")

    with context.expect_page() as popup:
        item.click()

    blog_page = popup.value
    blog_page.wait_for_load_state("domcontentloaded")
    blog_page.bring_to_front()
    log(f"블로그 진입: {blog_page.url}")
    return blog_page


def open_writer(
    context: BrowserContext, blog_page: Page, log: LogFn = print
) -> Tuple[Page, Frame]:
    """블로그 홈에서 글쓰기를 눌러 에디터를 연다 (새 탭으로 열림).

    에디터 탭과, 실제 편집이 이루어지는 mainFrame 을 함께 돌려준다.
    """
    blog_page.wait_for_selector(f"{MY_BLOG_MENU} a", timeout=15000)
    link = blog_page.locator(f"{MY_BLOG_MENU} a").nth(WRITE_INDEX)

    with context.expect_page() as popup:
        link.click()

    writer = popup.value
    writer.wait_for_load_state("domcontentloaded")
    writer.bring_to_front()

    frame = prepare_writer(writer, log=log)
    log(f"글쓰기 준비 완료: {writer.url}")
    return writer, frame


def editor_frame(writer: Page, timeout: float = 20.0) -> Frame:
    """에디터 본체는 mainFrame iframe 안에 들어 있다.

    iframe 태그가 붙은 직후에는 프레임이 아직 등록되지 않아
    page.frame() 이 None 을 돌려준다. 잡힐 때까지 폴링한다.
    """
    time.sleep(EDITOR_SETTLE_SEC)
    writer.wait_for_selector(f"iframe#{EDITOR_FRAME}", timeout=timeout * 1000)

    deadline = time.time() + timeout
    while time.time() < deadline:
        frame = writer.frame(name=EDITOR_FRAME)
        if frame is None:
            # name 이 아직 안 붙었으면 URL 로 찾는다.
            frame = next(
                (f for f in writer.frames if WRITE_FORM_PATH in (f.url or "")), None
            )
        if frame is not None:
            return frame
        time.sleep(0.3)

    raise RuntimeError("에디터 프레임(mainFrame)을 찾지 못했습니다.")


def _dismiss(frame: Frame, selector: str, label: str, log: LogFn, timeout: int) -> None:
    """있으면 닫고, 없으면 조용히 넘어간다."""
    target = frame.locator(selector).first
    try:
        target.wait_for(state="visible", timeout=timeout)
    except PWTimeout:
        return
    target.click()
    log(label)


def prepare_writer(writer: Page, log: LogFn = print) -> Frame:
    """에디터 진입 직후 뜨는 방해 요소를 정리하고 편집 프레임을 돌려준다.

    팝업들이 모두 mainFrame 안에 있어서 페이지가 아니라 프레임에서 찾아야 한다.
    """

    frame = editor_frame(writer)
    frame.wait_for_selector(".se-documentTitle", timeout=15000)

    # 팝업이 떠 있으면 '취소' 를 눌러 새 글로 시작한다.
    popup = frame.locator(POPUP_CONTAINER).first
    try:
        popup.wait_for(state="visible", timeout=3000)
    except PWTimeout:
        pass
    else:
        popup.locator(POPUP_CANCEL).first.click()
        log("팝업 닫음 (취소)")

    # 도움말 레이어
    _dismiss(frame, HELP_CLOSE, "도움말 레이어 닫음", log, 2000)

    return frame


def _pause() -> None:
    """사람이 치는 것처럼 보이도록 매번 다른 시간을 쉰다."""
    time.sleep(random.uniform(*TYPE_DELAY))


def _type_text(writer: Page, frame: Frame, selector: str, text: str) -> None:
    """에디터 영역을 클릭한 뒤 한 글자씩 입력한다.

    contenteditable 이라 fill() 이 안 먹는다. 줄 끝마다 엔터를 눌러
    다음 줄로 넘어간다. 키 입력은 프레임이 아니라 페이지에 보낸다.
    """
    target = frame.locator(selector).first
    target.wait_for(state="visible", timeout=10000)
    target.click()
    _pause()

    lines = text.splitlines()
    for i, line in enumerate(lines):
        for ch in line:
            writer.keyboard.type(ch)
            _pause()

        # 마지막 줄 뒤에는 빈 줄을 만들지 않는다.
        if i < len(lines) - 1:
            writer.keyboard.press("Enter")
            _pause()


def write_post(
    writer: Page, frame: Frame, title: str, body: str, log: LogFn = print
) -> None:
    """제목과 본문을 입력한다. 발행은 하지 않는다."""
    log(f"제목 입력 중: {title}")
    _type_text(writer, frame, TITLE_AREA, title)

    lines = len(body.splitlines())
    log(f"본문 입력 중: {lines}줄")
    _type_text(writer, frame, BODY_AREA, body)

    log("작성 완료")
