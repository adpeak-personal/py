"""단지 주소 → 좌표 변환 배치 (CLI).

apartments.lat/lng 를 채운다. 지도 핀·반경검색의 전제다.

사용:
  python run_geocode.py                 # 미처리 전량
  python run_geocode.py --limit 500     # 500건만 (한도 확인용)
  python run_geocode.py --no-retry      # 이전 오류 건은 건너뛰기
  python run_geocode.py --delay 0.2     # 호출 간격(초). 기본 0.1

상태 코드: 0 미처리 / 1 성공 / 2 주소로 못찾음 / 3 오류(다음 실행에서 재시도)

선행: .env 의 JUSO_SEARCH_KEY, JUSO_COORD_KEY
  주소정보누리집(business.juso.go.kr)에서 '도로명주소 검색 API' 와
  '좌표제공 API' 를 각각 신청한다. 자동승인이고 무료다.

※ 한 건당 API 호출이 2회다 (주소검색 → 좌표조회).
"""
from __future__ import annotations

import sys
import time

import config
from services import db, geocode


def main(argv: list[str]) -> int:
    flags = {a.split("=")[0]: a for a in argv if a.startswith("--")}

    def opt(name: str, default: float) -> float:
        raw = flags.get(name)
        if not raw:
            return default
        # "--limit 5" 와 "--limit=5" 둘 다 받는다.
        # 예전엔 '=' 형식만 받아서 "--limit 5" 가 조용히 무시되고 전량이 돌았다.
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
    delay = opt("--delay", 0.1)
    retry_errors = "--no-retry" not in flags

    # 키가 없으면 전 건이 '오류'로 찍히고 끝난다. 시작 전에 막는다.
    # 두 API 에 같은 키가 나올 수 있어 하나만 있어도 진행한다.
    if not (config.env("JUSO_SEARCH_KEY") or config.env("JUSO_COORD_KEY")):
        print(f"✗ JUSO_SEARCH_KEY / JUSO_COORD_KEY 가 없습니다 ({config.ENV_PATH}).")
        print("  business.juso.go.kr 에서 '도로명주소 검색 API' 와 '좌표제공 API' 를")
        print("  신청하면 승인키가 나옵니다 (자동승인, 무료).")
        print("  같은 키가 나왔다면 둘 중 하나에만 넣어도 됩니다.")
        return 1

    rows = db.get_pending_geocode(limit, retry_errors=retry_errors)
    total = len(rows)
    if total == 0:
        print("■ 좌표가 필요한 단지가 없습니다.")
        return 0

    print(f"■ 대상 {total}건 (호출 {total * 2}회 예상)\n")

    gc = geocode.default_geocoder()
    ok = notfound = failed = 0

    for i, row in enumerate(rows, 1):
        addr = (row["address"] or "").strip()
        label = f"{row['apt_nm'][:18]:18}"

        if not addr:
            db.mark_geocode_failed(row["id"], 2)
            notfound += 1
            continue

        try:
            c = gc.geocode(addr)
            db.set_apartment_coord(row["id"], c.lat, c.lng)
            ok += 1
            mark = f"{c.lat:.5f}, {c.lng:.5f}"
        except geocode.GeocodeQuotaExceeded as e:
            print(f"\n✗ {e}")
            print(f"  {i - 1}/{total} 처리 후 중단. 받은 좌표는 저장됨.")
            print("  한도가 초기화되면 같은 명령을 다시 실행하면 이어서 받는다.")
            break
        except geocode.GeocodeNotFound:
            db.mark_geocode_failed(row["id"], 2)
            notfound += 1
            mark = "주소 못찾음"
        except geocode.GeocodeError as e:
            db.mark_geocode_failed(row["id"], 3)
            failed += 1
            mark = f"오류: {str(e)[:40]}"

        if i % 25 == 0 or i == total:
            print(f"  [{i}/{total}] {label} {mark}")

        if delay:
            time.sleep(delay)

    print(f"\n→ 성공 {ok} / 주소 못찾음 {notfound} / 오류 {failed}")
    if failed:
        print("  오류 건은 다음 실행에서 자동 재시도된다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
