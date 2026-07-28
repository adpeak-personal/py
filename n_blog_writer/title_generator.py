"""카테고리별로 블로그 제목 하나를 뽑는다 (Perplexity).

web 검색이 붙어 있어서 실제로 지금 화제인 인물/사건/상품 기반의 제목이
뽑힌다. Gemini/GPT 로 뽑으면 "다양한 활동" 류의 뜬구름이 되기 쉬워서
Perplexity 로 고정.

work_subject.txt 의 빈 제목 자리에 넣기 위한 용도. 나중에 서버로 옮길
예정이라 파일 처리는 하지 않고 순수 생성만 담당한다.
"""
import os
import re
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

TITLE_MODEL = "sonar-pro"

# 카테고리 → 지시문. 실제 화제/최근 정보에서 뽑도록 유도.
CATEGORY_PROMPTS = {
    "cate1": (
        "국내 연예인 한 명을 임의로 골라, 그 인물의 근황·이슈·작품 활동 중 "
        "하나를 다루는 네이버 블로그 제목을 만들어주세요. "
        "꼭 오늘 가장 화제인 인물일 필요는 없고 배우·가수·아이돌·예능인 등 "
        "다양한 인물 풀에서 뽑아주세요. 실존 인물과 실제 활동 내용을 담되, "
        "기사 헤드라인을 그대로 가져오지 말고 개인 블로그 제목 톤으로 다시 써주세요.\n"
        "예: 애프터스쿨 비쥬얼 센터 유이 최근 근황\n"
        "예: 배우 손예진 새 드라마 촬영장 목격담 정리\n"
        "예: 아이유 신곡 티저 공개 반응 모아봤어요\n"
        "예: 예능 대세 이용진 요즘 스케줄 총정리"
    ),
    "cate2": (
        "지금 국내에서 가장 화제가 되고 있는 사회 이슈나 뉴스 하나를 소개하는 "
        "네이버 블로그 제목을 만들어주세요. 실제로 최근 벌어진 사건을 다뤄주세요. "
        "단, 정치/정당/선거/정치인/외교 관련 주제는 제외하고 "
        "생활·사건사고·환경·문화·경제·인물 같은 주제에서 골라주세요.\n"
        "예: 하천서 발견된 샴악어"
    ),
    "cate3": (
        "국내에서 최근 분양 중이거나 곧 분양 예정인 신규 아파트/오피스텔 하나를 "
        "소개하는 네이버 블로그 제목을 만들어주세요. "
        "실제로 존재하는 단지명과 지역을 넣어주세요.\n"
        "예: 숭의역 라온프라이빗 다양한 분양 정보"
    ),
    "cate4": (
        "최근 출시됐거나 곧 출시될 모바일/웨어러블 신제품 하나의 정보와 "
        "저렴하게 사는 방법(자급제, 알뜰폰, 통신사 이동, 사전예약, 할인 등)을 "
        "다루는 네이버 블로그 제목을 만들어주세요. "
        "아이폰·갤럭시(폴더블 포함)·애플워치·갤럭시워치·아이패드·갤럭시탭·갤럭시링 등 "
        "다양한 제품군 중에서 임의로 하나 골라, 실제로 존재하는 최신 모델명을 넣어주세요.\n"
        "예: 아이폰17 프로 다양한 정보와 저렴하게 사는 방법\n"
        "예: 갤럭시Z플립7 사전예약 혜택과 자급제 가격 비교\n"
        "예: 애플워치 시리즈10 알뜰폰 요금제로 저렴하게 쓰는 법\n"
        "예: 갤럭시탭 S11 울트라 스펙 정리와 학생 할인 팁"
    ),
}

SYSTEM_PROMPT = (
    "당신은 네이버 블로그 제목을 뽑는 카피라이터입니다. "
    "웹 검색 결과를 바탕으로, 클릭을 유도하면서도 과장이 심하지 않은 "
    "구체적인 제목을 만듭니다."
)

FORMAT_HINT = (
    "\n\n제목만 한 줄로 출력하세요. 따옴표, 번호, 각주([1] 등), "
    "마크다운 기호는 붙이지 마세요."
)

_CITATION = re.compile(r"\[\d+\]")


def _load_key() -> str:
    load_dotenv(BASE_DIR / ".env")
    key = os.getenv("PPLX_KEY")
    if not key:
        raise RuntimeError(".env 의 PPLX_KEY 가 없습니다.")
    return key


def _cleanup(text: str) -> str:
    text = _CITATION.sub("", text).strip()
    # 따옴표로 감싸서 오는 경우 벗겨낸다.
    return text.strip('"').strip("'").strip()


def generate_title(category: str) -> str:
    """카테고리(cate1~cate4) 를 받아 제목 한 줄을 돌려준다."""
    if category not in CATEGORY_PROMPTS:
        raise ValueError(f"알 수 없는 카테고리: {category}")

    from openai import OpenAI

    client = OpenAI(api_key=_load_key(), base_url="https://api.perplexity.ai")
    resp = client.chat.completions.create(
        model=TITLE_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": CATEGORY_PROMPTS[category] + FORMAT_HINT},
        ],
        temperature=0.9,
    )
    return _cleanup(resp.choices[0].message.content or "")
