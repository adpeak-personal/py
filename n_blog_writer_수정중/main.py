"""네이버 블로그 글 작성기 - GUI.

실제 작업은 전부 workspace.py 에서 이루어진다.
여기서는 시작/중지 버튼과 로그 출력만 담당한다.
"""
import queue
import threading
import tkinter as tk
from tkinter import scrolledtext

from workspace import run_workspace


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("네이버 블로그 글 작성기")
        root.geometry("560x360")

        self.messages: "queue.Queue[str]" = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None

        bar = tk.Frame(root)
        bar.pack(fill="x", padx=10, pady=10)

        self.start_btn = tk.Button(bar, text="시작", width=12, command=self.start)
        self.start_btn.pack(side="left")

        self.stop_btn = tk.Button(
            bar, text="중지", width=12, command=self.stop, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=(8, 0))

        self.status = tk.Label(bar, text="대기 중", anchor="w")
        self.status.pack(side="left", padx=(12, 0))

        self.log_box = scrolledtext.ScrolledText(root, state="disabled", height=16)
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.drain_messages)

    # ------------------------------------------------------------------
    # 로그: 워커 스레드 -> 큐 -> GUI 스레드
    # ------------------------------------------------------------------
    def log(self, message: str) -> None:
        self.messages.put(message)

    def drain_messages(self) -> None:
        while True:
            try:
                message = self.messages.get_nowait()
            except queue.Empty:
                break
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        if self.worker and not self.worker.is_alive():
            self.worker = None
            self.on_finished()

        self.root.after(100, self.drain_messages)

    # ------------------------------------------------------------------
    # 버튼 동작
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self.worker:
            return

        self.stop_event.clear()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status.configure(text="실행 중")

        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def _run(self) -> None:
        try:
            run_workspace(log=self.log, stop_event=self.stop_event)
        except Exception:
            pass  # 원인은 workspace 쪽에서 이미 로그로 남긴다

    def stop(self) -> None:
        self.stop_event.set()
        self.stop_btn.configure(state="disabled")
        self.status.configure(text="종료 중...")

    def on_finished(self) -> None:
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status.configure(text="대기 중")

    def on_close(self) -> None:
        self.stop_event.set()
        self.root.after(300, self.root.destroy)


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()


