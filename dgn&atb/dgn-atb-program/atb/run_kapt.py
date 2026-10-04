"""K-apt 마스터 동기화 + 매칭 실행 (CLI).

실거래 수집(GUI)과 별개로 도는 워커. 순서:
  1) kapt_sync.sync_sigungu  → kapt_complexes 채움 (K-apt 목록+기본+상세)
  2) apt_match_run.run_matching → apartments 매칭 결과 기록

사용:
  python run_kapt.py 11650                # 서초구: 동기화 후 매칭
  python run_kapt.py 11650 11680 11710    # 여러 시군구
  python run_kapt.py 11650 --match-only   # 동기화 건너뛰고 매칭만
  python run_kapt.py 11650 --sync-only    # 매칭 없이 동기화만
  python run_kapt.py 11650 --resync       # 최신 캐시 무시하고 K-apt 전량 재동기화
  python run_kapt.py 11650 --rematch      # 기존 매칭 초기화 후 전량 재매칭
  python run_kapt.py 11650 --no-detail    # 상세정보 호출 생략 (API 호출 절반)
  python run_kapt.py --seoul --sync-only  # 서울 25개 구 전체
  python run_kapt.py --all                # 전국 활성 시군구 (한도 걸리면 다음날 재실행)

기본: 최근 30일 내 동기화된 단지는 건너뜀(자주 눌러도 신규만 받음).

선행: MySQL 기동 + migrations/000_atb_db.sql 적용.
"""
from __future__ import annotations

import sys

from services import db, kapt_api, kapt_sync, apt_match_run


def _sync(sgg: str, max_age_days: int = 30, with_detail: bool = True):
    def prog(done, total, name):
        end = "\n" if done == total else "\r"
        print(f"  [동기화] {done}/{total}  {name[:24]:24}", end=end, flush=True)
    print(f"■ {sgg} K-apt 마스터 동기화...")
    st = kapt_sync.sync_sigungu(sgg, with_detail=with_detail,
                                max_age_days=max_age_days, on_progress=prog)
    print(f"  → 단지 {st['total']} / 신규·갱신 {st['saved']} / 건너뜀(최신) "
          f"{st.get('skipped', 0)} / 실패 {st['errors']}")


def _match(sgg: str):
    print(f"■ {sgg} 매칭...")
    st = apt_match_run.run_matching(int(sgg))
    auto = st["confirmed"] + st["matched"]
    print(f"  → 대상 {st['total']} (마스터 {st['master']})")
    print(f"     자동확정 {auto}  (confirmed {st['confirmed']} / matched {st['matched']})")
    print(f"     수동확인 {st['ambiguous'] + st['conflict']}  "
          f"(ambiguous {st['ambiguous']} / conflict {st['conflict']})")
    print(f"     미매칭 {st['unmatched']}")


def main(argv: list[str]):
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}

    if "--seoul" in flags:
        # 서울 25개 구 (11110~11740). 거래량이 가장 많아 마스터 우선순위가 높다.
        args = [str(r["sgg_cd"]) for r in db.load_sgg_codes(active_only=True)
                if 11110 <= int(r["sgg_cd"]) <= 11740]
    elif "--all" in flags:
        # 전국 활성 시군구. 서울을 먼저 두어 한도가 끊겨도 거래 많은 곳부터 채운다.
        codes = [str(r["sgg_cd"]) for r in db.load_sgg_codes(active_only=True)]
        args = sorted(codes, key=lambda c: (not c.startswith("11"), c))

    if not args:
        print(__doc__)
        return 1

    max_age = 0 if "--resync" in flags else 30   # --resync: 전량 강제 재동기화
    with_detail = "--no-detail" not in flags

    if "--rematch" in flags:
        for sgg in args:
            n = db.reset_matches(int(sgg))
            print(f"■ {sgg} 매칭 초기화: {n}건")

    failed_sgg: list[str] = []
    for sgg in args:
        if "--match-only" not in flags:
            try:
                _sync(sgg, max_age_days=max_age, with_detail=with_detail)
            except kapt_api.KaptQuotaExceeded as e:
                # 여기까지 받은 단지는 이미 저장됐다. 남은 시군구는 내일 이어서.
                print()
                print(f"✗ {e}")
                print(f"  {sgg} 에서 중단. 받은 데이터는 저장됨. "
                      f"한도가 초기화되면 같은 명령을 다시 실행하면 이어서 받는다.")
                return 2
            except kapt_api.KaptApiError as e:
                # 목록 조회가 재시도 후에도 실패 — 이 시군구만 건너뛴다.
                # 30일 캐시 덕에 다음 실행에서 이 시군구부터 다시 받는다.
                print()
                print(f"✗ {sgg} 동기화 실패, 건너뜀: {str(e)[:150]}")
                failed_sgg.append(sgg)
                continue
        if "--sync-only" not in flags:
            _match(sgg)
        print()

    if failed_sgg:
        print(f"■ 동기화 실패 시군구 {len(failed_sgg)}개: {' '.join(failed_sgg)}")
        print("  같은 명령을 다시 실행하면 이 시군구들만 다시 받는다.")
        return 3
    print("■ 전체 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
