"""실제 작업이 이루어지는 곳.

GUI(main.py)는 여기 있는 Workspace 를 별도 스레드에서 돌리기만 한다.
"""
import threading
from pathlib import Path
from typing import Callable, Optional

from playwright.sync_api import BrowserContext, Frame, Page

from ai_generator import generate_body
from config import Account, load_account
from naver_blog import go_to_blog, open_writer, write_post
from naver_login import login
from title_generator import generate_title
from work_subject import Subject, load_subjects, save_subjects

LogFn = Callable[[str], None]

# 본문의 img_line 마커가 참조할 파일들이 놓인 폴더.
# 지금 AI 본문에는 마커가 안 들어가지만 write_post 시그니처가 요구하므로 유지.
SAMPLE_IMAGE_DIR = Path(__file__).parent / "sample_image"


class Workspace:
    """계정 하나에 대한 브라우저 세션 + 작업 묶음."""

    def __init__(
        self,
        account: Optional[Account] = None,
        log: LogFn = print,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        # account 를 주지 않으면 기본 소스(id_pwd.txt)에서 읽는다.
        # 나중에 서버 관리로 바뀌면 이 부분만 교체하면 된다.
        self.account = account or load_account()
        self.log = log
        self.stop_event = stop_event or threading.Event()

        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.blog_page: Optional[Page] = None
        self.writer_page: Optional[Page] = None
        self.editor: Optional[Frame] = None  # 실제 편집이 일어나는 mainFrame

        # 이번 실행의 작성 대상. prepare_subject 로 채워진다.
        self.subject: Optional[Subject] = None
        self.body_text: str = ""

    # ------------------------------------------------------------------
    # 개별 작업
    # ------------------------------------------------------------------
    def do_login(self) -> None:
        self.page = login(self.context, self.account, log=self.log)
        self.log(f"현재 페이지: {self.page.url}")

    def open_blog(self) -> None:
        self.blog_page = go_to_blog(self.context, self.page, log=self.log)

    def open_writer_tab(self) -> None:
        self.writer_page, self.editor = open_writer(
            self.context, self.blog_page, log=self.log
        )

    def prepare_subject(self) -> None:
        """work_subject.txt 에서 항목들을 읽고 빈 제목을 채운 뒤 첫 항목을 고른다.

        생성된 제목은 파일에 다시 써서 다음 실행에서 재생성하지 않게 한다.
        """
        subjects = load_subjects()
        if not subjects:
            raise RuntimeError("work_subject.txt 에 주제가 없습니다.")

        changed = False
        for s in subjects:
            if not s.title:
                self.log(f"[제목 생성] 카테고리={s.category}")
                s.title = generate_title(s.category)
                self.log(f"[제목 생성] → {s.title}")
                changed = True
        if changed:
            save_subjects(subjects)
            self.log("work_subject.txt 갱신")

        self.subject = subjects[0]
        self.log(f"작성 대상: [{self.subject.category}] {self.subject.title}")

    def prepare_body(self) -> None:
        """Perplexity 로 본문 텍스트를 생성한다."""
        assert self.subject is not None, "prepare_subject 를 먼저 호출해야 합니다."
        self.body_text = generate_body(
            self.subject.title, self.subject.category, log=self.log
        )

    def write_post(self) -> None:
        """제목/본문을 입력한다. 발행은 아직 하지 않는다."""
        assert self.subject is not None and self.body_text, "본문 준비가 먼저 필요합니다."
        write_post(
            self.writer_page,
            self.editor,
            self.subject.title,
            self.body_text,
            SAMPLE_IMAGE_DIR,
            log=self.log,
        )

    # ------------------------------------------------------------------
    # 실행 흐름
    # ------------------------------------------------------------------
    def run(self) -> None:
        """지금은 제목 품질 확인 단계. 제목만 뽑고 끝낸다.

        본문 생성/브라우저 로그인/글 작성은 임시 비활성화. 다시 살릴 때
        prepare_body / write_post 를 launch_context 아래에서 호출하면 됨.
        """
        self.log(f"프로필: {self.account.profile}")

        try:
            self.prepare_subject()
            self.log("제목 생성 완료. (본문/발행 흐름은 임시 비활성화)")
        except Exception as exc:
            self.log(f"[오류] {type(exc).__name__}: {exc}")
            raise


def run_workspace(
    log: LogFn = print,
    stop_event: Optional[threading.Event] = None,
    account: Optional[Account] = None,
) -> None:
    """GUI 등 외부에서 호출하는 진입 함수."""
    Workspace(account=account, log=log, stop_event=stop_event).run()


if __name__ == "__main__":
    # GUI 없이 단독 실행 (Ctrl+C 로 종료)
    event = threading.Event()
    try:
        run_workspace(stop_event=event)
    except KeyboardInterrupt:
        event.set()
