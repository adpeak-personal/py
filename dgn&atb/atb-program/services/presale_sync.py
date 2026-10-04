"""청약홈 응답 → presale_notices / presale_types.

공고 종류마다 필드 이름이 조금씩 다르다(접수일이 RCEPT_* / SUBSCRPT_RCEPT_* /
GNRL_RCEPT_*, 전용면적이 HOUSE_TY 문자열 / EXCLUSE_AR 숫자 등). 여기서 한 모양으로
맞춘다. 원본은 raw 에 그대로 남겨 필드가 바뀌어도 다시 매핑할 수 있게 한다.

노출 제어 컬럼(is_featured / sort_weight / is_hidden)과 좌표는 절대 덮어쓰지 않는다.
광고 상품이 붙는 자리라, 재수집이 운영자가 정한 노출을 되돌리면 안 된다.
"""
from __future__ import annotations

import json
import re
from datetime import date

import pymysql

from services import db
from services.presale_api import Kind

# ─── 값 정리 ──────────────────────────────────────────────────────────────────


def _s(v, n: int | None = None) -> str | None:
    if v is None:
        return None
    t = str(v).strip()
    if not t or t in ("-", "null"):
        return None
    return t[:n] if n else t


def _int(v) -> int | None:
    t = _s(v)
    if t is None:
        return None
    t = t.replace(",", "")
    try:
        return int(float(t))
    except ValueError:
        return None


def _float(v) -> float | None:
    t = _s(v)
    if t is None:
        return None
    try:
        return float(t.replace(",", ""))
    except ValueError:
        return None


def _date(v) -> date | None:
    """'2026-09-28' 과 '20260928' 둘 다 받는다."""
    t = _s(v)
    if not t:
        return None
    d = re.sub(r"\D", "", t)
    if len(d) != 8:
        return None
    try:
        return date(int(d[:4]), int(d[4:6]), int(d[6:]))
    except ValueError:
        return None


def _yn(v) -> str | None:
    t = _s(v)
    return t if t in ("Y", "N") else None


def _first(d: dict, *keys):
    for k in keys:
        if _s(d.get(k)) is not None:
            return d.get(k)
    return None


# ─── 지역 매칭 ────────────────────────────────────────────────────────────────
# 공급위치(HSSPLY_ADRES) 앞부분을 sgg_codes 의 시도·시군구와 맞춘다.
# 주소가 '경기도 수원시 권선구 …' 면 가장 긴 '수원시 권선구' 를 고른다.

_SIDO_ALIAS = {
    "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시",
    "광주": "광주광역시", "대전": "대전광역시", "울산": "울산광역시",
    "세종": "세종특별자치시", "세종시": "세종특별자치시",
    "경기": "경기도", "강원": "강원특별자치도", "강원도": "강원특별자치도",
    "충북": "충청북도", "충남": "충청남도",
    "전북": "전북특별자치도", "전라북도": "전북특별자치도", "전남": "전라남도",
    "경북": "경상북도", "경남": "경상남도",
    "제주": "제주특별자치도", "제주도": "제주특별자치도",
}


# 2026 통합으로 주소에는 이렇게 쓰이지만 sgg_codes 는 옛 두 시도로 나뉘어 있다
_SIDO_MULTI = {"전남광주통합특별시": ("광주광역시", "전라남도")}


class RegionIndex:
    """주소 → (시도, 시군구, sgg_cd).

    1) 시도 토큰 + 가장 긴 시군구명 접두 일치 ('수원시 권선구' 가 '수원시' 보다 먼저)
    2) 실패하면 읍면동으로 역조회 — apartments 에 실거래로 쌓인 (시도, 법정동) → sgg_cd.
       '화성시 여울동'(분구 후 구 표기 없음), '인천 동구 송림동'(제물포구로 개편) 같은
       행정구역 변경을 따로 표로 관리하지 않아도 풀린다. 한 동이 여러 구에 걸치면 포기.
    3) 주소 앞에 사업명이 오고 진짜 주소가 괄호 안에 있는 경우도 괄호 안을 다시 본다.
    """

    def __init__(self):
        rows = db.load_sgg_codes(active_only=False)
        self.sidos = {r["sido_nm"] for r in rows}
        self.name_of = {int(r["sgg_cd"]): r["sgg_nm"] for r in rows}
        self.by_sido: dict[str, list[tuple[str, int]]] = {}
        for r in rows:
            if not r.get("is_active", 1):
                continue    # 옛 코드(광주 29xxx 등)로 매칭되면 화면 필터에서 빠진다
            self.by_sido.setdefault(r["sido_nm"], []).append((r["sgg_nm"], int(r["sgg_cd"])))
        for v in self.by_sido.values():
            v.sort(key=lambda x: -len(x[0]))

        self.by_umd: dict[tuple[str, str], set[int]] = {}
        conn = db._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""SELECT DISTINCT s.sido_nm, a.umd_nm, a.sgg_cd
                                 FROM apartments a JOIN sgg_codes s ON s.sgg_cd = a.sgg_cd
                                WHERE s.is_active = 1 AND a.umd_nm IS NOT NULL""")
                for sido, umd, cd in cur.fetchall():
                    self.by_umd.setdefault((sido, umd), set()).add(int(cd))
        finally:
            conn.close()

    def _sidos(self, token: str | None) -> tuple[str, ...]:
        if not token:
            return ()
        if token in _SIDO_MULTI:
            return _SIDO_MULTI[token]
        if token in self.sidos:
            return (token,)
        full = _SIDO_ALIAS.get(token)
        return (full,) if full in self.sidos else ()

    def _parse(self, text: str):
        text = re.sub(r"\s+", " ", text).strip()
        head, _, rest = text.partition(" ")
        sidos = self._sidos(head)
        if not sidos:
            return None
        rest = re.sub(r"^화성시 (\S+구)(?= |$)", r"화성\1", rest)   # 화성시 동탄구 → 화성동탄구

        for sido in sidos:
            for nm, cd in self.by_sido.get(sido, []):
                if rest == nm or rest.startswith(nm + " "):
                    return sido, nm, cd
        for sido in sidos:
            if sido.startswith("세종") and self.by_sido.get(sido):
                nm, cd = self.by_sido[sido][0]
                return sido, nm, cd

        for tok in rest.split(" "):
            if tok[-1:] in ("동", "읍", "면", "가") and len(tok) >= 2:
                hits = {(sd, cd) for sd in sidos for cd in self.by_umd.get((sd, tok), ())}
                if len(hits) == 1:
                    sido, cd = hits.pop()
                    return sido, self.name_of.get(cd), cd
                break
        tok = rest.split(" ", 1)[0] if rest else ""
        return sidos[0], (tok if tok[-1:] in ("시", "군", "구") else None), None

    def resolve(self, addr: str | None, area_nm: str | None) -> tuple[str | None, str | None, int | None]:
        addr = (addr or "").replace("화성특례시", "화성시")
        parens = re.findall(r"\(([^()]+)\)", addr)
        partial = None
        for t in [addr] + parens:
            r = self._parse(t)
            if r and r[2] is not None:
                return r
            partial = partial or r
        if partial:
            # 괄호 안에 시도 없이 동만 있는 경우: '인천광역시 서구 검단신도시 AA32BL(마전동)'
            sido = partial[0]
            for t in parens:
                for tok in re.split(r"[\s,]+", t):
                    hits = self.by_umd.get((sido, tok))
                    if hits and len(hits) == 1:
                        cd = next(iter(hits))
                        return sido, self.name_of.get(cd), cd
            return partial
        sidos = self._sidos(_s(area_nm))
        return (sidos[0] if sidos else None), None, None


# ─── 공고 ────────────────────────────────────────────────────────────────────


def notice_row(kind: Kind, d: dict, region: RegionIndex) -> dict:
    addr = _s(d.get("HSSPLY_ADRES"), 300)
    area_nm = _s(d.get("SUBSCRPT_AREA_CODE_NM"), 40)
    sido, sgg, sgg_cd = region.resolve(addr, area_nm)

    return {
        "house_manage_no": _s(d.get("HOUSE_MANAGE_NO"), 20),
        "pblanc_no": _s(d.get("PBLANC_NO"), 20),
        "house_nm": _s(d.get("HOUSE_NM"), 200) or "(이름 없음)",
        "house_secd": _s(d.get("HOUSE_SECD"), 10),
        # 청약홈 분류 그대로: APT / 신혼희망타운 / 무순위 / 불법행위 재공급 / 임의공급 …
        "house_secd_nm": _s(d.get("HOUSE_SECD_NM"), 40) or kind.label,
        "house_dtl_secd_nm": _s(_first(d, "HOUSE_DTL_SECD_NM", "HOUSE_DETAIL_SECD_NM"), 40),
        "rent_secd_nm": _s(d.get("RENT_SECD_NM"), 20),
        "subscrpt_area_nm": area_nm,
        "sido_nm": sido,
        "sgg_nm": sgg,
        "sgg_cd": sgg_cd,
        "addr": addr,
        "total_households": _int(d.get("TOT_SUPLY_HSHLDCO")),
        "notice_date": _date(d.get("RCRIT_PBLANC_DE")),
        "rcept_bgnde": _date(_first(d, "RCEPT_BGNDE", "SUBSCRPT_RCEPT_BGNDE", "GNRL_RCEPT_BGNDE")),
        "rcept_endde": _date(_first(d, "RCEPT_ENDDE", "SUBSCRPT_RCEPT_ENDDE", "GNRL_RCEPT_ENDDE")),
        "spsply_bgnde": _date(d.get("SPSPLY_RCEPT_BGNDE")),
        "spsply_endde": _date(d.get("SPSPLY_RCEPT_ENDDE")),
        "winner_date": _date(d.get("PRZWNER_PRESNATN_DE")),
        "contract_bgnde": _date(d.get("CNTRCT_CNCLS_BGNDE")),
        "contract_endde": _date(d.get("CNTRCT_CNCLS_ENDDE")),
        "movein_ym": (lambda v: v if v and len(v) == 6 and v.isdigit() else None)(
            re.sub(r"\D", "", _s(d.get("MVN_PREARNGE_YM")) or "")),
        "developer": _s(d.get("BSNS_MBY_NM"), 200),
        "builder": _s(d.get("CNSTRCT_ENTRPS_NM"), 200),
        "tel": _s(d.get("MDHS_TELNO"), 40),
        "homepage": _s(d.get("HMPG_ADRES"), 300),
        "pblanc_url": _s(d.get("PBLANC_URL"), 500),
        "speclt_rdn_earth_at": _yn(d.get("SPECLT_RDN_EARTH_AT")),
        "mdat_trget_area_at": _yn(d.get("MDAT_TRGET_AREA_SECD")),
        "parcprc_uls_at": _yn(d.get("PARCPRC_ULS_AT")),
        "raw": json.dumps({"kind": kind.key, **d}, ensure_ascii=False),
    }


_NOTICE_COLS = [
    "house_manage_no", "pblanc_no", "house_nm", "house_secd", "house_secd_nm",
    "house_dtl_secd_nm", "rent_secd_nm", "subscrpt_area_nm", "sido_nm", "sgg_nm", "sgg_cd",
    "addr", "total_households", "notice_date", "rcept_bgnde", "rcept_endde",
    "spsply_bgnde", "spsply_endde", "winner_date", "contract_bgnde", "contract_endde",
    "movein_ym", "developer", "builder", "tel", "homepage", "pblanc_url",
    "speclt_rdn_earth_at", "mdat_trget_area_at", "parcprc_uls_at", "raw",
]


def upsert_notices(rows: list[dict]) -> int:
    if not rows:
        return 0
    cols = ", ".join(f"`{c}`" for c in _NOTICE_COLS)
    ph = ", ".join(["%s"] * len(_NOTICE_COLS))
    upd = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in _NOTICE_COLS[2:])
    sql = (f"INSERT INTO presale_notices ({cols}, source, synced_at) VALUES ({ph}, 'applyhome', NOW()) "
           f"ON DUPLICATE KEY UPDATE {upd}, synced_at=NOW()")
    conn = db._conn()
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, [[r[c] for c in _NOTICE_COLS] for r in rows])
        conn.commit()
        return len(rows)
    finally:
        conn.close()


# ─── 주택형 ──────────────────────────────────────────────────────────────────

_TY_AREA = re.compile(r"^\s*(\d+(?:\.\d+)?)")


def type_row(kind: Kind, d: dict) -> dict:
    house_ty = _s(d.get("HOUSE_TY"), 40)
    if not house_ty:
        # 오피스텔·민간임대는 주택형 문자열 대신 군(GP)·타입(TP)을 준다
        house_ty = _s(" ".join(x for x in (_s(d.get("GP")), _s(d.get("TP"))) if x), 40)

    exclu = _float(d.get("EXCLUSE_AR"))
    if exclu is None and house_ty:
        m = _TY_AREA.match(house_ty)     # '084.9812A' → 84.9812
        exclu = float(m.group(1)) if m else None

    special = _int(d.get("SPSPLY_HSHLDCO"))
    if special is None and kind.key == "pvtrent":
        parts = [_int(d.get(k)) for k in ("SPSPLY_AGED_HSHLDCO", "SPSPLY_NEW_MRRG_HSHLDCO", "SPSPLY_YGMN_HSHLDCO")]
        special = sum(p for p in parts if p) if any(p is not None for p in parts) else None

    return {
        "house_manage_no": _s(d.get("HOUSE_MANAGE_NO"), 20),
        "pblanc_no": _s(d.get("PBLANC_NO"), 20),
        "model_no": _s(d.get("MODEL_NO"), 10) or "00",
        "house_ty": house_ty,
        "exclu_ar": exclu,
        "supply_ar": _float(_first(d, "SUPLY_AR", "CNTRCT_AR")),
        "general_hshldco": _int(_first(d, "SUPLY_HSHLDCO", "GNSPLY_HSHLDCO")),
        "special_hshldco": special,
        "top_amount": _int(_first(d, "LTTOT_TOP_AMOUNT", "SUPLY_AMOUNT")),
        "raw": json.dumps({"kind": kind.key, **d}, ensure_ascii=False),
    }


_TYPE_COLS = ["house_manage_no", "pblanc_no", "model_no", "house_ty", "exclu_ar",
              "supply_ar", "general_hshldco", "special_hshldco", "top_amount", "raw"]


def existing_notice_keys() -> set[tuple[str, str]]:
    conn = db._conn()
    try:
        with conn.cursor(pymysql.cursors.Cursor) as cur:
            cur.execute("SELECT house_manage_no, pblanc_no FROM presale_notices")
            return {(a, b) for a, b in cur.fetchall()}
    finally:
        conn.close()


def upsert_types(rows: list[dict]) -> int:
    if not rows:
        return 0
    cols = ", ".join(f"`{c}`" for c in _TYPE_COLS)
    ph = ", ".join(["%s"] * len(_TYPE_COLS))
    upd = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in _TYPE_COLS[3:])
    sql = f"INSERT INTO presale_types ({cols}) VALUES ({ph}) ON DUPLICATE KEY UPDATE {upd}"
    conn = db._conn()
    try:
        with conn.cursor() as cur:
            for i in range(0, len(rows), 1000):
                cur.executemany(sql, [[r[c] for c in _TYPE_COLS] for r in rows[i:i + 1000]])
        conn.commit()
        return len(rows)
    finally:
        conn.close()
