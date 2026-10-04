"""매칭 실행 워커.

kapt_complexes(마스터) 로 AptMatcher 를 만들고, apartments 중 미매칭(match_status=0)
단지를 이름+지번으로 매칭해 결과를 apartments 에 기록한다.

선행: services/kapt_sync.sync_sigungu() 로 kapt_complexes 가 채워져 있어야 한다.
자동확정(confirmed/matched)만 kapt_code 를 채우고, ambiguous/conflict 는 상태만
남겨 수동확인 대상으로 둔다.
"""
from __future__ import annotations

from collections import Counter

from services import db, apt_matcher as M


def run_matching(sgg_cd: int, on_progress=None) -> dict:
    """시군구 단위 매칭 실행. 상태별 건수 통계 반환."""
    master_rows = db.get_kapt_master(sgg_cd)
    master = [M.MasterRecord(kapt_code=r["kapt_code"], kapt_name=r["kapt_name"],
                             umd=r["umd_nm"] or "", jibun=r["jibun"] or "")
              for r in master_rows]
    matcher = M.AptMatcher(master)

    apts = db.get_unmatched_apartments(sgg_cd)
    total = len(apts)
    stats: Counter = Counter()
    for i, a in enumerate(apts):
        res = matcher.match(a["apt_nm"] or "", a["umd_nm"] or "", a["jibun"] or "")
        code = M.STATUS_CODE[res.status]
        # 자동확정만 kapt_code 채움. ambiguous/conflict/unmatched 는 kapt_code=NULL
        kapt = res.kapt_code if res.status in (M.CONFIRMED, M.MATCHED) else None
        db.update_apartment_match(a["id"], kapt, code, res.method)
        stats[res.status] += 1
        if on_progress:
            on_progress(i + 1, total, a["apt_nm"], res.status)

    return {
        "sgg_cd": sgg_cd, "master": len(master), "total": total,
        "confirmed": stats[M.CONFIRMED], "matched": stats[M.MATCHED],
        "ambiguous": stats[M.AMBIGUOUS], "conflict": stats[M.CONFLICT],
        "unmatched": stats[M.UNMATCHED],
    }
