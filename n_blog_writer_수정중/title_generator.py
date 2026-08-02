"""블로그 제목/키워드 생성.

- generate_title(category): cate1/cate2 용. Perplexity 로 최근 이슈 기반 제목 뽑기.
- generate_title_from_keyword(category, keyword): cate3/cate4 용.
  사용자가 준 키워드를 바탕으로 gpt-4o-mini 로 제목만 다듬는다.
- extract_keyword(title, category): cate1/cate2 제목에서 이미지 검색용
  핵심 키워드를 gpt-4o-mini 로 추출.

work_subject.txt 의 빈 자리를 채우기 위한 용도. 파일 처리는 하지 않고
순수 생성만 담당한다.
"""
import os
import re
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

TITLE_MODEL = "sonar-pro"          # Perplexity — 웹검색 기반 제목
KEYWORD_MODEL = "gpt-4o-mini"      # 키워드 추출 / 키워드 기반 제목 생성

# cate1/cate2: 카테고리만 받아서 화제거리를 웹에서 찾아 제목을 만든다.
CATEGORY_PROMPTS = {
    "cate1": (
        "국내 연예인 한 명을 임의로 골라, 그 인물의 근황·이슈·작품 활동 중 "
        "하나를 다루는 네이버 블로그 제목을 만들어주세요. "
        "가능하면 최근 2주 이내의 이슈·활동·발언·작품 소식을 우선으로 하되, "
        "마땅한 최신 이슈가 없다면 그 인물의 최근 근황이나 진행 중인 작품 활동으로 "
        "대체해도 좋습니다. "
        "배우·가수·아이돌·예능인 등 다양한 인물 풀에서 뽑아주세요. "
        "실존 인물과 실제 활동 내용을 담되, "
        "기사 헤드라인을 그대로 가져오지 말고 개인 블로그 제목 톤으로 다시 써주세요.\n"
        "예: 애프터스쿨 비쥬얼 센터 유이 최근 근황\n"
        "예: 배우 손예진 새 드라마 촬영장 목격담 정리\n"
        "예: 아이유 신곡 티저 공개 반응 모아봤어요\n"
        "예: 예능 대세 이용진 요즘 스케줄 총정리"
    ),
    "cate2": (
        "음식 하나를 임의로 골라 소개하는 네이버 블로그 제목을 만들어주세요. "
        "요리(완성된 음식) 일 수도 있고 식재료 하나일 수도 있습니다. "
        "한식·양식·중식·일식·분식·디저트·간식 같은 다양한 요리 카테고리와, "
        "채소·과일·해산물·육류·유제품 같은 다양한 재료군 중에서 골고루 뽑아주세요. "
        "특정 음식만 반복해서 고르지 말고 매번 다른 종류를 선택해주세요. "
        "레시피·효능·제철·손질법·보관법·활용법 같은 관점 중 하나를 다루면 됩니다.\n"
        "예: 제철 대하 손질법과 보관 요령 정리\n"
        "예: 집에서 만드는 부드러운 크림 파스타 레시피\n"
        "예: 여름철 오이 활용법과 효능 총정리\n"
        "예: 겉바속촉 간장 찜닭 만드는 법"
    ),
}

# cate3/cate4: 사용자가 준 키워드를 바탕으로 제목만 다듬는다. 웹검색 불필요.
KEYWORD_TITLE_PROMPTS = {
    "cate3": (
        "다음 부동산 단지 정보를 다루는 네이버 블로그 제목을 만들어주세요.\n"
        "단지/키워드: {keyword}\n\n"
        "입지·세대 구성·교통·학군·투자 포인트 관점에서 관심을 끌 만한, "
        "구체적이면서 과장 없는 담백한 제목을 뽑아주세요.\n"
        "예: 숭의역 라온프라이빗 다양한 분양 정보"
    ),
    "cate4": (
        "다음 모바일/웨어러블 제품을 다루는 네이버 블로그 제목을 만들어주세요.\n"
        "제품/키워드: {keyword}\n\n"
        "주요 스펙, 색상, 디자인, 기능, 카메라, 가격 등 정보 위주의 "
        "구체적이고 담백한 제목을 뽑아주세요. 사전예약 관련 내용은 언급하지 마세요.\n"
        "예: 갤럭시워치7 새 기능과 색상 옵션 정리"
    ),
}

# cate1/cate2 제목에서 이미지 검색용 키워드를 뽑는 지시문.
KEYWORD_EXTRACT_PROMPTS = {
    "cate1": (
        "다음 네이버 블로그 제목에서 이미지 검색에 사용할 핵심 키워드를 뽑아주세요.\n"
        "인물 이름 하나만으로 충분합니다. 다른 부가어(작품명, 소속사 등) 는 붙이지 마세요.\n\n"
        "제목: {title}\n\n"
        "키워드만 한 줄로 출력하세요. 따옴표나 설명은 붙이지 마세요."
    ),
    "cate2": (
        "다음 네이버 블로그 제목에서 이미지 검색에 사용할 핵심 키워드를 뽑아주세요.\n"
        "음식/재료 이름 중심으로 1~2어절 정도가 좋습니다. "
        "부가어(레시피, 만드는 법, 효능 등) 는 빼주세요.\n"
        "예: '겉바속촉 간장 찜닭 만드는 법' → 간장 찜닭\n"
        "예: '여름철 오이 활용법과 효능 총정리' → 오이\n\n"
        "제목: {title}\n\n"
        "키워드만 한 줄로 출력하세요. 따옴표나 설명은 붙이지 마세요."
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


def _load_pplx_key() -> str:
    load_dotenv(BASE_DIR / ".env")
    key = os.getenv("PPLX_KEY")
    if not key:
        raise RuntimeError(".env 의 PPLX_KEY 가 없습니다.")
    return key


def _load_openai_key() -> str:
    load_dotenv(BASE_DIR / ".env")
    key = os.getenv("GPT_KEY")
    if not key:
        raise RuntimeError(".env 의 GPT_KEY 가 없습니다.")
    return key


def _cleanup(text: str) -> str:
    text = _CITATION.sub("", text).strip()
    return text.strip('"').strip("'").strip()


def generate_title(category: str) -> str:
    """cate1/cate2 전용. 웹검색 기반으로 최근 이슈 제목 하나를 돌려준다."""
    if category not in CATEGORY_PROMPTS:
        raise ValueError(
            f"generate_title 은 cate1/cate2 만 지원합니다. 받은 값: {category}"
        )

    from openai import OpenAI

    client = OpenAI(api_key=_load_pplx_key(), base_url="https://api.perplexity.ai")
    resp = client.chat.completions.create(
        model=TITLE_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": CATEGORY_PROMPTS[category] + FORMAT_HINT},
        ],
        temperature=0.9,
    )
    return _cleanup(resp.choices[0].message.content or "")


def generate_title_from_keyword(category: str, keyword: str) -> str:
    """cate3/cate4 전용. 사용자가 준 키워드로 제목 한 줄을 만든다."""
    if category not in KEYWORD_TITLE_PROMPTS:
        raise ValueError(
            f"generate_title_from_keyword 는 cate3/cate4 만 지원합니다. 받은 값: {category}"
        )
    if not keyword:
        raise ValueError("키워드가 비어 있습니다.")

    from openai import OpenAI

    client = OpenAI(api_key=_load_openai_key())
    resp = client.chat.completions.create(
        model=KEYWORD_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": KEYWORD_TITLE_PROMPTS[category].format(keyword=keyword) + FORMAT_HINT,
            },
        ],
        temperature=0.8,
    )
    return _cleanup(resp.choices[0].message.content or "")


def extract_keyword(title: str, category: str) -> str:
    """cate1/cate2 제목에서 이미지 검색용 키워드를 뽑는다."""
    if category not in KEYWORD_EXTRACT_PROMPTS:
        raise ValueError(
            f"extract_keyword 는 cate1/cate2 만 지원합니다. 받은 값: {category}"
        )

    from openai import OpenAI

    client = OpenAI(api_key=_load_openai_key())
    resp = client.chat.completions.create(
        model=KEYWORD_MODEL,
        messages=[
            {"role": "system", "content": "핵심 키워드만 정확히 뽑아주는 도우미입니다."},
            {
                "role": "user",
                "content": KEYWORD_EXTRACT_PROMPTS[category].format(title=title),
            },
        ],
        temperature=0.3,
    )
    return _cleanup(resp.choices[0].message.content or "")
