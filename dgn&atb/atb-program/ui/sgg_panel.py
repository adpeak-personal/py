"""좌측 지역 선택 패널 — sgg_codes(시군구)를 체크박스로 표시.

기본 전체 선택. 시/도 헤더(토글) + 개별 시군구 체크박스. 스크롤 지원.
get_selected_codes() 로 선택된 시군구코드(5자리 문자열) 목록을 반환한다.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class SggPanel(tk.Frame):
    def __init__(self, master, codes: list[dict]):
        super().__init__(master, bg="#ffffff", highlightthickness=1,
                         highlightbackground="#e2e8f0")
        self.codes = codes
        self.vars: dict[int, tk.BooleanVar] = {}        # sgg_cd -> checked
        self._sido_vars: dict[str, tk.BooleanVar] = {}  # sido_nm -> 그룹 토글
        self._name_map: dict[int, str] = {}

        self._build_header()
        self._build_list()
        self._update_count()

    # ─── 헤더 (제목 + 전체 토글 + 카운트) ─────────────────────────────────────
    def _build_header(self):
        head = tk.Frame(self, bg="#ffffff")
        head.pack(fill="x", padx=12, pady=(12, 6))
        tk.Label(head, text="지역 선택", font=("맑은 고딕", 11, "bold"),
                 bg="#ffffff", fg="#0f172a").pack(anchor="w")

        row = tk.Frame(self, bg="#ffffff")
        row.pack(fill="x", padx=12, pady=(0, 6))
        self.all_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row, text="전체 선택/해제", variable=self.all_var,
                       command=self._toggle_all, bg="#ffffff", fg="#4f46e5",
                       activebackground="#ffffff", font=("맑은 고딕", 9, "bold"),
                       selectcolor="#ffffff", cursor="hand2").pack(side="left")
        self.count_var = tk.StringVar()
        tk.Label(row, textvariable=self.count_var, font=("맑은 고딕", 8),
                 bg="#ffffff", fg="#94a3b8").pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10)

    # ─── 스크롤 가능한 체크박스 목록 ──────────────────────────────────────────
    def _build_list(self):
        wrap = tk.Frame(self, bg="#ffffff")
        wrap.pack(fill="both", expand=True, padx=(8, 0), pady=8)

        self.canvas = tk.Canvas(wrap, bg="#ffffff", highlightthickness=0, width=190)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(self.canvas, bg="#ffffff")
        self._win = self.canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        # 패널 위에서만 휠 스크롤 (테이블과 충돌 방지)
        self.canvas.bind("<Enter>", lambda _e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))

        # 시/도별 그룹핑 (codes 는 sido_nm, sgg_cd 순 정렬되어 들어옴)
        cur_sido = None
        for c in self.codes:
            sido = c["sido_nm"]
            cd = int(c["sgg_cd"])
            self._name_map[cd] = c["sgg_nm"]

            if sido != cur_sido:
                cur_sido = sido
                svar = tk.BooleanVar(value=True)
                self._sido_vars[sido] = svar
                tk.Checkbutton(
                    inner, text=sido, variable=svar,
                    command=lambda s=sido: self._toggle_sido(s),
                    bg="#ffffff", fg="#475569", activebackground="#ffffff",
                    font=("맑은 고딕", 9, "bold"), selectcolor="#eef2ff",
                    anchor="w", cursor="hand2",
                ).pack(fill="x", pady=(8, 0))

            var = tk.BooleanVar(value=True)
            self.vars[cd] = var
            tk.Checkbutton(
                inner, text=f"   {c['sgg_nm']}", variable=var,
                command=self._update_count,
                bg="#ffffff", fg="#334155", activebackground="#ffffff",
                font=("맑은 고딕", 9), selectcolor="#eef2ff",
                anchor="w", cursor="hand2",
            ).pack(fill="x")

    def _wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    # ─── 토글 핸들러 ──────────────────────────────────────────────────────────
    def _toggle_all(self):
        state = self.all_var.get()
        for v in self.vars.values():
            v.set(state)
        for sv in self._sido_vars.values():
            sv.set(state)
        self._update_count()

    def _toggle_sido(self, sido: str):
        state = self._sido_vars[sido].get()
        for c in self.codes:
            if c["sido_nm"] == sido:
                self.vars[int(c["sgg_cd"])].set(state)
        self._update_count()

    def _update_count(self):
        n = sum(1 for v in self.vars.values() if v.get())
        self.count_var.set(f"선택 {n} / {len(self.vars)}")

    # ─── 공개 API ─────────────────────────────────────────────────────────────
    def get_selected_codes(self) -> list[str]:
        """선택된 시군구코드(5자리 문자열) 목록."""
        return [str(cd) for cd, v in self.vars.items() if v.get()]

    def get_name_map(self) -> dict[int, str]:
        return dict(self._name_map)
