"""네이버 블로그 진입 및 글 작성."""
import random
import time
import traceback
from pathlib import Path
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
TYPE_DELAY = (0.05, 0.35)

# SE 상단 툴바(.se-toolbar.se-document-toolbar) 내부의 li 들이 각각 툴바 버튼이며,
# 첫 번째 li 가 이미지 삽입이다. 클릭하면 OS 파일 열기 다이얼로그가 뜬다.
IMAGE_BUTTON = ".se-toolbar.se-document-toolbar li:first-child"

# 이미지가 에디터에 실제로 삽입됐는지 확인하는 셀렉터.
# 이미지 하나당 .se-image-resource 하나가 붙는다.
IMAGE_INSERTED = ".se-image-resource"

# 한글 Windows 의 파일 열기 다이얼로그 창 제목.
FILE_DIALOG_TITLE = "열기"
FILE_DIALOG_OPEN_TIMEOUT = 10   # 클릭 후 다이얼로그가 뜰 때까지
FILE_DIALOG_CLOSE_TIMEOUT = 10  # Enter 후 다이얼로그가 닫힐 때까지
IMAGE_UPLOAD_TIMEOUT = 60       # 다이얼로그 닫힌 뒤 실제 업로드까지 (네트워크 감안)

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


def _dialog_open(title: str = FILE_DIALOG_TITLE) -> bool:
    """제목이 일치하는 OS 창이 하나라도 있는지 검사한다.

    getWindowsWithTitle 은 부분 일치를 지원하지만 다른 창이 잡히지 않도록
    완전 일치로 좁힌다.
    """
    return any((w.title or "") == title for w in pg.getWindowsWithTitle(title))


def _wait_for_dialog_open(
    log: LogFn, title: str = FILE_DIALOG_TITLE, timeout: int = FILE_DIALOG_OPEN_TIMEOUT
) -> None:
    """OS 파일 열기 다이얼로그가 뜰 때까지 기다린다."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _dialog_open(title):
            log(f"[체크1] 파일 다이얼로그 '{title}' 열림 확인")
            return
        time.sleep(0.2)
    raise RuntimeError(
        f"파일 다이얼로그 '{title}' 가 {timeout}초 안에 뜨지 않았습니다."
    )


def _wait_for_dialog_close(
    log: LogFn, title: str = FILE_DIALOG_TITLE, timeout: int = FILE_DIALOG_CLOSE_TIMEOUT
) -> None:
    """OS 파일 열기 다이얼로그가 닫힐 때까지 기다린다."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _dialog_open(title):
            log(f"[체크2] 파일 다이얼로그 '{title}' 닫힘 확인")
            return
        time.sleep(0.3)
    raise RuntimeError(
        f"파일 다이얼로그 '{title}' 가 {timeout}초 안에 닫히지 않았습니다."
    )


def _insert_image(frame: Frame, image_path: Path, log: LogFn) -> None:
    """SE 툴바의 '사진' 버튼을 눌러 이미지를 삽입한다.

    각 단계마다 상태를 확인해서 인터넷/OS 지연이 있어도 다음 단계로 성급히
    넘어가지 않는다:
      1) 툴바 버튼 클릭 후 파일 다이얼로그가 실제로 떴는지
      2) 경로 입력 + Enter 후 다이얼로그가 실제로 닫혔는지
      3) 에디터의 .se-image-resource 갯수가 기대만큼 늘었는지

    실패 시 pg.alert 으로 실행을 멈추므로, 알럿이 떠 있는 동안 브라우저에서
    실제 DOM 을 확인해 셀렉터를 잡을 수 있다.
    """
    try:
        if not image_path.exists():
            raise FileNotFoundError(f"이미지 파일이 없음: {image_path}")

        path_str = str(image_path.resolve())
        log(f"이미지 삽입: {image_path.name}")

        button = frame.locator(IMAGE_BUTTON).first
        button.wait_for(state="visible", timeout=5000)

        # 삽입 전 이미지 개수를 기록해 두면 업로드 완료 시점을 알 수 있다.
        before = frame.locator(IMAGE_INSERTED).count()
        expected = before + 1

        # (1) 클릭 → 파일 다이얼로그가 뜰 때까지 대기.
        button.click()
        _wait_for_dialog_open(log)

        # (2) 기본값이 채워져 있을 수 있어 전체 선택 후 덮어쓴다.
        #     Enter 후 다이얼로그가 닫힐 때까지 대기.
        pg.hotkey("ctrl", "a")
        time.sleep(0.1)
        pg.write(path_str, interval=0.02)
        time.sleep(0.3)
        pg.press("enter")
        _wait_for_dialog_close(log)

        # (3) 실제로 이미지가 붙었는지 갯수로 확인.
        deadline = time.time() + IMAGE_UPLOAD_TIMEOUT
        while time.time() < deadline:
            current = frame.locator(IMAGE_INSERTED).count()
            if current >= expected:
                log(f"[체크3] 이미지 삽입 확인 ({before} → {current})")
                _pause()
                return
            time.sleep(0.3)
        current = frame.locator(IMAGE_INSERTED).count()
        raise RuntimeError(
            f"이미지가 {IMAGE_UPLOAD_TIMEOUT}초 안에 붙지 않았습니다 "
            f"(기대 {expected}개, 현재 {current}개)"
        )
    except Exception as exc:
        tb = traceback.format_exc()
        log(tb)
        pg.alert(
            text=(
                "이미지 삽입 실패\n"
                "파일: naver_blog.py\n"
                "함수: _insert_image\n"
                f"IMAGE_BUTTON = {IMAGE_BUTTON!r}\n"
                f"IMAGE_INSERTED = {IMAGE_INSERTED!r}\n\n"
                f"{type(exc).__name__}: {exc}\n\n"
                "이 창이 떠 있는 동안 브라우저에서 DOM 을 확인하세요.\n"
                "[OK] 를 누르면 브라우저가 닫히고 종료됩니다."
            ),
            title="이미지 삽입 실패",
        )
        raise


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
    _pause()

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

    lines = len(body.splitlines())
    log(f"본문 입력 중: {lines}줄")
    _type_body(writer, frame, body, image_dir, log)

    log("작성 완료")
