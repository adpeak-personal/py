"""국토교통부 매매 실거래가 조회 (아파트·오피스텔·연립다세대).

유형마다 서비스가 다르지만 필드는 거의 같다 — 단지명 태그만 aptNm / offiNm /
mhouseNm 으로 갈린다. from_element 가 그걸 aptNm 하나로 모아 담으므로,
저장·집계 쪽은 유형을 몰라도 된다.

요청·오류·XML 파싱은 services/molit.py 에 모아 두었다 (전월세와 공통).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from services import molit

# 유형 → 서비스명. 활용신청은 서비스마다 따로 해야 한다.
SERVICES = {
    "APT": "RTMSDataSvcAptTrade",
    "OFFI": "RTMSDataSvcOffiTrade",
    # 연립다세대는 houseType·landAr 가 더 오고 '단지' 개념이 약해 묶음 규칙을
    # 따로 정해야 한다. 서비스만 적어 두고 아직 수집하지 않는다.
    "RH": "RTMSDataSvcRHTrade",
}


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
        # 아파트는 aptNm, 오피스텔은 offiNm, 연립다세대는 mhouseNm 으로 온다
        kwargs["aptNm"] = raw.get("aptNm") or raw.get("offiNm") or raw.get("mhouseNm") or ""
        return cls(raw=raw, **kwargs)


@dataclass
class AptTradeResult:
    items: list[AptTradeItem]
    totalCount: int
    pageNo: int
    numOfRows: int


AptApiError = molit.MolitApiError


def fetch_trades(
    property_type: str,
    lawd_cd: str,
    deal_ymd: str,
    page_no: int = 1,
    num_of_rows: int = 100,
    timeout: int = 15,
) -> AptTradeResult:
    """매매 실거래가 조회. lawd_cd=지역코드5자리, deal_ymd=YYYYMM."""
    service = SERVICES.get(property_type)
    if not service:
        raise AptApiError(f"모르는 유형: {property_type} (가능: {", ".join(SERVICES)})")

    els, total, page, rows = molit.fetch_items(
        molit.service_url(service), lawd_cd, deal_ymd, page_no, num_of_rows, timeout
    )
    return AptTradeResult(
        items=[AptTradeItem.from_element(el) for el in els],
        totalCount=total,
        pageNo=page,
        numOfRows=rows,
    )


def fetch_apt_trades(lawd_cd: str, deal_ymd: str, page_no: int = 1,
                     num_of_rows: int = 100, timeout: int = 15) -> AptTradeResult:
    """아파트 전용 호출 (기존 코드 호환)."""
    return fetch_trades("APT", lawd_cd, deal_ymd, page_no, num_of_rows, timeout)
