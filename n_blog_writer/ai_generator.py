"""AI 로 블로그 본문을 생성한다.

- generate_body(title): 실제 사용. Perplexity 로 본문 생성 → 각주 정리.
- generate_and_compare(title): 3사 비교용 유틸. 워크플로에는 안 쓰지만,
  프롬프트/모델 변경 후 톤 재확인이 필요할 때 남겨둔다.
"""
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict

from dotenv import load_dotenv

LogFn = Callable[[str], None]

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

# 모델은 여기서만 바꾸면 된다.
OPENAI_MODEL = "gpt-4o-mini"
PPLX_MODEL = "sonar-pro"
GEMINI_MODEL = "gemini-2.5-flash"

CATEGORY_SYSTEM_PROMPTS = {
    "cate1": (
        "당신은 연예 이슈를 다루는 네이버 블로그 작가입니다. "
        "팬의 시선에서 친근한 존댓말로, 과장 없이 담백하게 인물의 근황과 활동을 정리합니다."
    ),
    "cate2": (
        "당신은 사회 이슈와 뉴스를 다루는 네이버 블로그 작가입니다. "
        "사실을 정확히 전달하되 자극적인 표현 없이 존댓말로 차분하게 사건의 배경과 흐름을 설명합니다."
    ),
    "cate3": (
        "당신은 부동산 분양 정보를 다루는 네이버 블로그 작가입니다. "
        "입지, 세대 구성, 교통, 학군, 투자 포인트를 정리하고, "
        "마지막 문단에서 관심 있는 분들이 문의할 수 있도록 자연스럽게 유도합니다."
    ),
    "cate4": (
        "당신은 스마트폰 신제품과 구매 정보를 다루는 네이버 블로그 작가입니다. "
        "주요 스펙과 특징, 저렴하게 구매할 수 있는 방법(자급제, 알뜰폰, 통신사 이동 등)을 "
        "실용적인 톤으로 정리합니다."
    ),
}

USER_PROMPT_TMPL = (
    "다음 제목으로 네이버 블로그 본문을 작성해 주세요.\n\n"
    "제목: {title}\n\n"
    "요구사항:\n"
    "- 500~800자 내외\n"
    "- 문단 3~5개로 자연스럽게 분리\n"
    "- 존댓말, 과장 없는 담백한 톤\n"
    "- 최신 정보가 필요하면 웹 검색으로 사실을 확인하되\n"
    "  본문에는 각주 번호([1], [2] 등)를 넣지 말 것\n"
    "- 마크다운·이모지·특수기호 없이 순수 텍스트로만"
)


def _system_prompt(category: str) -> str:
    if category not in CATEGORY_SYSTEM_PROMPTS:
        raise ValueError(f"알 수 없는 카테고리: {category}")
    return CATEGORY_SYSTEM_PROMPTS[category]


def _load_keys() -> Dict[str, str]:
    load_dotenv(BASE_DIR / ".env")
    keys = {
        "openai": os.getenv("GPT_KEY"),
        "pplx": os.getenv("PPLX_KEY"),
        "gemini": os.getenv("GEMINI_API_KEY"),
    }
    missing = [k for k, v in keys.items() if not v]
    if missing:
        raise RuntimeError(f".env 에 다음 키가 없습니다: {missing}")
    return keys


def _save(provider: str, title: str, body: str, log: LogFn) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"{provider}_{stamp}.txt"
    path.write_text(
        f"[제목]\n{title}\n\n[본문]\n{body}\n", encoding="utf-8"
    )
    log(f"[{provider}] 저장: {path}")
    return path


def _gen_openai(title: str, category: str, api_key: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": _system_prompt(category)},
            {"role": "user", "content": USER_PROMPT_TMPL.format(title=title)},
        ],
        temperature=0.8,
    )
    return (resp.choices[0].message.content or "").strip()


def _gen_pplx(title: str, category: str, api_key: str) -> str:
    # Perplexity 는 OpenAI 호환 엔드포인트를 제공한다.
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")
    resp = client.chat.completions.create(
        model=PPLX_MODEL,
        messages=[
            {"role": "system", "content": _system_prompt(category)},
            {"role": "user", "content": USER_PROMPT_TMPL.format(title=title)},
        ],
        temperature=0.8,
    )
    return (resp.choices[0].message.content or "").strip()


def _gen_gemini(title: str, category: str, api_key: str) -> str:
    from google import genai

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=_system_prompt(category) + "\n\n" + USER_PROMPT_TMPL.format(title=title),
    )
    return (resp.text or "").strip()


def _strip_citations(text: str) -> str:
    """본문 안의 [N] 각주 마커를 제거하고 붙어버린 공백을 정리한다.

    Perplexity 는 프롬프트로 금지시켜도 종종 [6] 형태로 각주를 붙인다.
    발행 시 그대로 노출되면 어색하므로 후처리로 제거.
    """
    text = re.sub(r"\[\d+\]", "", text)
    # 각주 제거 후 남은 " ." / " ," / " )" 같은 잉여 공백 정리.
    text = re.sub(r" +([.,)!?])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def generate_body(title: str, category: str, log: LogFn = print) -> str:
    """Perplexity 로 본문을 생성해 각주 정리 후 돌려준다.

    실제로 발행되는 최종본을 나중에 다시 볼 수 있도록
    output/{category}_{timestamp}.txt 로도 함께 저장한다.
    """
    keys = _load_keys()
    log(f"[pplx][{category}] 본문 생성 시작")
    t0 = time.time()
    raw = _gen_pplx(title, category, keys["pplx"])
    body = _strip_citations(raw)
    log(
        f"[pplx][{category}] 본문 생성 완료 ({time.time() - t0:.1f}초, "
        f"원본 {len(raw)}자 → 정리 {len(body)}자)"
    )
    _save(category, title, body, log)
    return body


def generate_and_compare(
    title: str, category: str, log: LogFn = print
) -> Dict[str, Path]:
    """같은 제목/카테고리를 3사에 던져 각각 텍스트 파일로 저장한다.

    한 곳이 실패해도 나머지는 계속 진행한다. 돌려주는 dict 는
    성공한 provider → 저장 경로.
    """
    keys = _load_keys()
    providers = [
        ("openai", _gen_openai, keys["openai"]),
        ("pplx", _gen_pplx, keys["pplx"]),
        ("gemini", _gen_gemini, keys["gemini"]),
    ]

    saved: Dict[str, Path] = {}
    for name, fn, key in providers:
        log(f"[{name}][{category}] 생성 시작")
        t0 = time.time()
        try:
            body = fn(title, category, key)
            elapsed = time.time() - t0
            log(f"[{name}][{category}] 생성 완료 ({elapsed:.1f}초, {len(body)}자)")
            saved[name] = _save(name, title, body, log)
        except Exception as exc:
            log(f"[{name}][{category}] 실패: {type(exc).__name__}: {exc}")

    return saved
