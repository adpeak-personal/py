"""실제 작업이 이루어지는 곳.

GUI(main.py)는 여기 있는 Workspace 를 별도 스레드에서 돌리기만 한다.
"""
import threading
from typing import Callable, List, Optional, Set

from playwright.sync_api import BrowserContext, Frame, Page

from ai_generator import generate_body
from browser import launch_context
from config import IMAGE_DIR, PUBLISHED_FILE, Account, load_account
from naver_blog import (
    go_to_blog,
    open_writer,
    publish_post,
    wait_for_manual_publish,
    write_post,
)
from naver_login import login
from title_generator import (
    extract_keyword,
    generate_title,
    generate_title_from_keyword,
)
from work_subject import Subject, load_subjects, save_subjects

LogFn = Callable[[str], None]


class Workspace:
    """계정 하나에 대한 브라우저 세션 + 작업 묶음."""

    def __init__(
        self,
        account: Optional[Account] = None,
        log: LogFn = print,
        stop_event: Optional[threading.Event] = None,
        test_mode: bool = False,
    ) -> None:
        self.test_mode = test_mode  # True 면 사람이 확인 후 직접 발행
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

        # prepare_subjects 로 채워진다.
        self.subjects: List[Subject] = []

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

    def prepare_subjects(self) -> None:
        """work_subject.txt 를 읽어 빈 제목/키워드를 채우고 처리 가능한 항목을 self.subjects 에 담는다.

        - cate1/cate2: 제목이 비면 생성, 그다음 키워드도 자동 추출
        - cate3/cate4: 키워드가 비면 스킵, 제목이 비면 키워드 기반으로 생성

        채워진 최신 상태는 파일에 다시 써서 다음 실행에서 재생성하지 않게 한다.
        """
        subjects = load_subjects()
        if not subjects:
            raise RuntimeError("work_subject.txt 에 주제가 없습니다.")

        changed = False
        processable: List[Subject] = []
        for s in subjects:
            try:
                if s.category in ("cate1", "cate2"):
                    if not s.title:
                        self.log(f"[제목 생성] {s.category}")
                        s.title = generate_title(s.category)
                        self.log(f"[제목 생성] → {s.title}")
                        changed = True
                    if not s.keyword:
                        self.log(f"[키워드 추출] {s.title}")
                        s.keyword = extract_keyword(s.title, s.category)
                        self.log(f"[키워드 추출] → {s.keyword}")
                        changed = True
                elif s.category in ("cate3", "cate4"):
                    if not s.keyword:
                        self.log(f"[스킵] {s.category}: 키워드 미입력")
                        continue
                    if not s.title:
                        self.log(f"[제목 생성] {s.category} 키워드={s.keyword}")
                        s.title = generate_title_from_keyword(s.category, s.keyword)
                        self.log(f"[제목 생성] → {s.title}")
                        changed = True
                else:
                    self.log(f"[스킵] 알 수 없는 카테고리: {s.category}")
                    continue
                processable.append(s)
            except Exception as exc:
                self.log(f"[스킵] 처리 실패 ({s.category}): {type(exc).__name__}: {exc}")

        if changed:
            save_subjects(subjects)
            self.log("work_subject.txt 갱신")

        if not processable:
            raise RuntimeError("처리 가능한 주제가 없습니다.")

        self.subjects = processable
        self.log(f"처리 대상 {len(processable)}건")

    # ------------------------------------------------------------------
    # 실행 흐름
    # ------------------------------------------------------------------
    @staticmethod
    def _published_titles() -> Set[str]:
        if not PUBLISHED_FILE.exists():
            return set()
        return set(PUBLISHED_FILE.read_text(encoding="utf-8").splitlines())

    @staticmethod
    def _mark_published(title: str) -> None:
        PUBLISHED_FILE.parent.mkdir(parents=True, exist_ok=True)
        with PUBLISHED_FILE.open("a", encoding="utf-8") as f:
            f.write(title + "\n")

    def _post_one(self, s: Subject) -> None:
        """글 하나를 생성·입력하고 모드에 맞게 발행한다."""
        body = generate_body(s.title, s.category, log=self.log)
        self.open_writer_tab()
        write_post(
            self.writer_page, self.editor, s.title, body, IMAGE_DIR, log=self.log
        )

        if self.test_mode:
            published = wait_for_manual_publish(
                self.writer_page, self.stop_event, log=self.log
            )
        else:
            publish_post(self.writer_page, self.editor, log=self.log)
            published = True

        if published:
            self._mark_published(s.title)

    def run(self) -> None:
        """주제마다 본문 생성 → 에디터 입력 → 발행. 이미 발행한 제목은 건너뛴다."""
        mode = "테스트 (확인 후 직접 발행)" if self.test_mode else "자동 발행"
        self.log(f"프로필: {self.account.profile} / 모드: {mode}")

        try:
            self.prepare_subjects()
        except Exception as exc:
            self.log(f"[오류] {type(exc).__name__}: {exc}")
            raise

        done = self._published_titles()
        targets = [s for s in self.subjects if s.title not in done]
        if len(targets) < len(self.subjects):
            self.log(f"이미 발행한 {len(self.subjects) - len(targets)}건 제외")
        if not targets:
            self.log("발행할 주제가 없습니다.")
            return

        with launch_context(self.account.profile_dir) as context:
            self.context = context
            self.do_login()
            self.open_blog()

            total = len(targets)
            for i, s in enumerate(targets, 1):
                if self.stop_event.is_set():
                    self.log("[중지] 사용자 요청")
                    break
                self.log(f"--- [{i}/{total}] [{s.category}] {s.title}")
                try:
                    self._post_one(s)
                except Exception as exc:
                    self.log(f"[실패] {type(exc).__name__}: {exc}")

        self.log("모든 작업 완료")


def run_workspace(
    log: LogFn = print,
    stop_event: Optional[threading.Event] = None,
    account: Optional[Account] = None,
    test_mode: bool = False,
) -> None:
    """GUI 등 외부에서 호출하는 진입 함수."""
    Workspace(
        account=account, log=log, stop_event=stop_event, test_mode=test_mode
    ).run()


if __name__ == "__main__":
    # GUI 없이 단독 실행 (Ctrl+C 로 종료)
    event = threading.Event()
    try:
        run_workspace(stop_event=event)
    except KeyboardInterrupt:
        event.set()
