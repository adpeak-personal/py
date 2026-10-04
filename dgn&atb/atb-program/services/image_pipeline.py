"""신규 단지 이미지 검수 → DB 저장 파이프라인.

image_status=0(미검수) 단지만 골라 네이버 이미지 검수기로 1장 확보한다.
  - 통과 1장 → apartments.thumbnail_url 저장, image_status=1
  - 못 찾음   → image_status=2 (다시 검수하지 않음)
  - 검수 오류 → status 그대로(0) 두어 다음 실행에서 재시도

기존 단지(=이미 status 1/2)는 get_pending_image_apartments 에서 안 잡히므로
건너뛴다. 따라서 거래가 아무리 많아도 검수는 '신규 건물 수'만큼만 돈다.
같은 건물의 새 거래는 apt_id 로 기존 thumbnail_url 을 자동 공유한다.

※ 이미지는 일단 원본 URL 그대로 저장. GCS 업로드는 이후 추가 예정.
"""
from __future__ import annotations

from dataclasses import dataclass

from services import db, image_service


@dataclass
class ImageSyncStats:
    total: int    # 검수 대상(미검수 단지) 수
    found: int    # 이미지 확보
    none: int     # 못 찾음
    failed: int   # 검수 중 오류 (다음 실행에서 재시도)


def sync_pending_images(limit: int | None = None, on_progress=None) -> ImageSyncStats:
    """미검수 단지 이미지 일괄 검수·저장.

    limit: 한 번에 처리할 최대 단지 수 (None=전체).
    on_progress(idx, total, apt_nm, status) 콜백(선택).
      status: 'found' | 'none' | 'failed'
    """
    rows = db.get_pending_image_apartments(limit)
    total = len(rows)
    found = none = failed = 0

    for idx, row in enumerate(rows):
        apt_id = row["id"]
        apt_nm = row["apt_nm"]
        umd_nm = row.get("umd_nm") or ""
        query = f"{apt_nm} {umd_nm} 아파트".strip()

        try:
            result = image_service.find_one_apartment_image(query)
        except image_service.ImageServiceError:
            # 네트워크/검수기 일시 오류 — status 0 유지하여 다음 실행에서 재시도
            failed += 1
            status = "failed"
        else:
            if result.image is not None:
                # TODO(GCS): result.image.image_bytes 를 GCS 업로드 후
                #            반환 URL 로 교체. 지금은 원본 URL 그대로 저장.
                db.set_apartment_image(apt_id, result.image.imageUrl, source="naver")
                found += 1
                status = "found"
            else:
                db.mark_apartment_no_image(apt_id)
                none += 1
                status = "none"

        if on_progress:
            on_progress(idx + 1, total, apt_nm, status)

    return ImageSyncStats(total=total, found=found, none=none, failed=failed)
