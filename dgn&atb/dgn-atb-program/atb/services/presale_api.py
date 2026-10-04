"""청약홈 분양정보 API 클라이언트 (한국부동산원, data.go.kr 15098547).

odcloud 게이트웨이(api.odcloud.kr)를 쓴다. serviceKey 는 실거래·K-apt 와 같은 키.
data.go.kr 의 일일 한도는 API 별로 따로라 K-apt 수집과 동시에 돌려도 서로 깎지 않는다.

공고 종류마다 '공고 상세' 와 '주택형별 상세' 엔드포인트가 한 쌍씩 있다.
응답은 최신 공고가 앞에 오는 순서라, 최근 것만 필요할 때는 앞 페이지만 받으면 된다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import requests

import config

_BASE = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/"


@dataclass(frozen=True)
class Kind:
    key: str         # 우리 쪽 식별자
    label: str
    notice_op: str
    type_op: str


# 청약홈이 공고를 나누는 방식 그대로. 무순위(줍줍)는 별도 엔드포인트다.
KINDS: tuple[Kind, ...] = (
    Kind("apt",       "APT",                 "getAPTLttotPblancDetail",        "getAPTLttotPblancMdl"),
    Kind("remndr",    "무순위·잔여세대",      "getRemndrLttotPblancDetail",     "getRemndrLttotPblancMdl"),
    Kind("officetel", "오피스텔·도시형",      "getUrbtyOfctlLttotPblancDetail", "getUrbtyOfctlLttotPblancMdl"),
    Kind("pvtrent",   "공공지원 민간임대",    "getPblPvtRentLttotPblancDetail", "getPblPvtRentLttotPblancMdl"),
    Kind("opt",       "임의공급",            "getOPTLttotPblancDetail",        "getOPTLttotPblancMdl"),
)


class PresaleApiError(RuntimeError):
    pass


class PresaleQuotaExceeded(PresaleApiError):
    """일일 한도 초과. 재시도해도 소용없으니 호출측은 즉시 멈춘다."""


_QUOTA_MARKERS = ("LIMITED_NUMBER_OF_SERVICE_REQUESTS", "요청횟수", "트래픽")
_RETRY_BACKOFF = (3, 10, 30)


def _get(op: str, page: int, per_page: int, timeout: int = 20) -> dict:
    if not config.DATA_AUTH_KEY:
        raise PresaleApiError(f"DATA_AUTH_KEY 가 설정되지 않았습니다 ({config.ENV_PATH} 확인).")

    params = {"page": page, "perPage": per_page, "serviceKey": config.DATA_AUTH_KEY}
    res = None
    for wait in (*_RETRY_BACKOFF, None):
        try:
            res = requests.get(_BASE + op, params=params, timeout=timeout)
            if res.status_code < 500:
                break
            err = f"HTTP {res.status_code}"
        except requests.RequestException as e:
            err = f"{type(e).__name__}: {str(e)[:120]}"
        if wait is None:
            raise PresaleApiError(f"{op}: 네트워크 오류(재시도 {len(_RETRY_BACKOFF)}회 후): {err}")
        time.sleep(wait)

    text = res.text[:300]
    if res.status_code == 429 or any(m in text for m in _QUOTA_MARKERS):
        raise PresaleQuotaExceeded(f"{op}: 일일 호출 한도 초과 — {text}")
    if not res.ok:
        raise PresaleApiError(f"{op}: HTTP {res.status_code} — {text}")
    try:
        return res.json()
    except ValueError as e:
        raise PresaleApiError(f"{op}: JSON 파싱 실패 — {text}") from e


def fetch_all(op: str, per_page: int = 500, max_pages: int | None = None,
              on_page=None) -> list[dict]:
    """엔드포인트 전량(또는 앞 max_pages 페이지)을 받는다."""
    out: list[dict] = []
    page = 1
    while True:
        body = _get(op, page, per_page)
        rows = body.get("data") or []
        out.extend(rows)
        total = int(body.get("totalCount") or 0)
        if on_page:
            on_page(op, len(out), total)
        if not rows or len(out) >= total:
            break
        if max_pages and page >= max_pages:
            break
        page += 1
    return out
