"""K-apt 상세정보만 보충 (CLI).

교통(지하철 노선·역·도보시간), 학군(교육시설), 편의시설, 주차·CCTV·승강기는
K-apt 상세 API 가 준다. 초기 수집 때 호출을 아끼려고 --no-detail 로 받은 단지들은
이 값이 비어 있는데, sync_sigungu 로 다시 돌리면 기본정보까지 또 받아 호출이
2배 든다. 그래서 상세만 1회씩 채운다.

사용:
  python run_kapt_detail.py                 # 상세 없는 단지 전량
  python run_kapt_detail.py --sido 11       # 시도 앞 2자리로 한정 (11=서울)
  python run_kapt_detail.py --limit 500     # 500건만 (한도 확인용)
  python run_kapt_detail.py --delay 0.05    # 호출 간격(초). 기본 0.05
  python run_kapt_detail.py --remap        # API 호출 없이 raw 에서 컬럼만 다시 만든다
                                           # (매핑 로직을 고쳤을 때)

선행: .env 의 DATA_AUTH_KEY (실거래·K-apt 공용)
"""
from __future__ import annotations

import sys
import time

import config
from services import db, kapt_api, kapt_sync


def main(argv: list[str]) -> int:
    flags = {a.split("=")[0]: a for a in argv if a.startswith("--")}

    def opt(name: str, default: float) -> float:
        raw = flags.get(name)
        if not raw:
            return default
        # "--sido 11" 과 "--sido=11" 둘 다 받는다
        if "=" in raw:
            v = raw.split("=", 1)[1]
        else:
            i = argv.index(raw)
            v = argv[i + 1] if i + 1 < len(argv) else ""
        try:
            return float(v)
        except ValueError:
            return default

    limit = int(opt("--limit", 0)) or None
    sido = int(opt("--sido", 0)) or None
    delay = opt("--delay", 0.05)

    if not config.env("DATA_AUTH_KEY"):
        print(f"✗ DATA_AUTH_KEY 가 설정되지 않았습니다 ({config.ENV_PATH}).")
        return 1

    if "--remap" in flags:
        rows = db.get_kapt_with_detail(limit, sido_prefix=sido)
        print(f"■ raw 재매핑 {len(rows)}건 (API 호출 없음)")
        print()
        n = 0
        for r in rows:
            dtl = r["dtl"] or {}
            db.update_kapt_detail(r["kapt_code"], kapt_sync.detail_fields(dtl), dtl)
            n += 1
            if n % 500 == 0:
                print(f"  {n}/{len(rows)}")
        print()
        print(f"→ 재매핑 {n}건")
        return 0

    rows = db.get_kapt_missing_detail(limit, sido_prefix=sido)
    total = len(rows)
    if total == 0:
        print("■ 상세정보가 필요한 단지가 없습니다.")
        return 0

    print(f"■ 대상 {total}건 (호출 {total}회 예상)\n")

    ok = failed = 0
    for i, row in enumerate(rows, 1):
        code, name = row["kapt_code"], row["kapt_name"]
        try:
            dtl = kapt_api.fetch_detail_info(code)
            db.update_kapt_detail(code, kapt_sync.detail_fields(dtl), dtl)
            ok += 1
            sub = dtl.get("subwayStation") or "-"
            mark = f"{sub}"
        except kapt_api.KaptQuotaExceeded as e:
            print(f"\n✗ {e}")
            print(f"  {i - 1}/{total} 처리 후 중단. 받은 건 저장됨.")
            print("  한도가 초기화되면 같은 명령을 다시 실행하면 이어서 받는다.")
            break
        except kapt_api.KaptApiError as e:
            failed += 1
            mark = f"오류: {str(e)[:40]}"

        if i % 100 == 0 or i == total:
            print(f"  [{i}/{total}] {name[:20]:20} {mark}")

        if delay:
            time.sleep(delay)

    print(f"\n→ 성공 {ok} / 실패 {failed}")
    if failed:
        print("  실패 건은 상세가 비어 있어 다음 실행에서 자동 재시도된다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
