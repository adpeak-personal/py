"""환경설정 로드 및 공용 상수/헬퍼.

atb-program 은 독립 실행된다. 비밀값은 atb-program/.env 가 단일 소스이며,
OS 환경변수로 개별 항목을 덮어쓸 수 있다. (템플릿: .env.example)
"""
from __future__ import annotations

import os
import datetime
from pathlib import Path

# ─── .env 로드 ────────────────────────────────────────────────────────────────
_PROGRAM_DIR = Path(__file__).resolve().parent
ENV_PATH = _PROGRAM_DIR / ".env"


def _load_env(path: Path) -> dict[str, str]:
    """아주 단순한 .env 파서 (KEY="VALUE" / KEY=VALUE)."""
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.strip().strip('"').strip("'")
        data[key.strip()] = val
    return data


_ENV: dict[str, str] = _load_env(ENV_PATH)


def env(key: str, default: str = "") -> str:
    """우선순위: OS 환경변수 > .env > default."""
    return os.environ.get(key) or _ENV.get(key) or default


# ─── API 키 ───────────────────────────────────────────────────────────────────
DATA_AUTH_KEY = env("DATA_AUTH_KEY")
NAVER_CLIENT_ID = env("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = env("NAVER_CLIENT_SECRET")

# ─── MySQL ────────────────────────────────────────────────────────────────────
MYSQL_HOST = env("MYSQL_HOST", "localhost")
MYSQL_USER = env("MYSQL_USER", "root")
MYSQL_PASSWORD = env("MYSQL_PASSWORD", "")
MYSQL_DATABASE = env("MYSQL_DATABASE", "test")
MYSQL_PORT = int(env("MYSQL_PORT", "3306"))

# ─── 엔드포인트 ────────────────────────────────────────────────────────────────
APT_TRADE_BASE_URL = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
)
NAVER_WEB_SEARCH_URL = "https://openapi.naver.com/v1/search/webkr.json"
NAVER_IMAGE_SEARCH_URL = "https://openapi.naver.com/v1/search/image.json"

# ─── Tesseract OCR ────────────────────────────────────────────────────────────
def _find_tesseract() -> str:
    candidates = [
        env("TESSERACT_EXE"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return "tesseract"  # PATH 에 있으면 사용


TESSERACT_EXE = _find_tesseract()
# eng/osd/kor 를 담은 프로젝트 로컬 tessdata
TESSDATA_DIR = str(_PROGRAM_DIR / "models" / "tessdata")


# ─── 지역 선택지 (프론트 SGG_OPTIONS 동일) ────────────────────────────────────
SGG_OPTIONS = [
    {"code": "11680", "name": "서울 강남구"},
    {"code": "11650", "name": "서울 서초구"},
    {"code": "11710", "name": "서울 송파구"},
    {"code": "11440", "name": "서울 마포구"},
    {"code": "11110", "name": "서울 종로구"},
    {"code": "11140", "name": "서울 중구"},
]


# ─── 헬퍼 ─────────────────────────────────────────────────────────────────────
def current_year_month() -> str:
    """현재 YYYYMM."""
    now = datetime.date.today()
    return f"{now.year}{now.month:02d}"


def format_price(raw: str | int) -> str:
    """'233,000' (만원 단위) → '23억 3,000만' 형식."""
    try:
        n = int(str(raw).replace(",", "").strip())
    except (ValueError, TypeError):
        return str(raw)
    if n >= 10000:
        eok = n // 10000
        rem = n % 10000
        return f"{eok}억" if rem == 0 else f"{eok}억 {rem:,}만"
    return f"{n:,}만"
