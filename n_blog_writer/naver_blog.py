"""네이버 블로그 진입 및 글 작성."""
import random
import threading
import time
from pathlib import Path
from typing import Callable, Tuple
from playwright.sync_api import (
    BrowserContext,
    Error as PWError,
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
TYPE_DELAY = (0.05, 0.35)

# 섹션 전환(제목 → 본문 클릭 → 본문 타이핑) 사이의 여유 대기.
SECTION_DELAY = (1.5, 2.5)

# SE 상단 툴바(.se-toolbar.se-document-toolbar) 내부의 li 들이 각각 툴바 버튼이며,
# 첫 번째 li 가 이미지 삽입이다. 클릭하면 OS 파일 열기 다이얼로그가 뜬다.
IMAGE_BUTTON = ".se-toolbar.se-document-toolbar li:first-child"

# 이미지가 에디터에 실제로 삽입됐는지 확인하는 셀렉터.
# 이미지 하나당 .se-image-resource 하나가 붙는다.
IMAGE_INSERTED = ".se-image-resource"

IMAGE_UPLOAD_TIMEOUT = 60  # 파일 지정 후 실제 업로드까지 (네트워크 감안)

# 발행: 상단 '발행' 버튼이 설정 레이어를 열고, 레이어 안의 '발행' 이 최종 확정이다.
PUBLISH_BUTTON = 'button:has-text("발행")'
PUBLISH_TIMEOUT = 60  # 확정 후 에디터를 벗어날 때까지

# 본문 라인의 마커. 라인 전체가 이 접두사로 시작하면 특수 처리한다.
IMG_MARKER = "img_line|"     # img_line|파일명.jpg
LINK_MARKER = "link_line|"   # link_line|url|표시텍스트

# 링크 관련 셀렉터
LINK_TOOLBAR_BUTTON = ".se-link-toolbar-button"     # 텍스트에 링크 걸 때 클릭
LINK_INPUT = ".se-custom-layer-link-input"          # 링크 입력 팝업
OGLINK_FRAME = ".se-oglink-frame"                   # 자동 생성된 프리뷰 박스
DELETE_TOOLBAR_BUTTON = ".se-delete-toolbar-button" # 박스 삭제 툴바 (두 개 뜨면 마지막)

# link_line 의 세 번째 필드가 이 값이면 특수 모드. 그 외는 표시 텍스트.
LINK_MODE_BOX = "onbox"      # URL + Enter → 프리뷰 박스 유지
LINK_MODE_NOBOX = "nobox"    # URL + Enter → 뜬 박스 제거


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


def _section_pause() -> None:
    """제목/본문 클릭/본문 타이핑 등 큰 단계 사이의 여유 대기."""
    time.sleep(random.uniform(*SECTION_DELAY))


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


def _insert_image(frame: Frame, image_path: Path, log: LogFn) -> None:
    """SE 툴바의 '사진' 버튼을 눌러 이미지를 삽입한다.

    파일 선택창은 Playwright 가 가로채므로 OS 창이 뜨지 않고 PC 를 점유하지 않는다.
    업로드 완료는 에디터의 .se-image-resource 갯수가 늘었는지로 확인한다.
    """
    if not image_path.exists():
        raise FileNotFoundError(f"이미지 파일이 없음: {image_path}")

    log(f"이미지 삽입: {image_path.name}")

    button = frame.locator(IMAGE_BUTTON).first
    button.wait_for(state="visible", timeout=5000)

    before = frame.locator(IMAGE_INSERTED).count()
    expected = before + 1

    with frame.page.expect_file_chooser(timeout=10000) as chooser:
        button.click()
    chooser.value.set_files(str(image_path.resolve()))

    deadline = time.time() + IMAGE_UPLOAD_TIMEOUT
    while time.time() < deadline:
        current = frame.locator(IMAGE_INSERTED).count()
        if current >= expected:
            log(f"이미지 삽입 확인 ({before} → {current})")
            _pause()
            return
        frame.page.wait_for_timeout(300)
    current = frame.locator(IMAGE_INSERTED).count()
    raise RuntimeError(
        f"이미지가 {IMAGE_UPLOAD_TIMEOUT}초 안에 붙지 않았습니다 "
        f"(기대 {expected}개, 현재 {current}개)"
    )


def _type_chars(writer: Page, text: str) -> None:
    """사람 흉내로 한 글자씩 타이핑."""
    for ch in text:
        writer.keyboard.type(ch)
        _pause()


def _insert_link_with_text(
    writer: Page, frame: Frame, url: str, text: str, log: LogFn
) -> None:
    """표시 텍스트에 링크를 걸어 삽입한다.

    텍스트 입력 → 방금 입력한 문자 수만큼 Shift+ArrowLeft 로 선택 →
    링크 툴바 버튼 클릭 → 링크 입력 팝업의 input 에 URL 입력 → Enter 로 확정.
    확정 후에는 텍스트가 선택된 상태로 남으므로 ArrowRight 로 블록을 풀고
    Enter 로 다음 문단으로 넘어간다.
    """
    log(f"링크 삽입 (텍스트): '{text}' → {url}")
    _type_chars(writer, text)

    for _ in range(len(text)):
        writer.keyboard.press("Shift+ArrowLeft")
    _pause()

    frame.locator(LINK_TOOLBAR_BUTTON).first.click()
    popup = frame.locator(LINK_INPUT).first
    popup.wait_for(state="visible", timeout=5000)
    popup.click()  # 입력창 명시적 포커스
    _pause()

    _type_chars(writer, url)
    writer.keyboard.press("Enter")
    _pause()

    writer.keyboard.press("ArrowRight")
    _pause()
    writer.keyboard.press("Enter")
    _pause()


def _insert_link_with_preview(writer: Page, url: str, log: LogFn) -> None:
    """URL + Enter 로 오글링크 프리뷰 박스가 자동 생성되게 한다."""
    log(f"링크 삽입 (프리뷰): {url}")
    _type_chars(writer, url)
    writer.keyboard.press("Enter")
    _pause()


def _remove_oglink_box(frame: Frame, log: LogFn) -> None:
    """방금 생긴 프리뷰 박스를 클릭해 삭제 툴바를 띄운 뒤 지운다.

    박스를 클릭하면 삭제 버튼이 두 개 뜨는데 마지막 것이 박스 삭제다.
    """
    log("링크 프리뷰 박스 제거")
    box = frame.locator(OGLINK_FRAME).last
    box.wait_for(state="visible", timeout=15000)
    box.click()
    _pause()

    del_btn = frame.locator(DELETE_TOOLBAR_BUTTON).last
    del_btn.wait_for(state="visible", timeout=5000)
    del_btn.click()
    _pause()


def _insert_link(
    writer: Page, frame: Frame, url: str, mode: str, log: LogFn
) -> None:
    """link_line 처리. 세 모드 모두 내부에서 커서를 다음 문단으로 옮겨 둔다."""
    if mode == LINK_MODE_BOX:
        _insert_link_with_preview(writer, url, log)
        return
    if mode == LINK_MODE_NOBOX:
        _insert_link_with_preview(writer, url, log)
        _remove_oglink_box(frame, log)
        return
    _insert_link_with_text(writer, frame, url, mode, log)


def _type_body(
    writer: Page,
    frame: Frame,
    body: str,
    image_dir: Path,
    log: LogFn,
) -> None:
    """본문 입력. 마커 라인은 특수 처리한다.

    - 시작할 때 Ctrl+Alt+C 로 가운데 정렬을 켜서 본문 전체가 가운데 정렬된다.
    - img_line|파일명 라인은 이미지 삽입으로 대체된다.
    - link_line|url|모드 라인은 링크 삽입으로 대체된다.
        모드가 onbox 면 프리뷰 박스 유지, nobox 면 박스 제거, 그 외는
        해당 값을 표시 텍스트로 써서 텍스트-링크를 만든다.
    """
    target = frame.locator(BODY_AREA).first
    target.wait_for(state="visible", timeout=10000)
    target.click()
    _pause()

    # 본문 전체 가운데 정렬 (한 번 켜두면 이후 문단도 따라간다)
    writer.keyboard.press("Control+Alt+c")

    # 정렬 반영이 눈에 보일 시간, 그리고 사람이 잠깐 생각하는 척.
    _section_pause()

    lines = body.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        press_enter = i < len(lines) - 1

        if stripped.startswith(IMG_MARKER):
            filename = stripped[len(IMG_MARKER):].strip()
            _insert_image(frame, image_dir / filename, log)
            # 이미지 삽입 후 SE 가 자동으로 다음 문단을 만들어주므로 Enter 를
            # 추가로 누르면 빈 줄이 생긴다.
            press_enter = False
        elif stripped.startswith(LINK_MARKER):
            fields = stripped[len(LINK_MARKER):].split("|", 1)
            if len(fields) != 2:
                log(f"[스킵] 잘못된 link_line 형식: {stripped}")
            else:
                url, mode = fields[0].strip(), fields[1].strip()
                _insert_link(writer, frame, url, mode, log)
            # 링크 처리가 내부적으로 다음 문단까지 커서를 옮기므로 Enter 불필요.
            press_enter = False
        else:
            _type_chars(writer, line)

        if press_enter:
            writer.keyboard.press("Enter")
            _pause()


def write_post(
    writer: Page,
    frame: Frame,
    title: str,
    body: str,
    image_dir: Path,
    log: LogFn = print,
) -> None:
    """제목과 본문을 입력한다. 발행은 하지 않는다."""
    log(f"제목 입력 중: {title}")
    _type_text(writer, frame, TITLE_AREA, title)

    # 제목 → 본문 이동 전 잠깐 쉼.
    _section_pause()

    lines = len(body.splitlines())
    log(f"본문 입력 중: {lines}줄")
    _type_body(writer, frame, body, image_dir, log)

    log("작성 완료")


def _left_editor(writer: Page) -> bool:
    """탭이 닫혔거나 글쓰기 화면을 벗어났으면 True (발행되면 글 보기로 바뀐다)."""
    if writer.is_closed():
        return True
    return not any(WRITE_FORM_PATH in (f.url or "") for f in writer.frames)


def publish_post(writer: Page, frame: Frame, log: LogFn = print) -> None:
    """발행 레이어를 열고 확정한 뒤, 실제로 에디터를 벗어났는지 확인한다."""
    buttons = frame.locator(PUBLISH_BUTTON)
    buttons.first.wait_for(state="visible", timeout=10000)
    before = buttons.count()
    buttons.first.click()

    # 레이어가 열리면 '발행' 버튼이 하나 늘어난다. 마지막 것이 최종 확정이다.
    deadline = time.time() + 10
    while buttons.count() <= before:
        if time.time() >= deadline:
            raise RuntimeError("발행 설정 레이어가 열리지 않았습니다.")
        writer.wait_for_timeout(200)
    _section_pause()
    buttons.last.click()

    deadline = time.time() + PUBLISH_TIMEOUT
    while time.time() < deadline:
        if _left_editor(writer):
            log("발행 완료")
            return
        writer.wait_for_timeout(500)
    raise RuntimeError(f"{PUBLISH_TIMEOUT}초 안에 발행이 끝나지 않았습니다.")


def wait_for_manual_publish(
    writer: Page, stop_event: threading.Event, log: LogFn = print
) -> bool:
    """테스트 모드: 사람이 브라우저에서 확인하고 발행할 때까지 기다린다.

    발행되면 True, 중지를 눌렀으면 False. 발행하지 않고 넘어가려면 탭을 닫으면
    되는데, 탭이 닫힌 경우 발행 여부를 알 수 없으므로 False 로 본다.
    """
    log("[테스트] 내용을 확인하고 직접 발행하세요. 건너뛰려면 글쓰기 탭을 닫으세요.")
    while not stop_event.is_set():
        try:
            if writer.is_closed():
                log("[테스트] 탭 닫힘: 발행 안 한 것으로 처리")
                return False
            if _left_editor(writer):
                log("[테스트] 발행 확인")
                return True
            writer.wait_for_timeout(500)
        except PWError:
            # 대기 중 탭이 닫히면 Playwright 예외가 난다. 다음 루프에서 판정한다.
            time.sleep(0.2)
    return False
