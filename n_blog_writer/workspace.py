"""실제 작업이 이루어지는 곳.

GUI(main.py)는 여기 있는 Workspace 를 별도 스레드에서 돌리기만 한다.
"""
import threading
from typing import Callable, Optional

from playwright.sync_api import BrowserContext, Frame, Page

from browser import launch_context
from config import Account, load_account
from naver_blog import go_to_blog, open_writer
from naver_login import login

LogFn = Callable[[str], None]


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

    def write_post(self) -> None:
        """제목/본문 입력 및 발행 (다음 단계에서 구현)."""
        self.log("글 작성 기능은 아직 준비 중입니다.")

    # ------------------------------------------------------------------
    # 실행 흐름
    # ------------------------------------------------------------------
    def run(self) -> None:
        self.log(f"프로필: {self.account.profile}")
        self.log(f"경로: {self.account.profile_dir}")

        try:
            with launch_context(self.account.profile_dir) as context:
                self.context = context
                self.do_login()
                self.open_blog()
                self.open_writer_tab()
                self.log("작업 준비 완료. 중지를 누르면 브라우저를 닫습니다.")

                # 중지 신호가 올 때까지 브라우저를 열어 둔다.
                self.stop_event.wait()
                self.log("브라우저를 닫는 중...")
        except Exception as exc:  # GUI 로 원인을 그대로 전달
            self.log(f"[오류] {type(exc).__name__}: {exc}")
            raise
        finally:
            self.context = None
            self.page = None
            self.blog_page = None
            self.writer_page = None
            self.editor = None


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
