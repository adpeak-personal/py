"""아파트 이미지 검색 — 네이버 이미지 검색 API (단일 소스).

네이버 이미지 검색 결과를 1장씩 검수(services/image_inspector)하여
'글씨/워터마크 없음 + 실내 아님 + 단지(건물) 외관' 조건을 통과하는 첫 1장에서 멈춘다.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import requests

import config

_UA = "Mozilla/5.0 (compatible; ATBBot/1.0)"

# 워터마크가 자주 박히는 출처(호스트 부분일치). 발견하는 대로 여기에 추가하면 됨.
WATERMARK_HOSTS = [
    "landthumb",        # 네이버 부동산 매물 썸네일 (NAVER 워터마크)
    "blogfiles.naver",  # 네이버 블로그 첨부
    # "postfiles.naver",
    "postfiles.pstatic",
    "cafefiles",        # 네이버 카페
    # "dthumb-phinf",     # 네이버 블로그 썸네일
    "blogthumb",
    "land.naver",       # 네이버 부동산
    "image.hogangnono", # 호갱노노 (자체 로고/워터마크)
]


def image_host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _is_watermark_source(url: str) -> bool:
    host = image_host(url)
    low = url.lower()
    return any(w in host or w in low for w in WATERMARK_HOSTS)


@dataclass
class NaverImage:
    imageUrl: str           # 원본 이미지 URL
    thumbnailUrl: str       # 표시용 썸네일 (없으면 imageUrl)
    pageUrl: str            # 클릭 시 열 URL
    width: int | None
    height: int | None
    image_bytes: bytes | None = None
    category: str | None = None


class ImageServiceError(RuntimeError):
    pass


# ─── 네이버 이미지 검색 ────────────────────────────────────────────────────────
def search_naver_images(query: str, display: int = 30,
                        exclude_watermark_sources: bool = True) -> list[NaverImage]:
    """네이버 이미지 검색. 최대 display 장 반환 (API 상한 100).

    exclude_watermark_sources=True 면 WATERMARK_HOSTS 출처 이미지는 제외한다.
    """
    if not (config.NAVER_CLIENT_ID and config.NAVER_CLIENT_SECRET):
        raise ImageServiceError("NAVER_CLIENT_ID/SECRET 가 설정되지 않았습니다.")

    params = {
        "query": query,
        "display": str(max(1, min(display, 100))),
        "sort": "sim",
        "filter": "all",
    }
    headers = {
        "X-Naver-Client-Id": config.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
    }
    try:
        res = requests.get(
            config.NAVER_IMAGE_SEARCH_URL, params=params, headers=headers, timeout=8
        )
    except requests.RequestException as e:
        raise ImageServiceError(f"네이버 이미지 검색 요청 실패: {e}") from e
    if not res.ok:
        raise ImageServiceError(
            f"네이버 이미지 검색 오류: {res.status_code} {res.text[:200]}")
    try:
        items = res.json().get("items", [])
    except ValueError as e:
        raise ImageServiceError(f"응답 파싱 실패: {e}") from e

    def to_int(v):
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    out: list[NaverImage] = []
    for it in items:
        link = it.get("link", "")
        if not link:
            continue
        if exclude_watermark_sources and _is_watermark_source(link):
            continue
        out.append(NaverImage(
            imageUrl=link,
            thumbnailUrl=it.get("thumbnail", "") or link,
            pageUrl=link,
            width=to_int(it.get("sizewidth")),
            height=to_int(it.get("sizeheight")),
        ))
    return out


# ─── 다운로드 ─────────────────────────────────────────────────────────────────
def download_image(url: str, timeout: int = 10) -> bytes:
    """이미지 바이트 다운로드."""
    res = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout)
    res.raise_for_status()
    return res.content


# ─── 1장 찾기 ─────────────────────────────────────────────────────────────────
@dataclass
class SingleResult:
    image: NaverImage | None
    checked: int
    total: int
    reasons: dict


def find_one_apartment_image(
    query: str,
    candidates: int = 30,
    on_progress=None,
) -> SingleResult:
    """네이버 이미지를 1장씩 검수 → '글씨/워터마크 없음 + 실내 아님 + 단지 외관'
    조건을 통과하는 첫 1장에서 멈춰 반환.

    on_progress(idx, total, reason) 콜백(선택).
    """
    try:
        from services import image_inspector
    except Exception as e:  # noqa: BLE001
        raise ImageServiceError(f"검수기 로드 실패: {e}") from e

    images = search_naver_images(query, display=candidates)
    total = len(images)
    reasons: dict[str, int] = {}
    checked = 0

    for idx, img in enumerate(images):
        data = None
        for url in (img.imageUrl, img.thumbnailUrl):
            if not url:
                continue
            try:
                data = download_image(url)
                break
            except requests.RequestException:
                continue
        if data is None:
            reasons["download_fail"] = reasons.get("download_fail", 0) + 1
            continue

        checked += 1
        try:
            res = image_inspector.inspect(data)
        except image_inspector.InspectorUnavailable as e:
            raise ImageServiceError(str(e)) from e
        except Exception:  # noqa: BLE001
            reasons["decode_fail"] = reasons.get("decode_fail", 0) + 1
            continue

        if on_progress:
            on_progress(idx + 1, total, res["reason"])

        if res["passed"]:
            img.image_bytes = data
            img.category = res["detail"].get("top_category")
            return SingleResult(image=img, checked=checked, total=total, reasons=reasons)

        reasons[res["reason"]] = reasons.get(res["reason"], 0) + 1

    return SingleResult(image=None, checked=checked, total=total, reasons=reasons)


# 호환용 별칭
def search_apt_images_by_web(query: str, max_images: int = 30, **_kw) -> list[NaverImage]:
    return search_naver_images(query, display=max_images)
