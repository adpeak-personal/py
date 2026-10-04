"""청약홈 분양정보 수집 (CLI).

공고 전량이 수천 건이라 매번 전체를 다시 받아도 호출이 60회 남짓이다.
그래서 '신규만' 판별 없이 전량을 받아 upsert 한다 — 공고가 정정되면(접수일 변경 등)
그대로 반영된다.

사용:
  python run_presale.py                  # 5종 전량 (APT·무순위·오피스텔·민간임대·임의공급)
  python run_presale.py --recent         # 종류별 앞 1페이지(최신 500건)만 — 매일 돌리는 용도
  python run_presale.py --kind apt       # 한 종류만 (apt/remndr/officetel/pvtrent/opt)
  python run_presale.py --no-types       # 주택형(평형·분양가) 생략

선행: .env 의 DATA_AUTH_KEY + data.go.kr 15098547 활용신청
"""
from __future__ import annotations

import sys

import config
from services import presale_api, presale_sync


def _progress(op: str, got: int, total: int):
    end = "\n" if got >= total else "\r"
    print(f"    {op}: {got:,}/{total:,}", end=end, flush=True)


def main(argv: list[str]) -> int:
    flags = set(a for a in argv if a.startswith("--"))
    kind_arg = None
    if "--kind" in argv:
        i = argv.index("--kind")
        kind_arg = argv[i + 1] if i + 1 < len(argv) else None

    kinds = [k for k in presale_api.KINDS if not kind_arg or k.key == kind_arg]
    if not kinds:
        print(f"✗ 알 수 없는 종류: {kind_arg} "
              f"(가능: {', '.join(k.key for k in presale_api.KINDS)})")
        return 1
    if not config.DATA_AUTH_KEY:
        print(f"✗ DATA_AUTH_KEY 가 설정되지 않았습니다 ({config.ENV_PATH}).")
        return 1

    max_pages = 1 if "--recent" in flags else None
    with_types = "--no-types" not in flags
    region = presale_sync.RegionIndex()

    total_n = total_t = 0
    for kind in kinds:
        print(f"■ {kind.label} ({kind.key})")
        try:
            raw = presale_api.fetch_all(kind.notice_op, max_pages=max_pages, on_page=_progress)
        except presale_api.PresaleQuotaExceeded as e:
            print(f"\n✗ {e}\n  받은 종류까지는 저장됨. 한도가 풀리면 다시 실행.")
            return 2

        rows = [presale_sync.notice_row(kind, d, region) for d in raw]
        rows = [r for r in rows if r["house_manage_no"] and r["pblanc_no"]]

        # 같은 응답 안에서 키가 겹치면(정정공고 등) 뒤의 것이 이긴다
        dedup = {(r["house_manage_no"], r["pblanc_no"]): r for r in rows}
        n = presale_sync.upsert_notices(list(dedup.values()))
        no_sgg = sum(1 for r in dedup.values() if r["sgg_cd"] is None)
        print(f"  → 공고 {n:,}건 저장 (시군구 미매칭 {no_sgg:,})")
        total_n += n

        if with_types:
            try:
                traw = presale_api.fetch_all(kind.type_op, max_pages=None if max_pages is None else 3,
                                             on_page=_progress)
            except presale_api.PresaleQuotaExceeded as e:
                print(f"\n✗ {e}\n  공고는 저장됨. 주택형은 한도가 풀리면 다시 실행.")
                return 2
            # FK: 공고가 저장된 것만. --recent 에선 주택형이 공고보다 넓게 올 수 있다.
            keys = presale_sync.existing_notice_keys()
            trows = [presale_sync.type_row(kind, d) for d in traw]
            trows = [t for t in trows if (t["house_manage_no"], t["pblanc_no"]) in keys]
            tdedup = {(t["house_manage_no"], t["pblanc_no"], t["model_no"]): t for t in trows}
            t = presale_sync.upsert_types(list(tdedup.values()))
            print(f"  → 주택형 {t:,}건 저장")
            total_t += t
        print()

    print(f"■ 완료 — 공고 {total_n:,} / 주택형 {total_t:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
