"""아파트 매매 실거래가 수집 (CLI).

GUI(main.py) 없이 헤드리스로 도는 수집 워커. 시군구 × 거래월 단위로
국토교통부 실거래가 API 를 전량 페이지네이션하며 DB 에 저장한다.

사용:
  python run_trades.py 11680 202607                 # 강남구 2026년 7월
  python run_trades.py 11680 11650 11710 202607     # 여러 시군구, 같은 월
  python run_trades.py 11680 202605-202607          # 강남구 3개월치
  python run_trades.py --all 202607                 # sgg_codes 활성 전체 (256개)

저장은 멱등하다 (transaction_key UNIQUE + INSERT IGNORE). 같은 명령을 다시
돌려도 중복 행이 생기지 않고, 이미 있는 건은 저장 0건으로 집계된다.

선행: MySQL 기동 + migrations/000_atb_db.sql 적용 + .env 의 DATA_AUTH_KEY.
"""
from __future__ import annotations

import re
import sys

from services import apt_api, db

_YM = re.compile(r"^\d{6}$")
_YM_RANGE = re.compile(r"^(\d{6})-(\d{6})$")


def _expand_months(token: str) -> list[str]:
    """'202607' → ['202607'],  '202605-202607' → ['202605','202606','202607']"""
    if _YM.match(token):
        return [token]

    m = _YM_RANGE.match(token)
    if not m:
        raise ValueError(f"거래월 형식 오류: {token} (YYYYMM 또는 YYYYMM-YYYYMM)")

    start, end = m.group(1), m.group(2)
    y, mo = int(start[:4]), int(start[4:])
    ey, emo = int(end[:4]), int(end[4:])
    if (ey, emo) < (y, mo):
        raise ValueError(f"거래월 범위가 거꾸로입니다: {token}")

    out: list[str] = []
    while (y, mo) <= (ey, emo):
        out.append(f"{y}{mo:02d}")
        mo += 1
        if mo == 13:
            y, mo = y + 1, 1
    return out


def collect(sgg_cd: str, deal_ymd: str) -> int:
    """시군구 × 거래월 1건 수집. 저장된(신규) 행 수 반환."""
    saved_total = 0
    page = 1

    while True:
        result = apt_api.fetch_apt_trades(
            lawd_cd=sgg_cd, deal_ymd=deal_ymd, page_no=page, num_of_rows=1000,
        )
        if not result.items:
            break

        saved_total += db.save_apt_trades(result.items)

        if page * 1000 >= result.totalCount:
            break
        page += 1

    return saved_total


def main(argv: list[str]) -> int:
    flags = {a.strip() for a in argv if a.startswith("--")}
    # 파이프로 코드를 넘길 때 개행/공백이 섞여 들어오면 API 가
    # '모르는 코드'로 보고 오류 없이 0건을 돌려준다
    # → 조용히 아무것도 수집되지 않는다. 미리 턴다.
    args = [a.strip() for a in argv if not a.startswith("--") and a.strip()]

    months: list[str] = []
    sggs: list[str] = []
    for a in args:
        if _YM.match(a) or _YM_RANGE.match(a):
            months.extend(_expand_months(a))
        else:
            sggs.append(a)

    if "--all" in flags:
        sggs = [str(r["sgg_cd"]) for r in db.load_sgg_codes(active_only=True)]

    if not sggs or not months:
        print(__doc__)
        return 1

    print(f"■ 대상: 시군구 {len(sggs)}개 × {len(months)}개월 = {len(sggs) * len(months)}건 요청\n")

    grand_total = 0
    failed: list[str] = []

    for ym in months:
        for i, sgg in enumerate(sggs, 1):
            label = f"{sgg} {ym}"
            try:
                saved = collect(sgg, ym)
                grand_total += saved
                print(f"  [{i}/{len(sggs)}] {label}  저장 {saved}건")
            except Exception as e:
                failed.append(label)
                print(f"  [{i}/{len(sggs)}] {label}  실패: {e}")

    print(f"\n→ 총 저장 {grand_total}건, 실패 {len(failed)}건")
    if failed:
        print(f"  실패 목록: {', '.join(failed)}")

    # 단지별 전용면적 목록 갱신 (프론트 평형 필터용 파생 데이터)
    if grand_total > 0:
        updated = db.refresh_exclu_areas([int(s) for s in sggs])
        print(f"→ exclu_areas 갱신: 단지 {updated}건")

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
