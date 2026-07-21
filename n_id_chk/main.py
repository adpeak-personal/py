"""간소 GUI: 체크 주기(일)만 입력하고 시작.

로그는 터미널(stdout)에 출력된다. 실제 배치 로직은 workspace.run_batch.
"""

import threading
import tkinter as tk
from tkinter import ttk

import workspace


class App(tk.Frame):
    def __init__(self, master):
        super().__init__(master, padx=16, pady=16)
        self.pack(fill="both", expand=True)
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        row = ttk.Frame(self)
        row.pack(fill="x")

        ttk.Label(row, text="체크 주기(일)").pack(side="left")
        self.days_var = tk.StringVar(value=str(workspace.DEFAULT_DAYS))
        ttk.Entry(row, textvariable=self.days_var, width=6).pack(side="left", padx=8)

        self.start_btn = ttk.Button(row, text="시작", command=self.start)
        self.start_btn.pack(side="left")

        self.status_var = tk.StringVar(value="대기 중")
        ttk.Label(self, textvariable=self.status_var, foreground="gray").pack(
            anchor="w", pady=(12, 0)
        )
        ttk.Label(
            self, text="※ 진행 로그는 실행한 터미널에서 확인하세요.",
            foreground="gray",
        ).pack(anchor="w", pady=(4, 0))

    def start(self):
        if self.worker and self.worker.is_alive():
            return

        try:
            days = int(self.days_var.get())
        except ValueError:
            days = workspace.DEFAULT_DAYS
            self.days_var.set(str(days))

        self.start_btn.configure(state="disabled")
        self.status_var.set(f"실행 중... (기준 {days}일) — 로그는 터미널 확인")

        self.worker = threading.Thread(
            target=self._run, args=(days,), daemon=True
        )
        self.worker.start()

    def _run(self, days):
        try:
            result = workspace.run_batch(days, log=print)
            msg = (f"완료 — 총 {result['total']} / "
                   f"성공 {result['ok']} / 실패 {result['fail']}")
        except Exception as e:
            print("오류:", e)
            msg = "오류 — 터미널 확인"
        # UI 갱신은 메인 스레드에서
        self.after(0, self._finish, msg)

    def _finish(self, msg):
        self.status_var.set(msg)
        self.start_btn.configure(state="normal")


def main():
    root = tk.Tk()
    root.title("네이버 로그인 체크")
    root.geometry("420x160")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
