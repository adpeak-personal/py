"""국토교통부 전월세 실거래가 조회 (아파트·오피스텔).

매매와 모양이 다르다:
  · dealAmount 가 없고 deposit(보증금) + monthlyRent(월세) 다. 월세가 0 이면 전세.
  · 취소일(cdealDay)·등기일(rgstDate) 이 없다 — 중복 제거 키를 따로 만들어야 한다.
  · contractTerm / contractType / preDeposit / preMonthlyRent / useRRRight 이 붙는다.
    2021년 6월 임대차 신고제 이후 건에만 채워지고, 그 전 건은 비어 있다.
  · 아파트 전월세만 aptSeq(단지 일련번호)와 도로명 필드를 더 준다.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from services import molit

# 유형 → 서비스명. 활용신청은 서비스마다 따로 해야 한다.
SERVICES = {
    "APT": "RTMSDataSvcAptRent",
    "OFFI": "RTMSDataSvcOffiRent",
}

RentApiError = molit.MolitApiError


@dataclass
class RentItem:
    """전월세 1건. 단지명은 유형별 태그가 달라 houseNm 하나로 모아 담는다."""

    houseNm: str = ""
    umdNm: str = ""
    jibun: str = ""
    excluUseAr: str = ""
    floor: str = ""
    deposit: str = ""
    monthlyRent: str = ""
    dealYear: str = ""
    dealMonth: str = ""
    dealDay: str = ""
    buildYear: str = ""
    contractTerm: str = ""
    contractType: str = ""
    preDeposit: str = ""
    preMonthlyRent: str = ""
    useRRRight: str = ""
    sggCd: str = ""
    aptSeq: str = ""
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_element(cls, el: ET.Element) -> "RentItem":
        raw = {child.tag.strip(): (child.text or "").strip() for child in el}
        known = {f for f in cls.__dataclass_fields__ if f != "raw"}
        kwargs = {k: v for k, v in raw.items() if k in known}
        # 아파트는 aptNm, 오피스텔은 offiNm 으로 온다
        kwargs["houseNm"] = raw.get("aptNm") or raw.get("offiNm") or raw.get("mhouseNm") or ""
        return cls(raw=raw, **kwargs)


@dataclass
class RentResult:
    items: list[RentItem]
    totalCount: int
    pageNo: int
    numOfRows: int


def fetch_rents(
    property_type: str,
    lawd_cd: str,
    deal_ymd: str,
    page_no: int = 1,
    num_of_rows: int = 1000,
    timeout: int = 20,
) -> RentResult:
    service = SERVICES.get(property_type)
    if not service:
        raise RentApiError(f"전월세를 지원하지 않는 유형: {property_type} (가능: {', '.join(SERVICES)})")

    els, total, page, rows = molit.fetch_items(
        molit.service_url(service), lawd_cd, deal_ymd, page_no, num_of_rows, timeout
    )
    return RentResult([RentItem.from_element(e) for e in els], total, page, rows)
