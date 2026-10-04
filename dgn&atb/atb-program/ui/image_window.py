"""이미지 팝업 창 — 네이버 이미지를 1장씩 검수해 '글씨 없는 단지 외관' 1장만 표시.

검수: 단지(건물) 외관 + 실외(실내/조경 제외) + 읽히는 글씨 없음 (services/image_inspector).
출처 차단: 워터마크 잘 박히는 호스트(네이버 매물/호갱노노 등)는 image_service 에서 제외.
통과한 1장을 크게 보여주고, 하단에 원본 링크(출처)를 표시한다.
"""
from __future__ import annotations

import io
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from services import image_service

MAX_W, MAX_H = 600, 400   # 표시 이미지 최대 크기
CANDIDATES = 30           # 검사할 후보 수 상한

_REASON_KO = {
    "indoor": "실내/조경",
    "not_building": "외관아님",
    "has_person": "인물",
    "has_text": "글씨/워터마크",
    "download_fail": "다운로드실패",
    "decode_fail": "디코딩실패",
}


class ImageWindow(tk.Toplevel):
    def __init__(self, master, apt_nm: str, query: str):
        super().__init__(master)
        self.apt_nm = apt_nm
        self.query = query
        self._photo = None  # GC 방지

        self.title(f"이미지 — {apt_nm}")
        self.geometry("660x600")
        self.configure(bg="#ffffff")
        self.transient(master)

        # 헤더
        header = tk.Frame(self, bg="#ffffff")
        header.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(header, text=apt_nm, font=("맑은 고딕", 13, "bold"),
                 bg="#ffffff", fg="#0f172a").pack(anchor="w")
        tk.Label(header, text=f"검색어: {query}", font=("맑은 고딕", 9),
                 bg="#ffffff", fg="#94a3b8").pack(anchor="w")
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20)

        # 본문
        self.body = tk.Frame(self, bg="#ffffff")
        self.body.pack(fill="both", expand=True, padx=20, pady=16)
        self.status = tk.Label(self.body, text="이미지 검수 준비 중...",
                               font=("맑은 고딕", 10), bg="#ffffff", fg="#64748b")
        self.status.pack(pady=30)

        threading.Thread(target=self._search, daemon=True).start()

    # ─── 진행상황 콜백 ────────────────────────────────────────────────────────
    def _progress(self, idx: int, total: int, reason: str):
        ko = _REASON_KO.get(reason, reason)
        self.after(0, lambda: self._set_status(f"검수 중... {idx}/{total}  (직전: {ko})"))

    def _set_status(self, text: str, color: str = "#64748b"):
        if self.winfo_exists() and self.status.winfo_exists():
            self.status.config(text=text, fg=color)

    # ─── 검색+검수 (백그라운드) ───────────────────────────────────────────────
    def _search(self):
        self.after(0, lambda: self._set_status(
            "이미지 검수 중... (모델 최초 1회 로딩 시 잠시 걸림)"))
        try:
            result = image_service.find_one_apartment_image(
                self.query, candidates=CANDIDATES, on_progress=self._progress)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            self.after(0, lambda: self._set_status(f"오류: {msg}", "#dc2626"))
            return
        self.after(0, lambda: self._render(result))

    def _render(self, result: image_service.SingleResult):
        if not self.winfo_exists():
            return
        self.status.destroy()

        if result.image is None:
            parts = ", ".join(
                f"{_REASON_KO.get(k, k)} {v}" for k, v in result.reasons.items())
            tk.Label(self.body, text="조건에 맞는 이미지를 찾지 못했습니다",
                     font=("맑은 고딕", 11, "bold"), bg="#ffffff", fg="#475569"
                     ).pack(pady=(40, 6))
            tk.Label(self.body,
                     text=f"{result.checked}/{result.total}장 검사  ·  탈락: {parts or '없음'}",
                     font=("맑은 고딕", 9), bg="#ffffff", fg="#94a3b8").pack()
            return
        self._show_image(result)

    def _show_image(self, result: image_service.SingleResult):
        img = result.image
        try:
            pil = Image.open(io.BytesIO(img.image_bytes)).convert("RGB")
            pil.thumbnail((MAX_W, MAX_H), Image.LANCZOS)
        except Exception as e:  # noqa: BLE001
            tk.Label(self.body, text=f"이미지 표시 실패: {e}", font=("맑은 고딕", 10),
                     bg="#ffffff", fg="#dc2626").pack(pady=30)
            return

        self._photo = ImageTk.PhotoImage(pil)
        holder = tk.Frame(self.body, bg="#ffffff", cursor="hand2")
        holder.pack(pady=(6, 8))
        lbl = tk.Label(holder, image=self._photo, bg="#ffffff",
                       highlightthickness=1, highlightbackground="#e2e8f0")
        lbl.pack()
        lbl.bind("<Button-1>", lambda _e: webbrowser.open(img.imageUrl))

        info = (f"✓ 단지 외관 · 실외 · 글씨/워터마크 없음   "
                f"({result.checked}/{result.total}장 중 선택"
                f"{' · ' + img.category if img.category else ''})")
        tk.Label(self.body, text=info, font=("맑은 고딕", 9),
                 bg="#ffffff", fg="#64748b").pack()

        # ─ 하단 링크 (출처) ─
        ttk.Separator(self.body, orient="horizontal").pack(fill="x", pady=(10, 6))
        link_row = tk.Frame(self.body, bg="#ffffff")
        link_row.pack(fill="x")
        host = image_service.image_host(img.imageUrl) or "link"
        tk.Label(link_row, text="출처:", font=("맑은 고딕", 9),
                 bg="#ffffff", fg="#94a3b8").pack(side="left")
        link = tk.Label(link_row, text=host, font=("맑은 고딕", 9, "underline"),
                        bg="#ffffff", fg="#2563eb", cursor="hand2")
        link.pack(side="left", padx=(4, 0))
        link.bind("<Button-1>", lambda _e: webbrowser.open(img.imageUrl))

        # 전체 URL (복사용) — 선택 가능한 Entry
        url_var = tk.StringVar(value=img.imageUrl)
        url_entry = tk.Entry(self.body, textvariable=url_var, state="readonly",
                             font=("맑은 고딕", 8), fg="#64748b", relief="flat",
                             readonlybackground="#f8fafc")
        url_entry.pack(fill="x", pady=(6, 0))
        tk.Label(self.body, text="이미지를 클릭하거나 위 링크로 원본을 엽니다 · URL은 드래그해 복사",
                 font=("맑은 고딕", 8), bg="#ffffff", fg="#cbd5e1").pack(pady=(4, 0))
