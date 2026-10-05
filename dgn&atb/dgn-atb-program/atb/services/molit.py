"""국토교통부 실거래가 API 공통부 (요청·오류·XML 파싱).

국토교통부는 주택 유형 × 매매/전월세 마다 서비스를 따로 낸다. 응답 껍데기와
오류 형식은 전부 같고 <item> 안의 필드만 다르다. 그 공통부를 여기 모은다.

활용신청은 서비스마다 따로 해야 한다 — 신청 안 된 서비스는 키가 멀쩡해도
resultCode 30 '등록되지 않은 서비스키' 를 돌려준다.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import requests

import config

_BASE = "https://apis.data.go.kr/1613000"


def service_url(service: str) -> str:
    """'RTMSDataSvcAptTrade' → 전체 URL. 오퍼레이션 이름은 서비스명에 get 을 붙인 꼴이다."""
    return f"{_BASE}/{service}/get{service}"


class MolitApiError(RuntimeError):
    pass


def fetch_items(
    url: str,
    lawd_cd: str,
    deal_ymd: str,
    page_no: int = 1,
    num_of_rows: int = 100,
    timeout: int = 15,
) -> tuple[list[ET.Element], int, int, int]:
    """(item 엘리먼트들, totalCount, pageNo, numOfRows).

    lawd_cd=지역코드 5자리, deal_ymd=YYYYMM.
    """
    if not config.DATA_AUTH_KEY:
        raise MolitApiError(f"DATA_AUTH_KEY 가 설정되지 않았습니다 ({config.ENV_PATH} 확인).")

    # serviceKey 는 이미 인코딩된 값이라 직접 URL 에 붙인다 (params 로 넘기면 재인코딩된다)
    qs = "&".join(
        f"{k}={v}"
        for k, v in {
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "pageNo": str(page_no),
            "numOfRows": str(num_of_rows),
        }.items()
    )
    res = requests.get(f"{url}?serviceKey={config.DATA_AUTH_KEY}&{qs}", timeout=timeout)
    if not res.ok:
        raise MolitApiError(f"API 응답 오류: {res.status_code} {res.reason}\n{res.text[:300]}")

    try:
        root = ET.fromstring(res.text)
    except ET.ParseError as e:
        raise MolitApiError(f"XML 파싱 실패: {e}\n{res.text[:300]}")

    # OpenAPI 게이트웨이 오류 (OpenAPI_ServiceResponse/cmmMsgHeader/errMsg)
    err = root.find(".//cmmMsgHeader/errMsg")
    if err is not None and (err.text or "").strip():
        reason = (root.findtext(".//returnAuthMsg") or "").strip()
        raise MolitApiError(f"API 오류: {err.text.strip()} {reason}".strip())

    code = root.findtext(".//header/resultCode")
    if code not in (None, "00", "000", "0"):
        msg = root.findtext(".//header/resultMsg") or "unknown error"
        raise MolitApiError(f"API 오류: [{code}] {msg}")

    def to_int(tag: str, default: int) -> int:
        txt = root.findtext(f".//body/{tag}")
        try:
            return int(txt) if txt is not None else default
        except ValueError:
            return default

    return (
        root.findall(".//body/items/item"),
        to_int("totalCount", 0),
        to_int("pageNo", page_no),
        to_int("numOfRows", num_of_rows),
    )
