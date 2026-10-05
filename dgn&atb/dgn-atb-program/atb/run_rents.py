"""전월세 실거래 수집 (CLI).

시군구 × 계약월 단위로 국토교통부 전월세 API 를 전량 페이지네이션하며 DB 에 넣는다.
아파트와 오피스텔이 서로 다른 서비스라 유형을 지정한다.

사용:
  python run_rents.py 11680 202609                    # 강남구 아파트 전월세
  python run_rents.py --type=OFFI 11680 202609        # 강남구 오피스텔 전월세
  python run_rents.py --all 202607-202609             # 전국 아파트 3개월
  python run_rents.py --all --recent                  # 전국, 최근 3년 (--years 로 조절)
  python run_rents.py --all --recent --years=1        # 전국, 최근 1년

매매보다 건수가 훨씬 많다 — 강남구 한 달이 아파트 매매 75건인데 전월세는 1,049건이다.
전국 3년이면 수백만 건이라, 한 번에 다 받으려 하지 말고 월 범위를 쪼개 돌리는 편이 낫다.
--recent 는 오래된 달부터 채우므로 중간에 끊겨도 다시 돌리면 이어진다.

저장은 멱등하다 (transaction_key UNIQUE + INSERT IGNORE).
종료코드: 0 성공 / 1 일부 실패 / 2 API 일일 한도
"""
from __future__ import annotations

import re
import sys
from datetime import date

from services import db, rent_api

_YM = re.compile(r"^\d{6}$")
_YM_RANGE = re.compile(r"^(\d{6})-(\d{6})$")

DEFAULT_YEARS = 3          # 사장님이 정한 보관 기간
PAGE_ROWS = 1000


def _opt(argv: list[str], name: str, default: str) -> str:
    """--name=값 과 --name 값 둘 다 받는다 (전에 '=' 만 받아 조용히 무시된 적이 있다)."""
    for i, a in enumerate(argv):
        if a == f"--{name}":
            return argv[i + 1] if i + 1 < len(argv) else default
        if a.startswith(f"--{name}="):
            return a.split("=", 1)[1]
    return default


def _expand_months(token: str) -> list[str]:
    if _YM.match(token):
        return [token]
    m = _YM_RANGE.match(token)
    if not m:
        raise ValueError(f"계약월 형식 오류: {token} (YYYYMM 또는 YYYYMM-YYYYMM)")
    start, end = m.group(1), m.group(2)
    y, mo = int(start[:4]), int(start[4:])
    ey, emo = int(end[:4]), int(end[4:])
    if (ey, emo) < (y, mo):
        raise ValueError(f"계약월 범위가 거꾸로입니다: {token}")
    out: list[str] = []
    while (y, mo) <= (ey, emo):
        out.append(f"{y}{mo:02d}")
        mo += 1
        if mo == 13:
            y, mo = y + 1, 1
    return out


def _recent_months(years: int) -> list[str]:
    """오래된 달부터 이번 달까지. 중간에 끊겨도 다시 돌리면 이어지게 오름차순."""
    today = date.today()
    months = years * 12
    out: list[str] = []
    y, mo = today.year, today.month
    for _ in range(months):
        out.append(f"{y}{mo:02d}")
        mo -= 1
        if mo == 0:
            y, mo = y - 1, 12
    return sorted(out)


def collect(property_type: str, sgg_cd: str, deal_ymd: str) -> int:
    """시군구 × 계약월 1건 수집. 저장된(신규) 행 수."""
    saved = 0
    page = 1
    while True:
        res = rent_api.fetch_rents(property_type, sgg_cd, deal_ymd,
                                   page_no=page, num_of_rows=PAGE_ROWS)
        if not res.items:
            break
        saved += db.save_rents(res.items, property_type)
        if page * PAGE_ROWS >= res.totalCount:
            break
        page += 1
    return saved


def main(argv: list[str]) -> int:
    flags = {a.split("=")[0] for a in argv if a.startswith("--")}
    property_type = _opt(argv, "type", "APT").upper()
    years = int(_opt(argv, "years", str(DEFAULT_YEARS)) or DEFAULT_YEARS)

    if property_type not in rent_api.SERVICES:
        print(f"✗ 전월세를 지원하지 않는 유형: {property_type} "
              f"(가능: {', '.join(rent_api.SERVICES)})")
        return 1

    # --type/--years 의 값이 위치 인자로 섞이지 않게 걸러낸다
    consumed = {property_type, str(years), _opt(argv, "type", ""), _opt(argv, "years", "")}
    args = [a.strip() for a in argv
            if not a.startswith("--") and a.strip() and a.strip() not in consumed]

    months: list[str] = []
    sggs: list[str] = []
    for a in args:
        if _YM.match(a) or _YM_RANGE.match(a):
            months.extend(_expand_months(a))
        else:
            sggs.append(a)

    if "--recent" in flags and not months:
        months = _recent_months(years)
    if "--all" in flags:
        sggs = [str(r["sgg_cd"]) for r in db.load_sgg_codes(active_only=True)]

    if not sggs or not months:
        print(__doc__)
        return 1

    total_req = len(sggs) * len(months)
    print(f"■ {property_type} 전월세 — 시군구 {len(sggs)}개 × {len(months)}개월 "
          f"= {total_req}건 요청 ({months[0]}~{months[-1]})\n")

    grand = 0
    failed: list[str] = []
    for ym in months:
        month_saved = 0
        for i, sgg in enumerate(sggs, 1):
            try:
                n = collect(property_type, sgg, ym)
                month_saved += n
                grand += n
                if len(sggs) <= 10:
                    print(f"  [{i}/{len(sggs)}] {sgg} {ym}  저장 {n}건")
            except rent_api.RentApiError as e:
                msg = str(e)
                # 일일 한도는 더 해봐야 소용없다 — 받은 것까지 두고 멈춘다
                if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in msg or "한도" in msg:
                    print(f"\n✗ 일일 한도 초과 ({sgg} {ym} 에서 중단). 받은 건은 저장됨.")
                    print(f"  → 총 저장 {grand}건. 한도가 풀리면 같은 명령을 다시 돌리면 이어진다.")
                    return 2
                failed.append(f"{sgg} {ym}")
                print(f"  ✗ {sgg} {ym}: {msg[:110]}")
            except Exception as e:
                failed.append(f"{sgg} {ym}")
                print(f"  ✗ {sgg} {ym}: {type(e).__name__} {str(e)[:110]}")
        if len(sggs) > 10:
            print(f"  {ym}  저장 {month_saved}건  (누적 {grand}건)")

    print(f"\n→ 총 저장 {grand}건, 실패 {len(failed)}건")
    if failed:
        print(f"  실패: {', '.join(failed[:30])}{' ...' if len(failed) > 30 else ''}")
        print("  같은 명령을 다시 돌리면 실패분만 다시 받는다 (저장은 멱등).")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
