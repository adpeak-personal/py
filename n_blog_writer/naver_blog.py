"""네이버 블로그 진입 및 글 작성."""
import time
from typing import Callable, Tuple

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

    # 이전 작성분 복구 팝업 -> '취소' (새 글로 시작)
    _dismiss(frame, ".se-popup-button-cancel", "이전 작성글 복구 팝업 닫음", log, 3000)
    # 도움말 레이어
    _dismiss(frame, ".se-help-panel-close-button", "도움말 레이어 닫음", log, 2000)

    return frame
