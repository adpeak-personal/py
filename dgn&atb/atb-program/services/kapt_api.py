"""공동주택(K-apt) 단지정보 API 클라이언트.

국토교통부 3개 서비스(기관코드 1613000)를 감싼다. serviceKey 는 실거래가와 동일 키.
  - AptListService4      : 단지 목록 (kaptCode 획득)
  - AptBasisInfoServiceV5: 단지 기본정보 (세대수/주소/준공일 등)
  - AptBasisInfoServiceV5: 단지 상세정보 (주차/승강기/CCTV 등)

응답은 JSON. 실거래가(apt_api.py)가 XML 인 것과 다르다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests

import config

_LIST_BASE = "https://apis.data.go.kr/1613000/AptListService4"
_INFO_BASE = "https://apis.data.go.kr/1613000/AptBasisInfoServiceV5"


class KaptApiError(RuntimeError):
    pass


class KaptQuotaExceeded(KaptApiError):
    """일일 호출 한도 초과. 재시도해도 소용없으므로 호출측은 즉시 중단해야 한다."""


class KaptTransient(KaptApiError):
    """잠시 후 다시 부르면 되는 오류. _get 안에서만 쓰고 밖으로는 나가지 않는다."""


# 공공데이터포털이 한도 초과 시 돌려주는 코드/문구
_QUOTA_MARKERS = (
    "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS",
    "SERVICE_ACCESS_DENIED",
    "요청횟수",
)

# 일시 오류 재시도 간격(초).
# 포털이 HTTP_ERROR 를 간헐적으로 뱉는 구간이 있다(측정: 4회 중 3회 실패).
# 3회로는 한 시군구가 통째로 건너뛰어져서, 넉넉히 다섯 번까지 기다려 본다.
_RETRY_BACKOFF = (3, 10, 30, 60, 120)

# HTTP 200 으로 오는 포털 쪽 일시 장애 표식
_TRANSIENT_MARKERS = ("HTTP_ERROR", "SERVICE_TIMEOUT", "INTERNAL_SERVER_ERROR")


def _get(url: str, params: dict, timeout: int = 15) -> dict:
    """요청 1회 + 일시 오류 재시도.

    일시 오류는 세 가지 모습으로 온다:
      - requests 예외 (ReadTimeout, TLS 끊김)
      - HTTP 5xx
      - HTTP 200 인데 본문이 'HTTP_ERROR' (포털 쪽 야간 장애에서 이 형태로 왔다)
    셋 다 쉬었다 다시 부르고, 끝내 안 되면 KaptApiError 로 올려 호출측이 그 단지·
    시군구만 실패로 세고 넘어가게 한다.
    """
    last = ""
    for wait in (*_RETRY_BACKOFF, None):
        try:
            return _get_once(url, params, timeout)
        except KaptTransient as e:
            last = str(e)
            if wait is None:
                raise KaptApiError(f"일시 오류가 계속됨(재시도 {len(_RETRY_BACKOFF)}회): {last}") from e
            time.sleep(wait)
    raise KaptApiError(f"일시 오류: {last}")   # 도달하지 않는다


def _get_once(url: str, params: dict, timeout: int = 15) -> dict:
    """serviceKey 는 이미 인코딩된 값이라 직접 URL 에 붙인다 (apt_api.py 와 동일)."""
    if not config.DATA_AUTH_KEY:
        raise KaptApiError(f"DATA_AUTH_KEY 가 설정되지 않았습니다 ({config.ENV_PATH} 확인).")

    qs = "&".join(f"{k}={v}" for k, v in params.items())
    full = f"{url}?serviceKey={config.DATA_AUTH_KEY}&{qs}"

    try:
        res = requests.get(full, timeout=timeout)
    except requests.RequestException as e:
        raise KaptTransient(f"{type(e).__name__}: {str(e)[:120]}") from e
    if res.status_code >= 500:
        raise KaptTransient(f"HTTP {res.status_code}")

    # 한도 초과는 HTTP 429 + 본문의 LIMITED_… 로 온다. res.ok 검사보다 먼저 봐야 한다 —
    # 순서가 반대면 일반 오류로 분류돼 단지마다 '실패' 로 찍히고 수집이 멈추지 않는다
    # (목록 API 는 한도가 따로라 계속 응답해서, 전 시군구를 헛돌며 전부 실패 처리됐다).
    if res.status_code == 429 or any(m in res.text[:500] for m in _QUOTA_MARKERS):
        raise KaptQuotaExceeded(f"일일 호출 한도 초과: HTTP {res.status_code} {res.text[:160]}")
    if not res.ok:
        raise KaptApiError(f"API 응답 오류: {res.status_code} {res.reason}\n{res.text[:200]}")

    try:
        data = res.json()
    except ValueError as e:
        raise KaptApiError(f"JSON 파싱 실패: {e}\n{res.text[:200]}") from e

    # OpenAPI 레벨 오류 (response 래퍼 없이 OpenAPI_ServiceResponse 로 옴)
    cmm = (data.get("OpenAPI_ServiceResponse") or {}).get("cmmMsgHeader")
    if cmm:
        msg = f"{cmm.get('errMsg')} / {cmm.get('returnAuthMsg')}"
        if any(m in str(msg) for m in _QUOTA_MARKERS):
            raise KaptQuotaExceeded(f"일일 호출 한도 초과: {msg}")
        if any(m in str(msg) for m in _TRANSIENT_MARKERS):
            raise KaptTransient(f"API 일시 오류: {msg}")
        raise KaptApiError(f"API 오류: {msg}")

    body = (data.get("response") or {}).get("body")
    header = (data.get("response") or {}).get("header") or {}
    code = header.get("resultCode")
    if code not in (None, "00", "000", "0"):
        msg = header.get("resultMsg")
        if any(m in str(msg) for m in _QUOTA_MARKERS):
            raise KaptQuotaExceeded(f"일일 호출 한도 초과: [{code}] {msg}")
        raise KaptApiError(f"API 오류: [{code}] {msg}")
    if body is None:
        raise KaptApiError(f"응답에 body 없음: {res.text[:200]}")
    return body


# ─── 단지 목록 ────────────────────────────────────────────────────────────────
@dataclass
class KaptListItem:
    kaptCode: str
    kaptName: str
    bjdCode: str = ""
    sido: str = ""      # as1
    sgg: str = ""       # as2
    umd: str = ""       # as3
    ri: str = ""        # as4

    @classmethod
    def from_json(cls, d: dict) -> "KaptListItem":
        return cls(
            kaptCode=d.get("kaptCode", ""),
            kaptName=d.get("kaptName", ""),
            bjdCode=d.get("bjdCode", "") or "",
            sido=d.get("as1", "") or "",
            sgg=d.get("as2", "") or "",
            umd=d.get("as3", "") or "",
            ri=d.get("as4", "") or "",
        )


def fetch_sigungu_apt_list(sigungu_code: str, page_size: int = 100) -> list[KaptListItem]:
    """시군구코드(5자리)로 등록 단지 전량 조회 (페이지네이션 자동)."""
    out: list[KaptListItem] = []
    page = 1
    while True:
        body = _get(f"{_LIST_BASE}/getSigunguAptList4",
                    {"sigunguCode": sigungu_code, "pageNo": page, "numOfRows": page_size})
        items = body.get("items") or []
        if isinstance(items, dict):          # 단건일 때 dict 로 오는 경우 방어
            items = [items]
        out.extend(KaptListItem.from_json(x) for x in items)
        total = int(body.get("totalCount") or 0)
        if len(out) >= total or not items:
            break
        page += 1
    return out


# ─── 기본/상세 정보 ───────────────────────────────────────────────────────────
def fetch_basis_info(kapt_code: str) -> dict:
    """단지 기본정보 (세대수/주소/준공일/시공사/면적분포 등). 원본 dict 반환."""
    body = _get(f"{_INFO_BASE}/getAphusBassInfoV5", {"kaptCode": kapt_code})
    return body.get("item") or {}


def fetch_detail_info(kapt_code: str) -> dict:
    """단지 상세정보 (주차/승강기/CCTV/구조/부대복리시설 등). 원본 dict 반환."""
    body = _get(f"{_INFO_BASE}/getAphusDtlInfoV5", {"kaptCode": kapt_code})
    return body.get("item") or {}
