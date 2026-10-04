"""주소 → 좌표 변환 (지오코딩).

■ 제공자를 왜 가려 썼나
  상용 지오코딩 API 는 대부분 결과를 DB 에 영구 저장하는 것을 약관으로 막는다.
  우리는 apartments.lat/lng 에 저장해 두고 지도·반경검색에 써야 하므로
  '저장 가능' 이 1순위 조건이다. 확인한 바(2026-09 기준):

    · VWorld / 국토부 지오코더 : "별도의 저장장치나 데이터베이스에 저장할 수
      없습니다" — 실시간 조회만. 사용 불가
    · 카카오 로컬 API          : 응답 결과 별도 저장 불가. 사용 불가
    · 행안부 주소정보누리집    : 공공데이터, 이용허락범위 제한 없음. 사용
      (juso.go.kr 승인키, 자동승인)

  약관은 바뀐다. 제공자를 갈아끼울 수 있게 Geocoder 프로토콜로 분리해 둔다.

■ 행안부 방식이 2단계인 이유
  좌표제공 API 는 자유 문자열이 아니라 도로명코드·건물번호를 받는다.
  그래서 주소검색 API 로 먼저 주소를 정규화해 코드를 얻고, 그 코드로 좌표를
  받는다. 한 건당 호출 2회다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import time

import requests

import config

_SEARCH_URL = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
_COORD_URL = "https://business.juso.go.kr/addrlink/addrCoordApi.do"


class GeocodeError(RuntimeError):
    """호출 실패 — 재시도 가치가 있다."""


class GeocodeNotFound(RuntimeError):
    """주소로 좌표를 찾지 못함 — 같은 주소로 다시 물어도 결과가 같다."""


class GeocodeQuotaExceeded(GeocodeError):
    """일일 한도 초과 — 즉시 중단해야 한다."""


@dataclass
class Coord:
    lat: float          # 위도 (WGS84)
    lng: float          # 경도 (WGS84)
    matched_address: str  # 실제로 매칭된 도로명주소 (검수용)


class GeocodeRateLimited(GeocodeError):
    """E0007 — 짧은 시간에 요청이 몰림. 잠깐 쉬면 풀린다(주소 문제가 아니다)."""


# E0007 을 받으면 이만큼 쉬고 다시 묻는다. 셋 다 실패하면 GeocodeError 로 남겨
# 다음 실행에서 재시도되게 한다.
_RATE_LIMIT_BACKOFF = (2, 5, 10)


class Geocoder(Protocol):
    def geocode(self, address: str) -> Coord: ...


# ─── 행안부 주소정보누리집 ─────────────────────────────────────────────────────
class JusoGeocoder:
    """행정안전부 도로명주소 검색 + 좌표제공 API.

    두 API 의 승인키가 서로 다르다(신청 화면이 별도). .env 에서 각각 받는다.
    """

    def __init__(self, search_key: str = "", coord_key: str = "", timeout: int = 10):
        s = search_key or config.env("JUSO_SEARCH_KEY")
        c = coord_key or config.env("JUSO_COORD_KEY")
        # '1 시스템 1 승인키' 안내가 있어 두 API 에 같은 키가 나올 수 있다.
        # 하나만 넣어도 동작하게 서로 메운다.
        self.search_key = s or c
        self.coord_key = c or s
        self.timeout = timeout

    def _check(self, common: dict, where: str) -> None:
        code = str(common.get("errorCode", ""))
        msg = common.get("errorMessage", "")
        if code == "0":
            return
        # E0005: 검색결과 없음 / E0006: 주소를 상세히 입력
        if code in ("E0005", "E0006"):
            raise GeocodeNotFound(f"{where}: [{code}] {msg}")
        if code == "E0007":  # 짧은 시간 다량 요청
            raise GeocodeRateLimited(f"{where}: [{code}] {msg}")
        if code in ("E0010", "E0012"):  # 사용량 초과 / 승인키 만료
            raise GeocodeQuotaExceeded(f"{where}: [{code}] {msg}")
        raise GeocodeError(f"{where}: [{code}] {msg}")

    def _search(self, address: str) -> dict:
        """주소 문자열 → 도로명코드·건물번호 등 정규화된 주소 레코드."""
        if not self.search_key:
            raise GeocodeError("JUSO_SEARCH_KEY 가 설정되지 않았습니다 (.env 확인).")

        res = requests.get(
            _SEARCH_URL,
            params={
                "confmKey": self.search_key,
                "currentPage": 1,
                "countPerPage": 1,
                "keyword": address,
                "resultType": "json",
            },
            timeout=self.timeout,
        )
        if not res.ok:
            raise GeocodeError(f"주소검색 HTTP {res.status_code}")

        body = (res.json().get("results") or {})
        self._check(body.get("common") or {}, "주소검색")

        items = body.get("juso") or []
        if not items:
            raise GeocodeNotFound(f"주소검색 결과 없음: {address}")
        return items[0]

    def _coord(self, juso: dict) -> tuple[float, float]:
        """정규화된 주소 → (entX, entY). 좌표계는 EPSG:5179 (UTM-K)."""
        if not self.coord_key:
            raise GeocodeError("JUSO_COORD_KEY 가 설정되지 않았습니다 (.env 확인).")

        res = requests.get(
            _COORD_URL,
            params={
                "confmKey": self.coord_key,
                "admCd": juso.get("admCd"),
                "rnMgtSn": juso.get("rnMgtSn"),
                "udrtYn": juso.get("udrtYn"),
                "buldMnnm": juso.get("buldMnnm"),
                "buldSlno": juso.get("buldSlno"),
                "resultType": "json",
            },
            timeout=self.timeout,
        )
        if not res.ok:
            raise GeocodeError(f"좌표조회 HTTP {res.status_code}")

        body = (res.json().get("results") or {})
        self._check(body.get("common") or {}, "좌표조회")

        items = body.get("juso") or []
        if not items:
            raise GeocodeNotFound("좌표조회 결과 없음")

        # 주소는 찾았는데 좌표가 빈 문자열로 오는 곳이 있다(지번은 있으나 좌표 미구축).
        # 오류로 두면 매일 예약 실행마다 똑같이 실패하므로 '못찾음' 으로 확정한다.
        x, y = items[0].get("entX"), items[0].get("entY")
        if x in (None, "") or y in (None, ""):
            raise GeocodeNotFound(f"좌표 없음(entX/entY 비어 있음): {items[0].get('roadAddr', '')}")
        try:
            return float(x), float(y)
        except (TypeError, ValueError) as e:
            raise GeocodeError(f"좌표 파싱 실패: {e}") from e

    def _with_backoff(self, fn, *args):
        """속도 제한(E0007)·네트워크 끊김은 쉬었다 재시도한다. 다른 오류는 그대로 올린다.

        네트워크 예외(ConnectTimeout 등)를 잡지 않으면 3만 건 도는 중 한 번의 끊김으로
        프로세스가 죽는다. 끝내 안 되면 GeocodeError 로 바꿔 그 단지만 '오류(3)' 가 되고
        다음 실행에서 재시도된다.
        """
        for wait in _RATE_LIMIT_BACKOFF:
            try:
                return fn(*args)
            except (GeocodeRateLimited, requests.RequestException):
                time.sleep(wait)
        try:
            return fn(*args)
        except requests.RequestException as e:
            raise GeocodeError(f"네트워크 오류: {type(e).__name__}") from e

    def geocode(self, address: str) -> Coord:
        juso = self._with_backoff(self._search, address)
        x, y = self._with_backoff(self._coord, juso)
        lng, lat = utmk_to_wgs84(x, y)
        return Coord(lat=lat, lng=lng, matched_address=juso.get("roadAddr", address))


# ─── 좌표계 변환 (EPSG:5179 UTM-K → EPSG:4326 WGS84) ──────────────────────────
# 행안부 좌표제공 API 는 UTM-K 로 준다. 지도(위경도)에 찍으려면 변환이 필요하다.
# pyproj 의존을 피하려고 횡축 메르카토르 역변환을 직접 구현한다
# (GRS80 타원체, 중앙자오선 127.5°E, 원점위도 38°N, 축척 0.9996, false E/N 1000000/2000000).
import math

_A = 6378137.0                 # GRS80 장반경
_F = 1 / 298.257222101         # 편평률
_K0 = 0.9996
_LON0 = math.radians(127.5)
_LAT0 = math.radians(38.0)
_FE = 1_000_000.0
_FN = 2_000_000.0

_E2 = _F * (2 - _F)
_EP2 = _E2 / (1 - _E2)


def _meridian_arc(lat: float) -> float:
    e2, e4, e6 = _E2, _E2**2, _E2**3
    return _A * (
        (1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * lat
        - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * lat)
        + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * lat)
        - (35 * e6 / 3072) * math.sin(6 * lat)
    )


def utmk_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """UTM-K(EPSG:5179) → (경도, 위도) degrees."""
    m = (y - _FN) / _K0 + _meridian_arc(_LAT0)
    mu = m / (_A * (1 - _E2 / 4 - 3 * _E2**2 / 64 - 5 * _E2**3 / 256))

    e1 = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))
    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )

    sin1, cos1, tan1 = math.sin(phi1), math.cos(phi1), math.tan(phi1)
    c1 = _EP2 * cos1**2
    t1 = tan1**2
    n1 = _A / math.sqrt(1 - _E2 * sin1**2)
    r1 = _A * (1 - _E2) / (1 - _E2 * sin1**2) ** 1.5
    d = (x - _FE) / (n1 * _K0)

    lat = phi1 - (n1 * tan1 / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * _EP2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * _EP2 - 3 * c1**2) * d**6 / 720
    )
    lon = _LON0 + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * _EP2 + 24 * t1**2) * d**5 / 120
    ) / cos1

    return math.degrees(lon), math.degrees(lat)


def default_geocoder() -> Geocoder:
    return JusoGeocoder()
