"""블로그 작업기 — 간단한 화면.

하는 일은 `run_login.py` 와 똑같다. 여기서는 **버튼과 로그 상자만** 맡는다.
작업 코드가 화면을 모르게 두려고, `run_login` 의 `say`/`ask`/`stop_flag` 고리에
이 창의 것을 끼워 넣는 방식이다.

    .venv\\Scripts\\pythonw.exe gui.py      (검은 창 없이)
    .venv\\Scripts\\python.exe  gui.py      (터미널도 같이 보고 싶을 때)

⚠️ **작업이 도는 동안 PC 를 쓰면 안 된다.** 진짜 마우스가 움직인다.
   급하면 마우스를 화면 **왼쪽 위 모서리**로 밀면 즉시 멈춘다(pyautogui 안전장치).
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import run_login
from config import Settings
from zzikko import Zzikko, ZzikkoError

ALL = "(쓰는 프로필 전부)"


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("블로그 작업기")
        root.geometry("760x520")
        root.minsize(620, 420)

        # 워커 스레드 → 큐 → 화면 스레드. tkinter 는 다른 스레드에서 못 건드린다
        self.lines: "queue.Queue[str]" = queue.Queue()
        self.stop = threading.Event()
        self.worker: threading.Thread | None = None
        # 사람에게 물을 때 쓰는 자리 (워커가 걸어 두고 기다린다)
        self.answered = threading.Event()

        bar = tk.Frame(root)
        bar.pack(fill="x", padx=10, pady=(10, 6))

        tk.Label(bar, text="프로필").pack(side="left")
        self.profile = ttk.Combobox(bar, width=22, state="readonly", values=[ALL])
        self.profile.set(ALL)
        self.profile.pack(side="left", padx=(6, 10))

        tk.Button(bar, text="목록 새로고침", command=self.load_profiles).pack(side="left")

        self.shot = tk.BooleanVar(value=False)
        self.keep = tk.BooleanVar(value=False)
        tk.Checkbutton(bar, text="화면 남기기", variable=self.shot).pack(side="left", padx=(12, 0))
        tk.Checkbutton(bar, text="창 열어두기", variable=self.keep).pack(side="left")

        run = tk.Frame(root)
        run.pack(fill="x", padx=10)
        self.start_btn = tk.Button(run, text="로그인 시작", width=14, command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = tk.Button(run, text="중지", width=10, command=self.ask_stop, state="disabled")
        self.stop_btn.pack(side="left", padx=(8, 0))
        tk.Button(run, text="IP 확인", width=10, command=self.check_ip).pack(side="left", padx=(8, 0))
        self.status = tk.Label(run, text="대기 중", anchor="w", fg="#666")
        self.status.pack(side="left", padx=(12, 0))

        self.log_box = scrolledtext.ScrolledText(root, state="disabled", height=20, font=("Consolas", 9))
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.drain)
        self.log("찍고에서 프로필을 받아옵니다…")
        self.load_profiles()

    # ── 로그 ───────────────────────────────────────────
    def log(self, line: str = "") -> None:
        """어느 스레드에서 불러도 된다 — 큐에만 넣는다."""
        self.lines.put(str(line))

    def drain(self) -> None:
        while True:
            try:
                line = self.lines.get_nowait()
            except queue.Empty:
                break
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        if self.worker and not self.worker.is_alive():
            self.worker = None
            self.finished()
        self.root.after(100, self.drain)

    # ── 사람에게 묻기 ──────────────────────────────────
    def ask(self, prompt: str = "") -> str:
        """워커가 부른다. 창은 화면 스레드에서 띄우고, 워커는 답이 올 때까지 기다린다."""
        self.answered.clear()
        self.root.after(0, lambda: self._show_ask(prompt))
        # 중지를 눌러도 빠져나오게 둘 다 본다
        while not self.answered.wait(0.2):
            if self.stop.is_set():
                return "q"
        return ""

    def _show_ask(self, prompt: str) -> None:
        messagebox.showinfo("확인이 필요합니다", prompt or "확인을 마쳤으면 확인을 누르세요.")
        self.answered.set()

    # ── 돌리기 ─────────────────────────────────────────
    def load_profiles(self) -> None:
        def work() -> None:
            try:
                api = Zzikko(Settings.load())
                api.login()
                res = api.session.get(f"{api.base}/admin/blog/profiles", timeout=20)
                names = [p["name"] for p in res.json().get("items", []) if p["active"]]
            except (ZzikkoError, FileNotFoundError, ValueError) as error:
                self.log(f"프로필을 받지 못했습니다: {error}")
                return
            except Exception as error:
                self.log(f"프로필을 받지 못했습니다. {type(error).__name__}: {error}")
                return
            self.root.after(0, lambda: self.profile.configure(values=[ALL, *names]))
            self.log(f"쓰는 프로필 {len(names)}개: {', '.join(names) or '(없음)'}")

        threading.Thread(target=work, daemon=True).start()

    def start(self) -> None:
        if self.worker:
            return
        self.stop.clear()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status.configure(text="도는 중…", fg="#c2410c")

        only = None if self.profile.get() == ALL else self.profile.get()
        shot, keep = self.shot.get(), self.keep.get()

        def work() -> None:
            # 작업기의 고리를 이 창의 것으로 바꿔 끼운다
            run_login.say = self.log
            run_login.ask = self.ask
            run_login.stop_flag = self.stop
            try:
                run_login.run(only=only, shot=shot, keep=keep)
            except Exception as error:
                self.log(f"멈췄습니다. {type(error).__name__}: {error}")

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def check_ip(self) -> None:
        if self.worker:
            return
        only = self.profile.get()
        if only == ALL:
            self.log("IP 확인은 프로필을 하나 골라야 합니다")
            return

        def work() -> None:
            run_login.say = self.log
            try:
                run_login.check_ip(only)
            except Exception as error:
                self.log(f"재지 못했습니다. {type(error).__name__}: {error}")

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()
        self.start_btn.configure(state="disabled")
        self.status.configure(text="IP 재는 중…", fg="#c2410c")

    def ask_stop(self) -> None:
        self.stop.set()
        self.answered.set()  # 묻는 창에서 기다리고 있었다면 같이 풀어 준다
        self.status.configure(text="중지하는 중… (하던 것 하나는 끝냅니다)", fg="#666")
        self.log("중지를 눌렀습니다. 하던 아이디 하나는 끝내고 멈춥니다")

    def finished(self) -> None:
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status.configure(text="대기 중", fg="#666")

    def on_close(self) -> None:
        if self.worker:
            if not messagebox.askokcancel("닫기", "작업이 도는 중입니다. 그래도 닫을까요?"):
                return
            self.stop.set()
            self.answered.set()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
