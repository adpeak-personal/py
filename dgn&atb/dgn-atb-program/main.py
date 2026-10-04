"""당근광고 + 부동산 수집 통합 실행기 (진입점).

노트북에 켜두면 jobs.py 의 스케줄대로 두 프로그램의 작업을 돌린다.
창을 닫으면 전부 멈춘다.

실행:  노트북 — build.bat 으로 만든 dist\\dgn-atb\\dgn-atb.exe (파이썬 설치 불필요)
       개발 — start.bat  (또는 python main.py)
"""
from __future__ import annotations

import ctypes
import os
import queue
import sys
from datetime import datetime
from tkinter import BOTH, END, LEFT, RIGHT, X, Button, Frame, Label, Tk, messagebox
from tkinter.scrolledtext import ScrolledText

from jobs import LOG_DIR, Scheduler, preflight

FONT = "맑은 고딕"
REFRESH_MS = 1000

# 절전 방지: 실행기가 떠 있는 동안 노트북이 잠들지 않게 한다 (프로그램 종료 시 자동 해제)
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def _single_instance() -> bool:
    """두 번 띄우면 같은 작업이 두 번 돈다 — 이름 있는 뮤텍스로 막는다."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    App._mutex = k32.CreateMutexW(None, False, "Local\\dgn_atb_runner")   # 프로세스 끝날 때까지 쥐고 있는다
    return ctypes.get_last_error() != 183   # ERROR_ALREADY_EXISTS


def _fmt(dt: datetime | None) -> str:
    return dt.strftime("%m-%d %H:%M") if dt else "-"


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.events: queue.Queue[str] = queue.Queue()
        self.sched = Scheduler(on_event=self.events.put)
        self.rows: dict[str, dict[str, Label]] = {}

        root.title("당근 · 부동산 수집기")
        root.geometry("620x460+400+200")
        root.minsize(560, 380)
        root.configure(bg="#f2f2f2")
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        bar = Frame(root, bg="#1a1a2e", height=44)
        bar.pack(fill=X)
        bar.pack_propagate(False)
        Label(bar, text="당근 · 부동산 수집기", bg="#1a1a2e", fg="white",
              font=(FONT, 11, "bold")).pack(side=LEFT, padx=14)
        Button(bar, text="로그 폴더", command=lambda: os.startfile(LOG_DIR),
               font=(FONT, 9), relief="flat", bg="#33334d", fg="white",
               activebackground="#44445e", activeforeground="white",
               cursor="hand2").pack(side=RIGHT, padx=12)

        table = Frame(root, bg="#f2f2f2", padx=14, pady=10)
        table.pack(fill=X)
        for c, (text, w) in enumerate([("작업", 18), ("일정", 10), ("마지막 실행", 11), ("상태", 12), ("", 8)]):
            Label(table, text=text, width=w, anchor="w", bg="#f2f2f2", fg="#666666",
                  font=(FONT, 9, "bold")).grid(row=0, column=c, sticky="w", pady=(0, 4))
        for r, job in enumerate(self.sched.jobs.values(), start=1):
            cells = {}
            for c, (name, w) in enumerate([("label", 18), ("schedule", 10), ("last", 11), ("status", 12)]):
                cells[name] = Label(table, width=w, anchor="w", bg="#f2f2f2", fg="#333333", font=(FONT, 9))
                cells[name].grid(row=r, column=c, sticky="w", pady=2)
            cells["label"].config(text=job.label)
            cells["schedule"].config(text=job.schedule_text)
            Button(table, text="지금 실행", font=(FONT, 8), relief="flat", bg="#3d7cf0", fg="white",
                   activebackground="#2f6bdc", activeforeground="white", cursor="hand2",
                   command=lambda k=job.key: self.sched.run_now(k)).grid(row=r, column=4, sticky="w")
            self.rows[job.key] = cells

        self.log = ScrolledText(root, height=10, font=("Consolas", 9), bg="white", relief="flat")
        self.log.pack(fill=BOTH, expand=True, padx=14, pady=(0, 14))

        for w in preflight():
            self.write(f"⚠ {w}")
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        self.write("시작 — 창이 떠 있는 동안 절전 모드로 들어가지 않습니다")
        self.sched.start()
        self.refresh()

    def write(self, msg: str):
        self.log.insert(END, f"[{datetime.now():%m-%d %H:%M:%S}] {msg}\n")
        # 며칠씩 켜두므로 화면 로그는 최근 것만 남긴다 (전체는 logs 폴더)
        if int(self.log.index("end-1c").split(".")[0]) > 500:
            self.log.delete("1.0", "101.0")
        self.log.see(END)

    def refresh(self):
        while not self.events.empty():
            self.write(self.events.get_nowait())
        for key, job in self.sched.jobs.items():
            cells = self.rows[key]
            if job.running:
                status, color = "실행 중…", "#3d7cf0"
            elif job.queued:
                status, color = "대기", "#b07d00"
            elif job.last_code is None:
                status, color = "-", "#999999"
            elif job.last_code == 0:
                status, color = "성공", "#1f8a4c"
            else:
                status, color = f"실패 (코드 {job.last_code})", "#d0342c"
            last = job.last_start
            if last is None and job.daily_at:
                # 재시작 직후엔 메모리에 기록이 없으니 오늘 돌았는지만 표시
                ran = self.sched.last_daily_run(key)
                cells["last"].config(text=f"{ran[5:]} (이전)" if ran else "-")
            else:
                cells["last"].config(text=_fmt(last))
            cells["status"].config(text=status, fg=color)
        self.root.after(REFRESH_MS, self.refresh)

    def on_close(self):
        running = [j.label for j in self.sched.jobs.values() if j.running]
        msg = "종료하면 모든 수집이 멈춥니다."
        if running:
            msg += f"\n\n지금 도는 작업도 중단됩니다:\n- " + "\n- ".join(running)
        if messagebox.askokcancel("종료", msg):
            self.sched.stop()
            self.root.destroy()


def main():
    if "--job" in sys.argv:
        # 실행기가 작업 하나를 돌리려고 자기 자신을 다시 띄운 경우 (jobs._worker_cmd)
        import worker
        sys.exit(worker.run(sys.argv))
    if not _single_instance():
        root = Tk()
        root.withdraw()
        messagebox.showinfo("당근 · 부동산 수집기", "이미 실행 중입니다.")
        sys.exit(0)
    root = Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
