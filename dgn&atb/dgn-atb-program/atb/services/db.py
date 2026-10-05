"""MySQL 저장.

apartments(단지) upsert → apartment_deals / property_rents insert → apt_id 연결.
모두 INSERT IGNORE 로 중복 무시.

주택 유형(property_type: APT / OFFI)은 단지와 거래 양쪽에 둔다. 같은 지번에
같은 이름의 아파트와 오피스텔이 있을 수 있어 단지 유니크 키에도 들어간다.
"""
from __future__ import annotations

import hashlib
import json

import pymysql

import config
from services.apt_api import AptTradeItem
from services.rent_api import RentItem


def _conn():
    return pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
        charset="utf8mb4",
        autocommit=False,
    )


def load_sgg_codes(active_only: bool = False) -> list[dict]:
    """sgg_codes(시군구 마스터) 조회. [{sgg_cd, sido_nm, sgg_nm, is_active}, ...]."""
    sql = ("SELECT sgg_cd, sido_nm, sgg_nm, is_active FROM sgg_codes "
           + ("WHERE is_active = 1 " if active_only else "")
           + "ORDER BY sido_nm, sgg_cd")
    conn = _conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql)
            return list(cur.fetchall())
    finally:
        conn.close()


def _to_int(val, default=None):
    try:
        return int(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return default


def _to_area(val):
    """전용면적. DECIMAL(7,4) 로 들어가므로 수치형으로 만들어 넘긴다."""
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _parse_item(item: AptTradeItem, property_type: str = "APT") -> dict:
    """API 아이템 → DB row dict."""
    amount = _to_int(item.dealAmount, 0)
    y = _to_int(item.dealYear, 0)
    m = _to_int(item.dealMonth, 0)
    d = _to_int(item.dealDay, 0)
    deal_date = f"{y:04d}-{m:02d}-{d:02d}"

    sgg_cd = item.sggCd or ""
    key_src = f"{sgg_cd}_{item.aptNm}_{item.aptDong}_{deal_date}_{item.floor}_{item.excluUseAr}_{amount}"
    # 아파트 키는 건드리지 않는다 — 식을 바꾸면 이미 쌓인 61만 건이 전부 새 키가 되어
    # 다음 수집에서 중복으로 다시 들어온다. 다른 유형만 앞에 유형을 붙인다.
    if property_type != "APT":
        key_src = f"{property_type}_{key_src}"
    transaction_key = hashlib.md5(key_src.encode("utf-8")).hexdigest()

    return {
        "transaction_key": transaction_key,
        "property_type": property_type,
        "sgg_cd": _to_int(sgg_cd),
        "umd_nm": item.umdNm,
        "jibun": str(item.jibun or ""),
        "apt_nm": item.aptNm,
        "apt_dong": str(item.aptDong or ""),
        "build_year": _to_int(item.buildYear),
        "deal_amount": amount,
        "deal_date": deal_date,
        "deal_year": y,
        "deal_month": m,
        "deal_day": d,
        "exclu_use_ar": _to_int(item.excluUseAr) if "." not in str(item.excluUseAr)
        else float(item.excluUseAr),
        "floor": _to_int(item.floor),
        "dealing_gbn": item.dealingGbn or None,
        "buyer_gbn": item.buyerGbn or None,
        "sler_gbn": item.slerGbn or None,
        "land_leasehold_gbn": item.landLeaseholdGbn or "N",
        "cdeal_type": item.cdealType or None,
        "cdeal_day": item.cdealDay or None,
        "estate_agent_sgg_nm": item.estateAgentSggNm or None,
        "rgst_date": item.rgstDate or None,
    }


def save_apt_trades(items: list[AptTradeItem], property_type: str = "APT") -> int:
    """매매 거래 목록 저장. 신규 저장된 거래 건수 반환."""
    if not items:
        return 0

    rows = [_parse_item(it, property_type) for it in items]
    conn = _conn()
    try:
        with conn.cursor() as cur:
            # 1. 배치 내 unique 단지만 apartments upsert
            seen: set[str] = set()
            for r in rows:
                key = f"{property_type}_{r['sgg_cd']}_{r['apt_nm']}_{r['jibun']}"
                if key in seen:
                    continue
                seen.add(key)
                cur.execute(
                    "INSERT IGNORE INTO apartments "
                    "(property_type, sgg_cd, umd_nm, jibun, apt_nm, build_year) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (property_type, r["sgg_cd"], r["umd_nm"], r["jibun"], r["apt_nm"],
                     r["build_year"]),
                )

            # 2. apartment_deals INSERT IGNORE (배치)
            columns = list(rows[0].keys())
            placeholders = "(" + ",".join(["%s"] * len(columns)) + ")"
            all_ph = ",".join([placeholders] * len(rows))
            values: list = []
            for r in rows:
                values.extend(r[c] for c in columns)
            cur.execute(
                f"INSERT IGNORE INTO apartment_deals ({','.join(columns)}) VALUES {all_ph}",
                values,
            )
            saved = cur.rowcount

            # 3. apt_id 연결 (NULL 인 것만)
            cur.execute(
                "UPDATE apartment_deals d "
                "JOIN apartments a "
                "  ON a.property_type = d.property_type "
                " AND a.sgg_cd = d.sgg_cd AND a.apt_nm = d.apt_nm "
                " AND COALESCE(a.jibun, '') = COALESCE(d.jibun, '') "
                "SET d.apt_id = a.id WHERE d.apt_id IS NULL"
            )
        conn.commit()
        return saved
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── 전용면적 파생 (apartment_deals → apartments.exclu_areas) ──────────────────
# ─── 전월세 ───────────────────────────────────────────────────────────────────
def _parse_rent(item: RentItem, property_type: str) -> dict:
    """전월세 API 아이템 → property_rents row dict."""
    y = _to_int(item.dealYear, 0)
    m = _to_int(item.dealMonth, 0)
    d = _to_int(item.dealDay, 0)
    deal_date = f"{y:04d}-{m:02d}-{d:02d}"

    sgg_cd = item.sggCd or ""
    deposit = _to_int(item.deposit, 0)
    monthly = _to_int(item.monthlyRent, 0)
    area = _to_area(item.excluUseAr)
    floor = _to_int(item.floor)
    ctype = item.contractType or ""
    cterm = item.contractTerm or ""

    # 전월세는 등기일·해제일이 없어 매매처럼 키를 만들 수 없다. 계약 조건까지
    # 넣어 같은 날 같은 호의 같은 조건이면 한 건으로 본다 (사실상 중복신고).
    key_src = "|".join([
        property_type, str(sgg_cd), item.houseNm, str(item.jibun or ""), deal_date,
        str(floor), f"{area:.4f}", str(deposit), str(monthly), ctype, cterm,
    ])

    return {
        "transaction_key": hashlib.md5(key_src.encode("utf-8")).hexdigest(),
        "property_type": property_type,
        "sgg_cd": _to_int(sgg_cd),
        "umd_nm": item.umdNm,
        "jibun": str(item.jibun or ""),
        "apt_nm": item.houseNm,
        "build_year": _to_int(item.buildYear),
        "deal_date": deal_date,
        "deal_year": y,
        "deal_month": m,
        "deal_day": d,
        "deposit": deposit,
        "monthly_rent": monthly,
        "exclu_use_ar": area,
        "floor": floor,
        "contract_term": cterm or None,
        "contract_type": ctype or None,
        "pre_deposit": _to_int(item.preDeposit),
        "pre_monthly_rent": _to_int(item.preMonthlyRent),
        "use_rr_right": item.useRRRight or None,
    }


def save_rents(items: list[RentItem], property_type: str = "APT") -> int:
    """전월세 목록 저장. 신규 저장된 건수 반환.

    매매가 없는 단지도 단지 마스터에 넣는다 — 안 넣으면 전월세 행이 apt_id 없이
    떠돌아 단지 화면에서 전세가율을 낼 수 없다. 단지 목록(listApts)은 매매를
    INNER JOIN 하므로 거래 없는 단지가 목록에 끼지는 않는다.
    """
    if not items:
        return 0

    rows = [_parse_rent(it, property_type) for it in items]
    # 면적·날짜가 깨진 건은 버린다 (DECIMAL/DATE 에 못 들어간다)
    rows = [r for r in rows if r["exclu_use_ar"] > 0 and r["deal_year"] > 0 and r["apt_nm"]]
    if not rows:
        return 0

    conn = _conn()
    try:
        with conn.cursor() as cur:
            seen: set[str] = set()
            for r in rows:
                key = f"{property_type}_{r['sgg_cd']}_{r['apt_nm']}_{r['jibun']}"
                if key in seen:
                    continue
                seen.add(key)
                cur.execute(
                    "INSERT IGNORE INTO apartments "
                    "(property_type, sgg_cd, umd_nm, jibun, apt_nm, build_year) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (property_type, r["sgg_cd"], r["umd_nm"], r["jibun"], r["apt_nm"],
                     r["build_year"]),
                )

            # rent_type 은 생성 컬럼이라 넣지 않는다 (monthly_rent 로 자동 계산)
            columns = list(rows[0].keys())
            ph = "(" + ",".join(["%s"] * len(columns)) + ")"
            values: list = []
            for r in rows:
                values.extend(r[c] for c in columns)
            cur.execute(
                f"INSERT IGNORE INTO property_rents ({','.join(columns)}) VALUES "
                + ",".join([ph] * len(rows)),
                values,
            )
            saved = cur.rowcount

            cur.execute(
                "UPDATE property_rents r "
                "JOIN apartments a "
                "  ON a.property_type = r.property_type "
                " AND a.sgg_cd = r.sgg_cd AND a.apt_nm = r.apt_nm "
                " AND COALESCE(a.jibun, '') = COALESCE(r.jibun, '') "
                "SET r.apt_id = a.id WHERE r.apt_id IS NULL"
            )
        conn.commit()
        return saved
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def refresh_exclu_areas(sgg_cds: list | None = None) -> int:
    """apartments.exclu_areas 를 그 단지 거래들의 전용면적 종류(JSON 배열)로 갱신.

    apt_id 로 연결된 거래에서 distinct 전용면적을 모은다. sgg_cds 지정 시 해당
    시군구 단지만 갱신(저장 직후 호출용). 갱신된 단지 수 반환.
    """
    where = "WHERE d.apt_id IS NOT NULL"
    params: tuple = ()
    if sgg_cds:
        ph = ",".join(["%s"] * len(sgg_cds))
        where += f" AND d.sgg_cd IN ({ph})"
        params = tuple(int(x) for x in sgg_cds)

    sql = f"""
        UPDATE apartments a
        JOIN (
          SELECT apt_id, JSON_ARRAYAGG(ar) AS areas
          FROM (
            SELECT DISTINCT d.apt_id, d.exclu_use_ar AS ar
            FROM apartment_deals d
            {where}
            ORDER BY d.apt_id, d.exclu_use_ar
          ) t
          GROUP BY apt_id
        ) s ON s.apt_id = a.id
        SET a.exclu_areas = s.areas
    """
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            affected = cur.rowcount
        conn.commit()
        return affected
    finally:
        conn.close()


# ─── 이미지 검수 상태 ──────────────────────────────────────────────────────────
def get_pending_image_apartments(limit: int | None = None) -> list[dict]:
    """이미지 미검수(image_status=0) 단지 목록.

    신규 건물만 검수하기 위함. 기존 건물은 이미 status 1(있음)/2(없음) 이라
    여기 안 잡히므로, 거래가 아무리 많아도 '신규 건물 수'만큼만 검수한다.
    """
    sql = ("SELECT id, apt_nm, umd_nm, jibun FROM apartments "
           "WHERE image_status = 0 ORDER BY id")
    params: tuple = ()
    if limit is not None:
        sql += " LIMIT %s"
        params = (limit,)
    conn = _conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())
    finally:
        conn.close()


def set_apartment_image(apt_id: int, image_url: str, source: str = "naver") -> None:
    """검수 통과 이미지 1장 저장 → image_status=1 (검수완료·이미지있음)."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE apartments "
                "SET thumbnail_url = %s, thumbnail_source = %s, "
                "    image_status = 1, image_checked_at = NOW() "
                "WHERE id = %s",
                (image_url, source, apt_id),
            )
        conn.commit()
    finally:
        conn.close()


def mark_apartment_no_image(apt_id: int) -> None:
    """검수했으나 통과 이미지 없음 → image_status=2 (다시 검수하지 않음)."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE apartments "
                "SET image_status = 2, image_checked_at = NOW() "
                "WHERE id = %s",
                (apt_id,),
            )
        conn.commit()
    finally:
        conn.close()


# ─── K-apt 단지 마스터 (kapt_complexes) ────────────────────────────────────────
_KAPT_COLUMNS = [
    "kapt_code", "kapt_name", "sgg_cd", "sido_nm", "sgg_nm", "umd_nm", "bjd_code",
    "addr_jibun", "addr_road", "jibun", "total_households", "dong_cnt", "top_floor",
    "use_apr_date", "heat_type", "hall_type", "sale_type", "builder", "total_area",
    "parking_total", "cctv_cnt", "raw",
]


def upsert_kapt_complexes(rows: list[dict]) -> int:
    """kapt_complexes 배치 upsert (INSERT ... ON DUPLICATE KEY UPDATE). 처리 행수 반환."""
    if not rows:
        return 0

    cols = _KAPT_COLUMNS
    # synced_at 을 insert/update 양쪽 모두 NOW() 로 기록 — '최근 동기화 건너뛰기'가
    # 신규 insert 에도 동작하도록 (update 때만 기록하면 새 단지가 늘 NULL 이 됨).
    placeholders = "(" + ",".join(["%s"] * len(cols)) + ", NOW())"
    updates = ",".join(f"{c}=VALUES({c})" for c in cols if c != "kapt_code")
    sql = (f"INSERT INTO kapt_complexes ({','.join(cols)}, synced_at) VALUES {placeholders} "
           f"ON DUPLICATE KEY UPDATE {updates}, synced_at=NOW()")

    conn = _conn()
    try:
        with conn.cursor() as cur:
            for r in rows:
                vals = [json.dumps(r.get(c), ensure_ascii=False) if c == "raw" else r.get(c)
                        for c in cols]
                cur.execute(sql, vals)
        conn.commit()
        return len(rows)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_kapt_missing_detail(limit: int | None = None,
                            sido_prefix: int | None = None) -> list[dict]:
    """상세정보가 비어 있는 단지 [{kapt_code, kapt_name}, ...].

    기본정보는 이미 있고 상세만 없는 단지다. sync_sigungu 로 다시 돌리면
    기본정보까지 또 받아 호출이 2배 들어서, 상세만 1회씩 채우려고 따로 뽑는다.
    """
    sql = ("SELECT kapt_code, kapt_name FROM kapt_complexes "
           "WHERE COALESCE(JSON_LENGTH(raw->'$.dtl'), 0) = 0")
    params: tuple = ()
    if sido_prefix is not None:
        sql += " AND sgg_cd DIV 1000 = %s"
        params = (sido_prefix,)
    sql += " ORDER BY kapt_code"
    if limit:
        sql += f" LIMIT {int(limit)}"

    conn = _conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())
    finally:
        conn.close()


def get_kapt_with_detail(limit: int | None = None,
                         sido_prefix: int | None = None) -> list[dict]:
    """상세 원본이 있는 단지 [{kapt_code, dtl}, ...]. 매핑만 다시 돌릴 때 쓴다."""
    sql = ("SELECT kapt_code, raw->'$.dtl' AS dtl FROM kapt_complexes "
           "WHERE COALESCE(JSON_LENGTH(raw->'$.dtl'), 0) > 0")
    params: tuple = ()
    if sido_prefix is not None:
        sql += " AND sgg_cd DIV 1000 = %s"
        params = (sido_prefix,)
    sql += " ORDER BY kapt_code"
    if limit:
        sql += f" LIMIT {int(limit)}"

    conn = _conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, params)
            rows = list(cur.fetchall())
        for r in rows:
            if isinstance(r["dtl"], str):
                r["dtl"] = json.loads(r["dtl"])
        return rows
    finally:
        conn.close()


def update_kapt_detail(kapt_code: str, fields: dict, dtl: dict) -> None:
    """상세 컬럼들 + raw.dtl 갱신. 기본정보(raw.bass)는 건드리지 않는다."""
    cols = [k for k in fields]
    sets = ", ".join(f"`{c}` = %s" for c in cols)
    vals = [fields[c] for c in cols]

    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE kapt_complexes "
                f"SET {sets}, "
                f"    raw = JSON_SET(COALESCE(raw, JSON_OBJECT()), '$.dtl', CAST(%s AS JSON)), "
                f"    synced_at = NOW() "
                f"WHERE kapt_code = %s",
                (*vals, json.dumps(dtl, ensure_ascii=False), kapt_code),
            )
        conn.commit()
    finally:
        conn.close()


def get_recent_kapt_codes(within_days: int) -> set:
    """최근 within_days 일 내 동기화된 kapt_code 집합 (재동기화 건너뛰기용)."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT kapt_code FROM kapt_complexes "
                "WHERE synced_at >= NOW() - INTERVAL %s DAY", (within_days,))
            return {r[0] for r in cur.fetchall()}
    finally:
        conn.close()


def get_kapt_master(sgg_cd: int) -> list[dict]:
    """매칭용 마스터: 시군구의 K-apt 단지 [{kapt_code, kapt_name, umd_nm, jibun}, ...]."""
    conn = _conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT kapt_code, kapt_name, umd_nm, jibun FROM kapt_complexes "
                "WHERE sgg_cd = %s", (sgg_cd,))
            return list(cur.fetchall())
    finally:
        conn.close()


# ─── 매칭 결과 반영 (apartments) ───────────────────────────────────────────────
# K-apt 에 없던 단지를 다시 매칭해 보는 간격. 마스터에 새 단지가 올라오면 그때
# 붙을 수 있으니 아주 버리지는 않되, 매일 같은 결과를 다시 내게 하지도 않는다.
REMATCH_AFTER_DAYS = 7


def get_unmatched_apartments(sgg_cd: int | None = None) -> list[dict]:
    """매칭할 단지 [{id, apt_nm, umd_nm, jibun}, ...].

    두 가지를 집는다.
      - match_status=0 : 아직 한 번도 매칭을 안 해본 단지
      - match_status=5 : 해봤지만 K-apt 에 없던 단지 — REMATCH_AFTER_DAYS 마다 한 번
    """
    sql = ("SELECT id, apt_nm, umd_nm, jibun FROM apartments "
           "WHERE (match_status = 0 OR (match_status = 5 AND (matched_at IS NULL "
           "       OR matched_at < NOW() - INTERVAL %s DAY)))")
    params: tuple = (REMATCH_AFTER_DAYS,)
    if sgg_cd is not None:
        sql += " AND sgg_cd = %s"
        params = (REMATCH_AFTER_DAYS, sgg_cd)
    sql += " ORDER BY id"
    conn = _conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())
    finally:
        conn.close()


# ─── 지오코딩 ─────────────────────────────────────────────────────────────────
def get_pending_geocode(limit: int | None = None, retry_errors: bool = True) -> list[dict]:
    """좌표가 없는 단지와 그 최선의 주소.

    주소 우선순위: K-apt 도로명 > K-apt 지번 > 실거래 기반 조합.
    '주소로 못찾음(2)' 은 같은 주소로 다시 물어도 결과가 같으므로 기본 제외하고,
    '오류(3)' 만 재시도 대상에 넣는다.
    """
    statuses = "(0, 3)" if retry_errors else "(0)"
    sql = f"""
        SELECT a.id,
               COALESCE(
                 NULLIF(k.addr_road, ''),
                 NULLIF(k.addr_jibun, ''),
                 CONCAT_WS(' ', s.sido_nm, s.sgg_nm, a.umd_nm, a.jibun)
               ) AS address,
               a.apt_nm
          FROM apartments a
          JOIN sgg_codes s ON s.sgg_cd = a.sgg_cd
          LEFT JOIN kapt_complexes k ON k.kapt_code = a.kapt_code
         WHERE a.geocode_status IN {statuses}
           AND (a.lat IS NULL OR a.lng IS NULL)
         ORDER BY a.id
    """
    if limit:
        sql += f" LIMIT {int(limit)}"

    conn = _conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql)
            return list(cur.fetchall())
    finally:
        conn.close()


def set_apartment_coord(apt_id: int, lat: float, lng: float) -> None:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE apartments SET lat=%s, lng=%s, geocode_status=1, geocoded_at=NOW() "
                "WHERE id=%s",
                (lat, lng, apt_id),
            )
        conn.commit()
    finally:
        conn.close()


def mark_geocode_failed(apt_id: int, status: int) -> None:
    """status 2: 주소로 못찾음(재시도 무의미) / 3: 오류(다음 실행에서 재시도)."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE apartments SET geocode_status=%s, geocoded_at=NOW() WHERE id=%s",
                (status, apt_id),
            )
        conn.commit()
    finally:
        conn.close()


def reset_matches(sgg_cd: int | None = None) -> int:
    """매칭 결과 초기화 (match_status=0 — '안 해봄'). 매처를 개선한 뒤 전량 재매칭할 때 쓴다.

    get_unmatched_apartments() 는 '안 해봄(0)' 과 'K-apt 에 없음(5)' 만 집으므로,
    초기화 없이는 이미 매칭된 단지가 새 로직으로 다시 평가되지 않는다.
    """
    sql = ("UPDATE apartments SET kapt_code = NULL, match_status = 0, "
           "match_method = NULL, matched_at = NULL")
    params: tuple = ()
    if sgg_cd is not None:
        sql += " WHERE sgg_cd = %s"
        params = (sgg_cd,)
    conn = _conn()
    try:
        with conn.cursor() as cur:
            n = cur.execute(sql, params)
        conn.commit()
        return n
    finally:
        conn.close()


def update_apartment_match(apt_id: int, kapt_code: str | None,
                           status_code: int, method: str) -> None:
    """매칭 결과 저장. kapt_code 는 자동확정(confirmed/matched)일 때만 채운다."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE apartments "
                "SET kapt_code = %s, match_status = %s, match_method = %s, matched_at = NOW() "
                "WHERE id = %s",
                (kapt_code, status_code, method or None, apt_id),
            )
        conn.commit()
    finally:
        conn.close()
