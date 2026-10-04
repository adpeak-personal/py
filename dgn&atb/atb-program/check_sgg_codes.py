"""sgg_codes 점검/교정 — 공공API 가 실제로 인정하는 시군구 코드로 맞춘다.

배경:
  시드(000_atb_db.sql)의 광주/전남/전북 코드가 현행 공공API 와 달라서 해당 42개
  시군구는 실거래가 한 건도 수집되지 않았다. API 를 직접 조회해 확인한 결과:

    · 광주광역시(29xxx) + 전라남도(46xxx) → '전남광주통합특별시'(12xxx) 로 통합
    · 전북특별자치도 45xxx → 52xxx 로 코드 변경

  새 코드로는 실거래 조회가 정상 동작한다(광주 북구 468건, 전주완산구 387건 등).

시도명 처리:
  API 는 통합 시도명 '전남광주통합특별시' 를 쓰지만, DB 에는 기존대로
  '광주광역시' / '전라남도' 를 유지한다. 프론트 지도(KoreaMap)가 GeoJSON 의
  '광주'/'전남' 을 쓰기 때문에 통합명을 넣으면 지도 매칭이 깨진다.
  → 코드만 새 것으로 바꾸고 시도 구분은 코드 범위로 판별한다.

행정구역 개편이 있으면 코드가 바뀌고, 낡은 코드로는 API 가 오류 없이 0건을
돌려주기 때문에 '조용히 아무것도 수집되지 않는' 상태가 된다. 주기적으로 돌려
대조할 것.

사용: python check_sgg_codes.py            # 대조 결과만 출력
     python check_sgg_codes.py --apply    # DB 교정 + 시드 SQL 재작성
"""
from __future__ import annotations

import io
import re
import sys
from collections import Counter, defaultdict

import pymysql
import requests

import config

_URL = "https://apis.data.go.kr/1613000/AptListService4/getTotalAptList4"
_SEED_SQL = "../atb-back/migrations/000_atb_db.sql"

# 통합 시도의 코드 → 원래 시도 구분. 광주 5개 자치구만 광역시, 나머지는 전남.
_GWANGJU_GU = {12210: "동구", 12240: "서구", 12270: "남구",
               12300: "북구", 12330: "광산구"}

# API 는 자치구를 붙여 쓴다(전주완산구). DB 표기(전주시 완산구)로 맞춘다.
_CITY_GU = re.compile(r"^(전주|수원|성남|안양|부천|안산|고양|용인|청주|천안|포항|창원)(.+구)$")


def normalize_sgg_name(name: str) -> str:
    m = _CITY_GU.match(name)
    return f"{m.group(1)}시 {m.group(2)}" if m else name


def fetch_all() -> list[dict]:
    """전국 K-apt 단지 전량 (페이지네이션)."""
    out: list[dict] = []
    page = 1
    while True:
        url = (f"{_URL}?serviceKey={config.DATA_AUTH_KEY}"
               f"&pageNo={page}&numOfRows=1000&_type=json")
        body = requests.get(url, timeout=30).json()["response"]["body"]
        items = body.get("items") or []
        if isinstance(items, dict):
            items = [items]
        out.extend(items)
        total = int(body.get("totalCount") or 0)
        if len(out) >= total or not items:
            break
        page += 1
    return out


def build_map(items: list[dict]) -> dict[int, tuple[str, str]]:
    """bjdCode 앞 5자리 → (시도, 시군구).

    세종처럼 하위 시군구가 없어 as2 가 null 인 경우도 시도명으로 채워 넣는다.
    (이걸 걸러내면 유효한 코드를 '없는 코드'로 오판한다.)
    """
    names: dict[int, Counter] = defaultdict(Counter)
    for it in items:
        bjd = (it.get("bjdCode") or "").strip()
        if len(bjd) < 5 or not bjd[:5].isdigit():
            continue
        sido = (it.get("as1") or "").strip()
        sgg = (it.get("as2") or "").strip() or sido
        if not sido:
            continue
        names[int(bjd[:5])][(sido, sgg)] += 1

    out = {}
    for cd, c in names.items():
        sido, sgg = c.most_common(1)[0][0]
        if sido == "전남광주통합특별시":
            # 통합 이전 구분으로 되돌린다 (지도/통계 호환)
            sido = "광주광역시" if cd in _GWANGJU_GU else "전라남도"
        out[cd] = (sido, normalize_sgg_name(sgg))
    return out


def conn():
    return pymysql.connect(
        host=config.MYSQL_HOST, port=config.MYSQL_PORT,
        user=config.MYSQL_USER, password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def rewrite_seed(api: dict[int, tuple[str, str]], obsolete: set[int]) -> int:
    """시드 SQL 의 시군구 INSERT 블록을 현행 코드로 다시 쓴다.

    시드를 안 고치면 새 서버에 000_atb_db.sql 을 적용할 때 같은 문제가 재발한다.
    """
    s = io.open(_SEED_SQL, encoding="utf-8").read()
    start = s.index("INSERT IGNORE INTO `sgg_codes`")
    end = s.index(";", start) + 1

    # 시도 출력 순서 (기존 시드와 동일하게 유지)
    order = ["서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시",
             "대전광역시", "울산광역시", "세종특별자치시", "경기도", "충청북도",
             "충청남도", "전북특별자치도", "전라남도", "경상북도", "경상남도",
             "제주특별자치도", "강원특별자치도"]

    by_sido: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for cd, (sido, sgg) in api.items():
        if cd in obsolete:
            continue
        by_sido[sido].append((cd, sgg))

    lines = ["INSERT IGNORE INTO `sgg_codes` (`sgg_cd`, `sido_nm`, `sgg_nm`) VALUES"]
    rows: list[str] = []
    for sido in order + sorted(set(by_sido) - set(order)):
        items = sorted(by_sido.get(sido, []))
        if not items:
            continue
        rows.append(f"  -- {sido} ({len(items)})")
        for cd, sgg in items:
            rows.append(f"  ({cd}, '{sido}', '{sgg}'),")
    rows[-1] = rows[-1].rstrip(",") + ";"
    lines.extend(rows)

    io.open(_SEED_SQL, "w", encoding="utf-8", newline="\n").write(
        s[:start] + "\n".join(lines) + s[end:]
    )
    return sum(len(v) for v in by_sido.values())


def main(apply: bool) -> int:
    print("■ K-apt 전국 단지목록 수신...", flush=True)
    api = build_map(fetch_all())
    print(f"  → 시군구 코드 {len(api)}개 추출\n")

    c = conn()
    with c.cursor() as cur:
        cur.execute("SELECT sgg_cd, sido_nm, sgg_nm, is_active FROM sgg_codes")
        rows = list(cur.fetchall())
    db_rows = {r["sgg_cd"]: (r["sido_nm"], r["sgg_nm"]) for r in rows}
    active = {r["sgg_cd"] for r in rows if r["is_active"]}

    # 이미 비활성화한 건 조치 대상이 아니다 — 매번 다시 보고하면 노이즈만 된다.
    obsolete = sorted((set(db_rows) - set(api)) & active)  # 살아있는데 API 가 모름
    missing = sorted(set(api) - set(db_rows))              # 시드에 없는 = 누락 지역
    already = len((set(db_rows) - set(api)) - active)

    print(f"■ 폐지된 코드 {len(obsolete)}개 (수집 불가 → 비활성화 필요)"
          + (f"   [이미 비활성 {already}개는 생략]" if already else ""))
    for cd in obsolete:
        print(f"    {cd}  {db_rows[cd][0]} {db_rows[cd][1]}")
    print(f"\n■ 누락된 코드 {len(missing)}개 (추가)")
    for cd in missing:
        print(f"    {cd}  {api[cd][0]} {api[cd][1]}")

    if not obsolete and not missing:
        print()
        print("→ 시드가 현행 공공API 와 일치한다. 조치 불필요.")
        return 0

    if not apply:
        print("\n(--apply 를 주면 DB 와 시드 SQL 을 교정한다)")
        return 0

    with c.cursor() as cur:
        if obsolete:
            # 삭제하지 않는다 — 이미 붙은 거래/단지의 FK 참조가 깨진다.
            cur.executemany("UPDATE sgg_codes SET is_active=0 WHERE sgg_cd=%s",
                            [(cd,) for cd in obsolete])
        if missing:
            cur.executemany(
                "INSERT IGNORE INTO sgg_codes (sgg_cd, sido_nm, sgg_nm) VALUES (%s,%s,%s)",
                [(cd, api[cd][0], api[cd][1]) for cd in missing],
            )
    c.commit()
    print(f"\n→ DB: 비활성 {len(obsolete)} / 추가 {len(missing)}")

    n = rewrite_seed(api, set())
    print(f"→ 시드 SQL 재작성: {n}개 시군구")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv))
