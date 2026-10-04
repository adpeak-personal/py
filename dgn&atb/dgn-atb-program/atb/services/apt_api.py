"""국토교통부 아파트 매매 실거래가 조회 (atb-back/lib/aptApi.ts 포팅)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import requests

import config


@dataclass
class AptTradeItem:
    """실거래 1건. API XML <item>의 자식 태그를 그대로 담는다."""

    aptNm: str = ""
    aptDong: str = ""
    umdNm: str = ""
    jibun: str = ""
    excluUseAr: str = ""
    floor: str = ""
    dealAmount: str = ""
    dealYear: str = ""
    dealMonth: str = ""
    dealDay: str = ""
    buildYear: str = ""
    dealingGbn: str = ""
    buyerGbn: str = ""
    slerGbn: str = ""
    sggCd: str = ""
    estateAgentSggNm: str = ""
    cdealType: str = ""
    cdealDay: str = ""
    landLeaseholdGbn: str = ""
    rgstDate: str = ""
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_element(cls, item_el: ET.Element) -> "AptTradeItem":
        raw = {child.tag.strip(): (child.text or "").strip() for child in item_el}
        known = {f for f in cls.__dataclass_fields__ if f != "raw"}
        kwargs = {k: v for k, v in raw.items() if k in known}
        return cls(raw=raw, **kwargs)


@dataclass
class AptTradeResult:
    items: list[AptTradeItem]
    totalCount: int
    pageNo: int
    numOfRows: int


class AptApiError(RuntimeError):
    pass


def fetch_apt_trades(
    lawd_cd: str,
    deal_ymd: str,
    page_no: int = 1,
    num_of_rows: int = 100,
    timeout: int = 15,
) -> AptTradeResult:
    """실거래가 조회. lawd_cd=지역코드5자리, deal_ymd=YYYYMM."""
    if not config.DATA_AUTH_KEY:
        raise AptApiError(f"DATA_AUTH_KEY 가 설정되지 않았습니다 ({config.ENV_PATH} 확인).")

    # serviceKey 는 이미 인코딩된 값이라 직접 URL 에 붙인다 (TS 구현과 동일)
    other = {
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "pageNo": str(page_no),
        "numOfRows": str(num_of_rows),
    }
    qs = "&".join(f"{k}={v}" for k, v in other.items())
    url = f"{config.APT_TRADE_BASE_URL}?serviceKey={config.DATA_AUTH_KEY}&{qs}"

    res = requests.get(url, timeout=timeout)
    if not res.ok:
        raise AptApiError(f"API 응답 오류: {res.status_code} {res.reason}\n{res.text[:300]}")

    try:
        root = ET.fromstring(res.text)
    except ET.ParseError as e:
        raise AptApiError(f"XML 파싱 실패: {e}\n{res.text[:300]}")

    # OpenAPI 오류 응답 (OpenAPI_ServiceResponse/cmmMsgHeader/errMsg)
    err = root.find(".//cmmMsgHeader/errMsg")
    if err is not None and (err.text or "").strip():
        raise AptApiError(f"API 오류: {err.text.strip()}")

    result_code = root.findtext(".//header/resultCode")
    if result_code not in (None, "00", "000", "0"):
        msg = root.findtext(".//header/resultMsg") or "unknown error"
        raise AptApiError(f"API 오류: [{result_code}] {msg}")

    items = [AptTradeItem.from_element(el) for el in root.findall(".//body/items/item")]

    def to_int(tag: str, default: int = 0) -> int:
        txt = root.findtext(f".//body/{tag}")
        try:
            return int(txt) if txt is not None else default
        except ValueError:
            return default

    return AptTradeResult(
        items=items,
        totalCount=to_int("totalCount"),
        pageNo=to_int("pageNo", page_no),
        numOfRows=to_int("numOfRows", num_of_rows),
    )
