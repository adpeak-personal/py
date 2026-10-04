"""메인 윈도우 — 아파트 실거래가 조회 / DB 저장 / 이미지 보기.

좌측 지역 체크박스(sgg_codes) 다중 선택 → 선택 지역들을 조회/수집하여 DB 저장.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox

import config
from services import apt_api, db, image_pipeline, kapt_sync, apt_match_run
from services.apt_api import AptTradeItem
from ui.image_window import ImageWindow
from ui.sgg_panel import SggPanel

# 표 컬럼 정의: (id, 헤더, 너비, 정렬)
COLUMNS = [
    ("region", "지역", 80, "center"),
    ("aptNm", "아파트명", 170, "w"),
    ("umd", "동/읍면동", 120, "w"),
    ("area", "전용면적", 75, "e"),
    ("floor", "층", 45, "e"),
    ("price", "거래금액", 130, "e"),
    ("date", "거래일", 95, "center"),
    ("buildYear", "건축년도", 65, "center"),
    ("gbn", "거래유형", 75, "center"),
]

PREVIEW_CONFIRM_OVER = 20  # 미리보기 지역이 이보다 많으면 확인


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("아파트 실거래가 조회")
        self.geometry("1180x720")
        self.configure(bg="#f8fafc")

        self._items: list[AptTradeItem] = []
        self._name_map: dict[int, str] = {}
        self._busy = False

        self._build_styles()
        self._build_header()
        self._build_form()
        self._build_status()
        self._build_body()

        self.deal_ymd_var.set(config.current_year_month())
        self._load_sgg()

    # ─── 스타일 ───────────────────────────────────────────────────────────────
    def _build_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=28, font=("맑은 고딕", 10),
                        background="#ffffff", fieldbackground="#ffffff")
        style.configure("Treeview.Heading", font=("맑은 고딕", 9, "bold"),
                        background="#f1f5f9", foreground="#475569")
        style.map("Treeview", background=[("selected", "#e0e7ff")],
                  foreground=[("selected", "#3730a3")])
        style.configure("Accent.TButton", font=("맑은 고딕", 10, "bold"),
                        foreground="#ffffff", background="#4f46e5", padding=(16, 6))
        style.map("Accent.TButton", background=[("active", "#4338ca")])
        style.configure("Save.TButton", font=("맑은 고딕", 10, "bold"),
                        foreground="#ffffff", background="#059669", padding=(16, 6))
        style.map("Save.TButton", background=[("active", "#047857")])
        style.configure("Match.TButton", font=("맑은 고딕", 10, "bold"),
                        foreground="#ffffff", background="#0891b2", padding=(16, 6))
        style.map("Match.TButton", background=[("active", "#0e7490")])

    # ─── 헤더 ─────────────────────────────────────────────────────────────────
    def _build_header(self):
        head = tk.Frame(self, bg="#f8fafc")
        head.pack(fill="x", padx=24, pady=(18, 6))
        tk.Label(head, text="아파트 실거래가 조회", font=("맑은 고딕", 17, "bold"),
                 bg="#f8fafc", fg="#0f172a").pack(anchor="w")
        tk.Label(head, text="좌측에서 지역을 선택하고, 계약년월 기준으로 조회·DB 저장합니다",
                 font=("맑은 고딕", 9), bg="#f8fafc", fg="#64748b").pack(anchor="w")

    # ─── 검색 폼 (계약년월 + 버튼) ────────────────────────────────────────────
    def _build_form(self):
        card = tk.Frame(self, bg="#ffffff", highlightthickness=1,
                        highlightbackground="#e2e8f0")
        card.pack(fill="x", padx=24, pady=8)
        inner = tk.Frame(card, bg="#ffffff")
        inner.pack(fill="x", padx=18, pady=14)

        tk.Label(inner, text="계약년월 (YYYYMM)", font=("맑은 고딕", 8, "bold"),
                 bg="#ffffff", fg="#475569").grid(row=0, column=0, sticky="w")
        self.deal_ymd_var = tk.StringVar()
        ymd = ttk.Entry(inner, textvariable=self.deal_ymd_var, width=12,
                        font=("맑은 고딕", 10))
        ymd.grid(row=1, column=0, sticky="w", padx=(0, 14), pady=(4, 0))
        ymd.bind("<Return>", lambda _e: self.fetch_data())

        self.fetch_btn = ttk.Button(inner, text="조회(미리보기)", style="Accent.TButton",
                                    command=self.fetch_data)
        self.fetch_btn.grid(row=1, column=1, padx=(0, 8), pady=(4, 0))
        self.save_btn = ttk.Button(inner, text="선택 지역 DB에 저장", style="Save.TButton",
                                   command=self.sync_to_db)
        self.save_btn.grid(row=1, column=2, padx=(0, 8), pady=(4, 0))
        self.kapt_btn = ttk.Button(inner, text="선택 지역 K-apt 매칭", style="Match.TButton",
                                   command=self.sync_kapt)
        self.kapt_btn.grid(row=1, column=3, padx=(0, 8), pady=(4, 0))
        self.image_btn = ttk.Button(inner, text="신규 단지 이미지 검수·저장",
                                    style="Accent.TButton", command=self.sync_images)
        self.image_btn.grid(row=1, column=4, pady=(4, 0))

    # ─── 상태줄 ───────────────────────────────────────────────────────────────
    def _build_status(self):
        self.status_var = tk.StringVar(value="")
        self.status_lbl = tk.Label(self, textvariable=self.status_var,
                                   font=("맑은 고딕", 9), bg="#f8fafc",
                                   fg="#64748b", anchor="w")
        self.status_lbl.pack(fill="x", padx=24, pady=(2, 0))

    # ─── 본문: 좌측 지역패널 + 우측 결과표 ────────────────────────────────────
    def _build_body(self):
        body = tk.Frame(self, bg="#f8fafc")
        body.pack(fill="both", expand=True, padx=24, pady=(8, 20))

        # 좌측 패널 자리 (코드 로드 후 채움)
        self.left_holder = tk.Frame(body, bg="#f8fafc", width=220)
        self.left_holder.pack(side="left", fill="y", padx=(0, 12))
        self.left_holder.pack_propagate(False)
        self.sgg_panel: SggPanel | None = None
        self.sgg_loading = tk.Label(self.left_holder, text="지역 불러오는 중...",
                                    font=("맑은 고딕", 9), bg="#f8fafc", fg="#94a3b8")
        self.sgg_loading.pack(pady=20)

        # 우측 결과표
        wrap = tk.Frame(body, bg="#ffffff", highlightthickness=1,
                        highlightbackground="#e2e8f0")
        wrap.pack(side="left", fill="both", expand=True)

        cols = [c[0] for c in COLUMNS]
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        for cid, head, width, anchor in COLUMNS:
            self.tree.heading(cid, text=head)
            self.tree.column(cid, width=width, anchor=anchor, stretch=(cid == "aptNm"))

        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.tag_configure("odd", background="#fafafa")
        self.tree.bind("<Double-1>", self._on_row_double_click)

        self.empty_hint = tk.Label(
            wrap, text="🏢  지역을 선택하고 [조회]를 눌러주세요\n"
                       "행을 더블클릭하면 이미지를 볼 수 있어요",
            font=("맑은 고딕", 11), bg="#ffffff", fg="#94a3b8", justify="center")
        self.empty_hint.place(relx=0.5, rely=0.5, anchor="center")

    # ─── sgg_codes 로드 ───────────────────────────────────────────────────────
    def _load_sgg(self):
        threading.Thread(target=self._load_sgg_worker, daemon=True).start()

    def _load_sgg_worker(self):
        try:
            codes = db.load_sgg_codes()
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda: self._sgg_load_failed(str(e)))
            return
        self.after(0, lambda: self._sgg_load_done(codes))

    def _sgg_load_failed(self, msg: str):
        self.sgg_loading.config(text=f"지역 로드 실패:\n{msg}", fg="#dc2626",
                                wraplength=190, justify="left")

    def _sgg_load_done(self, codes: list[dict]):
        self.sgg_loading.destroy()
        self.sgg_panel = SggPanel(self.left_holder, codes)
        self.sgg_panel.pack(fill="both", expand=True)
        self._name_map = self.sgg_panel.get_name_map()

    # ─── 공통: 입력 검증 ──────────────────────────────────────────────────────
    def _validate(self) -> tuple[list[str], str] | None:
        if self._busy:
            return None
        if not self.sgg_panel:
            messagebox.showwarning("잠시만요", "지역 목록을 아직 불러오는 중입니다.")
            return None
        codes = self.sgg_panel.get_selected_codes()
        if not codes:
            messagebox.showwarning("지역 선택", "최소 한 개 지역을 선택하세요.")
            return None
        ymd = self.deal_ymd_var.get().strip()
        if len(ymd) != 6 or not ymd.isdigit():
            messagebox.showwarning("입력 확인", "계약년월은 YYYYMM 6자리로 입력하세요.")
            return None
        return codes, ymd

    def _set_busy(self, busy: bool):
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.fetch_btn.config(state=state)
        self.save_btn.config(state=state)
        self.kapt_btn.config(state=state)
        self.image_btn.config(state=state)

    # ─── 조회 (미리보기) ──────────────────────────────────────────────────────
    def fetch_data(self):
        v = self._validate()
        if not v:
            return
        codes, ymd = v
        if len(codes) > PREVIEW_CONFIRM_OVER and not messagebox.askyesno(
            "미리보기 확인",
            f"{len(codes)}개 지역을 미리보기하면 API를 {len(codes)}번 호출해 "
            f"시간이 걸립니다.\n계속할까요?\n\n(DB 저장만 할 거면 [아니오] 후 "
            f"[선택 지역 DB에 저장]을 누르세요)",
        ):
            return

        self._set_busy(True)
        self.fetch_btn.config(text="조회중...")
        self.status_lbl.config(fg="#64748b")
        threading.Thread(target=self._fetch_worker, args=(codes, ymd), daemon=True).start()

    def _fetch_worker(self, codes: list[str], ymd: str):
        items: list[AptTradeItem] = []
        for i, code in enumerate(codes):
            name = self._name_map.get(int(code), code)
            self.after(0, lambda i=i, name=name: self.status_var.set(
                f"조회 중... {i + 1}/{len(codes)}  [{name}]"))
            try:
                res = apt_api.fetch_apt_trades(code, ymd, num_of_rows=100)
            except Exception:  # noqa: BLE001 — 개별 지역 실패는 건너뜀
                continue
            for it in res.items:
                it.sggCd = code
            items.extend(res.items)
        self.after(0, lambda: self._fetch_done(items, ymd, len(codes)))

    def _fetch_done(self, items: list[AptTradeItem], ymd: str, n_regions: int):
        self._set_busy(False)
        self.fetch_btn.config(text="조회(미리보기)")
        self._items = items
        self._fill_table(items)
        self.status_var.set(
            f"{n_regions}개 지역 · {ymd[:4]}년 {ymd[4:]}월 — 미리보기 {len(items):,}건 "
            f"(각 지역 최대 100건)")
        self.status_lbl.config(fg="#4f46e5")

    def _fill_table(self, items: list[AptTradeItem]):
        self.empty_hint.place_forget()
        self.tree.delete(*self.tree.get_children())
        if not items:
            self.empty_hint.config(text="조회 결과가 없습니다")
            self.empty_hint.place(relx=0.5, rely=0.5, anchor="center")
            return

        for i, it in enumerate(items):
            region = self._name_map.get(int(it.sggCd), it.sggCd) if it.sggCd else ""
            dong = it.umdNm + (f"  {it.aptDong}동" if it.aptDong else "")
            date = f"{it.dealYear}.{int(it.dealMonth or 0):02d}.{int(it.dealDay or 0):02d}" \
                if it.dealMonth else ""
            self.tree.insert(
                "", "end", iid=str(i),
                values=(
                    region,
                    it.aptNm,
                    dong,
                    f"{it.excluUseAr}㎡",
                    f"{it.floor}층",
                    f"{config.format_price(it.dealAmount)}원",
                    date,
                    it.buildYear,
                    it.dealingGbn or "-",
                ),
                tags=(("odd",) if i % 2 else ()),
            )

    # ─── 이미지 보기 (더블클릭) ───────────────────────────────────────────────
    def _on_row_double_click(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self._items):
            return
        item = self._items[idx]
        ImageWindow(self, item.aptNm, f"{item.aptNm} {item.umdNm} 아파트")

    # ─── DB 저장 (선택 지역 전체 페이지 수집) ─────────────────────────────────
    def sync_to_db(self):
        v = self._validate()
        if not v:
            return
        codes, ymd = v
        if not messagebox.askyesno(
            "DB 저장",
            f"선택한 {len(codes)}개 지역의 {ymd[:4]}년 {ymd[4:]}월 실거래가를 "
            f"전부 수집해 MySQL({config.MYSQL_DATABASE})에 저장할까요?\n"
            f"지역 수가 많으면 시간이 걸릴 수 있습니다.",
        ):
            return
        self._set_busy(True)
        self.save_btn.config(text="저장중...")
        self.status_lbl.config(fg="#64748b")
        threading.Thread(target=self._save_worker, args=(codes, ymd), daemon=True).start()

    def _save_worker(self, codes: list[str], ymd: str):
        total_saved = total_fetched = 0
        errors: list[str] = []
        for i, code in enumerate(codes):
            name = self._name_map.get(int(code), code)
            self.after(0, lambda i=i, name=name: self.status_var.set(
                f"저장 중... {i + 1}/{len(codes)}  [{name}]  "
                f"(누적 {total_saved:,}건 저장)"))
            page = 1
            try:
                while True:
                    res = apt_api.fetch_apt_trades(code, ymd, page_no=page, num_of_rows=1000)
                    if not res.items:
                        break
                    for it in res.items:
                        it.sggCd = code
                    total_saved += db.save_apt_trades(res.items)
                    total_fetched += len(res.items)
                    if page * 1000 >= res.totalCount:
                        break
                    page += 1
            except Exception as e:  # noqa: BLE001
                errors.append(f"{name}: {e}")
        # 저장된 지역의 전용면적 파생 갱신 (apartments.exclu_areas)
        try:
            db.refresh_exclu_areas(codes)
        except Exception as e:  # noqa: BLE001
            errors.append(f"전용면적 갱신: {e}")
        self.after(0, lambda: self._save_done(total_saved, total_fetched, len(codes), errors))

    def _save_done(self, saved: int, fetched: int, n_regions: int, errors: list[str]):
        self._set_busy(False)
        self.save_btn.config(text="선택 지역 DB에 저장")
        if errors:
            self.status_var.set(
                f"저장 완료(일부 실패) — {n_regions}개 지역 중 {len(errors)}개 오류, "
                f"신규 {saved:,}건 저장 / 수집 {fetched:,}건")
            self.status_lbl.config(fg="#d97706")
            messagebox.showwarning("일부 지역 실패", "\n".join(errors[:10]))
        else:
            self.status_var.set(
                f"저장 완료 — {n_regions}개 지역, 신규 {saved:,}건 저장 "
                f"(수집 {fetched:,}건)")
            self.status_lbl.config(fg="#059669")

    # ─── 신규 단지 이미지 검수·저장 ───────────────────────────────────────────
    def sync_images(self):
        if self._busy:
            return
        if not messagebox.askyesno(
            "이미지 검수",
            "아직 검수하지 않은 신규 단지(image_status=0)의 이미지를 검색·검수해 "
            "저장합니다.\n기존 단지는 건너뜁니다.\n\n단지 수가 많으면 시간이 오래 "
            "걸릴 수 있어요. 계속할까요?",
        ):
            return
        self._set_busy(True)
        self.image_btn.config(text="검수중...")
        self.status_lbl.config(fg="#64748b")
        threading.Thread(target=self._image_worker, daemon=True).start()

    def _image_worker(self):
        def progress(idx, total, apt_nm, status):
            ko = {"found": "확보", "none": "없음", "failed": "실패"}.get(status, status)
            self.after(0, lambda: self.status_var.set(
                f"이미지 검수 중... {idx}/{total}  [{apt_nm}] {ko}"))
        try:
            stats = image_pipeline.sync_pending_images(on_progress=progress)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            self.after(0, lambda: self._image_done_error(msg))
            return
        self.after(0, lambda: self._image_done(stats))

    def _image_done(self, stats: image_pipeline.ImageSyncStats):
        self._set_busy(False)
        self.image_btn.config(text="신규 단지 이미지 검수·저장")
        if stats.total == 0:
            self.status_var.set("검수할 신규 단지가 없습니다 (모두 검수 완료).")
            self.status_lbl.config(fg="#64748b")
            return
        self.status_var.set(
            f"이미지 검수 완료 — 대상 {stats.total:,} · 확보 {stats.found:,} · "
            f"없음 {stats.none:,} · 실패 {stats.failed:,}")
        self.status_lbl.config(fg="#059669")

    def _image_done_error(self, msg: str):
        self._set_busy(False)
        self.image_btn.config(text="신규 단지 이미지 검수·저장")
        self.status_var.set(f"이미지 검수 실패: {msg}")
        self.status_lbl.config(fg="#dc2626")

    # ─── 선택 지역 K-apt 매칭 ─────────────────────────────────────────────────
    #   run_kapt.py 와 동일: 시군구별 K-apt 마스터 동기화 → 실거래 단지 매칭.
    #   계약년월과 무관하므로 지역 선택만 검증한다.
    def sync_kapt(self):
        if self._busy:
            return
        if not self.sgg_panel:
            messagebox.showwarning("잠시만요", "지역 목록을 아직 불러오는 중입니다.")
            return
        codes = self.sgg_panel.get_selected_codes()
        if not codes:
            messagebox.showwarning("지역 선택", "최소 한 개 지역을 선택하세요.")
            return
        if not messagebox.askyesno(
            "K-apt 매칭",
            f"선택한 {len(codes)}개 지역의 K-apt 단지정보를 동기화하고, 저장된 "
            f"실거래 단지와 이름·지번으로 매칭합니다.\n(먼저 'DB에 저장'으로 실거래를 "
            f"넣어둬야 매칭 대상이 생깁니다.)\n\n지역당 단지 수백 건을 조회해 시간이 "
            f"걸릴 수 있어요. 계속할까요?",
        ):
            return
        self._set_busy(True)
        self.kapt_btn.config(text="매칭중...")
        self.status_lbl.config(fg="#64748b")
        threading.Thread(target=self._kapt_worker, args=(codes,), daemon=True).start()

    def _kapt_worker(self, codes: list[str]):
        agg = {"confirmed": 0, "matched": 0, "ambiguous": 0,
               "conflict": 0, "unmatched": 0, "synced": 0, "skipped": 0}
        errors: list[str] = []
        n = len(codes)
        for i, code in enumerate(codes):
            name = self._name_map.get(int(code), code)

            def prog(done, total, kn, i=i, name=name):
                self.after(0, lambda: self.status_var.set(
                    f"K-apt 동기화 {i + 1}/{n}  [{name}]  {done}/{total}  {kn[:16]}"))
            try:
                st = kapt_sync.sync_sigungu(str(code), on_progress=prog)
                agg["synced"] += st.get("saved", 0)
                agg["skipped"] += st.get("skipped", 0)
                self.after(0, lambda i=i, name=name: self.status_var.set(
                    f"매칭 중 {i + 1}/{n}  [{name}] ..."))
                m = apt_match_run.run_matching(int(code))
                for k in ("confirmed", "matched", "ambiguous", "conflict", "unmatched"):
                    agg[k] += m.get(k, 0)
            except Exception as e:  # noqa: BLE001 — 지역별 실패는 모아서 보고
                errors.append(f"{name}: {e}")
        self.after(0, lambda: self._kapt_done(agg, len(codes), errors))

    def _kapt_done(self, agg: dict, n_regions: int, errors: list[str]):
        self._set_busy(False)
        self.kapt_btn.config(text="선택 지역 K-apt 매칭")
        auto = agg["confirmed"] + agg["matched"]
        review = agg["ambiguous"] + agg["conflict"]
        base = (f"K-apt 매칭 완료 — 마스터 신규·갱신 {agg['synced']:,}/건너뜀 "
                f"{agg['skipped']:,} · 자동확정 {auto:,} (확정 {agg['confirmed']:,}/"
                f"단일 {agg['matched']:,}) · 수동확인 {review:,} · 미매칭 {agg['unmatched']:,}")
        if errors:
            self.status_var.set(f"{base}  (지역 {len(errors)}개 오류)")
            self.status_lbl.config(fg="#dc2626")
            messagebox.showwarning("일부 지역 실패", "\n".join(errors[:10]))
        else:
            self.status_var.set(base)
            self.status_lbl.config(fg="#059669")


def run():
    App().mainloop()
