from func import *
from openai import OpenAI
from dotenv import load_dotenv
from upload import (download_image, upload_image_to_gcs,
                    upload_thumbnail_to_gcs)
import os
import sys
import re
import requests

_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE_DIR, '.env'))

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
PPLX_KEY = os.getenv("PPLX_KEY")

# 찍고 백엔드 — blog_jobs 큐를 폴링할 베이스 URL
BACK_API = os.getenv("ZK_BACK_API", "http://localhost:3041")

# 클라이언트 객체 생성 (여기에 API 키 입력)
client = OpenAI(
    api_key=PPLX_KEY,
    base_url="https://api.perplexity.ai" # 목적지를 OpenAI에서 퍼플렉시티로 변경!
)

# 네이버 검색 API 키 (https://developers.naver.com/apps 에서 발급)


# 본문 후처리용 정규식 상수 —
# _Q: 따옴표(홑/쌍/전각/낫표) 옵션 매칭용 문자셋
# _RIVAL_SITES: 경쟁 사이트/커뮤니티 이름 (모두 '찍고' 로 치환)
_Q = r"[\'\"‘’“”「」『』]"
_RIVAL_SITES = [
    "옆커폰", "성지나라", "폰슐랭", "올댓폰", "좌표나라",
    "사나폰", "폰사와", "싸당", "청년폰", "성지매니아", "휴대폰 직방","하이휴대폰이야",
]
_rival_pattern = "|".join(map(re.escape, _RIVAL_SITES))


def it_blog():

    # ─── .env 로드 검증용 print ───
    from upload import _BASE_DIR as UPLOAD_BASE_DIR, GCS_BUCKET, GCS_KEY_FILE

    def _mask(v, keep=4):
        if not v:
            return f"<빈값> ({type(v).__name__})"
        s = str(v)
        return s if len(s) <= keep * 2 else f"{s[:keep]}...{s[-keep:]} (len={len(s)})"

    env_path = os.path.join(_BASE_DIR, '.env')
    print("=" * 60)
    print(f"[env 검증] frozen(exe): {getattr(sys, 'frozen', False)}")
    print(f"[env 검증] it_blog _BASE_DIR: {_BASE_DIR}")
    print(f"[env 검증] upload  _BASE_DIR: {UPLOAD_BASE_DIR}")
    print(f"[env 검증] .env 경로: {env_path}")
    print(f"[env 검증] .env 존재: {os.path.exists(env_path)}")
    print(f"[env 검증] cwd: {os.getcwd()}")
    print("-" * 60)
    print(f"[env 검증] NAVER_CLIENT_ID     : {_mask(NAVER_CLIENT_ID)}")
    print(f"[env 검증] NAVER_CLIENT_SECRET : {_mask(NAVER_CLIENT_SECRET)}")
    print(f"[env 검증] PPLX_KEY            : {_mask(PPLX_KEY)}")
    print(f"[env 검증] BACK_API            : {BACK_API}")
    print(f"[env 검증] ZK_JWT_SECRET       : {_mask(os.getenv('ZK_JWT_SECRET'))}")
    print(f"[env 검증] ZK_MASTER_USER_ID   : {os.getenv('ZK_MASTER_USER_ID')}")
    print(f"[env 검증] ZK_GCS_BUCKET       : {GCS_BUCKET or '<빈값>'}")
    print(f"[env 검증] GCS_KEY_FILE 경로   : {GCS_KEY_FILE}")
    print(f"[env 검증] GCS_KEY_FILE 존재   : {os.path.exists(GCS_KEY_FILE)}")
    print("=" * 60)


    """blog_jobs 큐에서 due 인 작업 1건을 가져와 글 생성·발행 한다.

    워커 흐름:
      1. GET /api/blog-jobs/due       — due 인 PENDING 1건 (없으면 종료)
      2. PATCH /:id/claim             — PROCESSING 로 선점 (race 방지)
      3. 퍼플렉시티로 글 생성 + 네이버 이미지 + HTML 빌드
      4. PATCH /:id/complete          — posts 에 저장 + DONE 처리
         실패시 PATCH /:id/fail       — FAILED + 에러 메모
    """
    # 1) due 작업 가져오기
    try:
        res = requests.get(f"{BACK_API}/api/blog-jobs/due", timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"[it_blog] /due 조회 실패: {e}")
        return

    job = res.json().get("job")
    if not job:
        print("[it_blog] due 작업 없음 — 스킵")
        return

    job_id = job["id"]
    title = job["title"]
    keywords = job.get("keywords") or []
    # 이미지 GCS 업로드 시 사용할 폴더 prefix — 백엔드가 board_slug/sub_slug 로 알려줌
    # 백엔드 blog-jobs 에서 board='community', sub='blog' 로 내려주면 최종 폴더는 'community/blog'.
    # 폴더가 백엔드 AI_BLOG_GCS_PREFIX 와 일치해야 finalizeTmpUrls 이후에도 위치가 안 어긋남.
    board_slug = job.get("board_slug") or "community"
    sub_slug = job.get("sub_slug") or "blog"
    dest_prefix = f"{board_slug}/{sub_slug}" if sub_slug else board_slug

    # 글 생성에 쓸 핵심 키워드 — 전체 중 첫 번째 (예: "강남 휴대폰 성지")
    article_keyword = keywords[0] if keywords else title

    # 이미지 검색에 쓸 키워드 — 기종(갤럭시/아이폰) 들어간 키워드만 추출
    # 이유: "강남 휴대폰 성지" 같은 키워드는 이미지 검색 결과가 부실하므로,
    # "갤럭시S26" / "아이폰 17 프로" 같은 모델명으로 검색해야 좋은 이미지 확보.
    image_keywords = [k for k in keywords if ("갤럭시" in k) or ("아이폰" in k)]
    # 매칭되는 게 있으면 그 중 첫 번째, 없으면 article_keyword 로 폴백
    image_keyword = image_keywords[0] if image_keywords else article_keyword

    print(
        f"[it_blog] 작업 픽업: id={job_id}, title={title!r}, "
        f"article_kw={article_keyword!r}, image_kw={image_keyword!r}"
    )

    # 2) 선점 — 다른 워커와 동시 처리 방지
    try:
        claim = requests.patch(f"{BACK_API}/api/blog-jobs/{job_id}/claim", timeout=10)
        if claim.status_code == 409:
            print(f"[it_blog] 이미 다른 워커가 가져감 (id={job_id})")
            return
        claim.raise_for_status()
    except Exception as e:
        print(f"[it_blog] claim 실패: {e}")
        return

    # 3) 글 생성 + HTML 빌드
    try:
        article = generate_it_post(title, article_keyword)

        # 퍼플렉시티가 간헐적으로 같은 문단을 무한 반복하는 케이스 대응 —
        # 첫 반복 지점 이후는 잘라낸다.
        article = _dedupe_repeated_paragraphs(article)

        # 프롬프트의 지시문이 본문에 그대로 노출되는 경우를 방지 —
        # "…사이트만 언급…" 형태의 괄호(반각/전각 모두)를 제거.

        article = re.sub(r"\s*[(（][^()（）]*사이트만\s*언급[^()（）]*[)）]", "", article)

        # "카페나 타 사이트 (말고)(, 오직)" 계열 문구를 통째로 제거 —
        # ‘카페’, "타 사이트" 처럼 따옴표(홑/쌍/전각/낫표)가 붙어도 매치되도록
        # 각 명사 양옆에 옵션 따옴표 [ ' " ‘ ’ “ ” 「 」 『 』 ] 를 허용.
        article = re.sub(
            rf"\s*{_Q}?카페{_Q}?\s*나\s*{_Q}?타\s*사이트{_Q}?(\s*말고)?(\s*,\s*오직)?",
            "",
            article,
        )

        # 남아있는 "카페", "카페의", "카페에서", "카페를" 제거 (따옴표로 감싸져 있어도 함께 제거)
        article = re.sub(rf"{_Q}?카페(?:의|에서|를)?{_Q}?", "", article)

        # 경쟁 사이트/커뮤니티 이름은 전부 '찍고' 로 치환
        article = re.sub(rf"{_Q}?(?:{_rival_pattern}){_Q}?", "찍고", article)

        image_urls = search_naver_image(image_keyword, display=30)
        # build_blog_html 이 (본문 HTML, 썸 GCS URL) 을 리턴.
        # 썸은 실제로 본문에 들어간 첫 이미지의 원본 바이트로 만든 것 → 반드시 GCS 에 있음.
        final_html, thumbnail_url = build_blog_html(article, image_urls, dest_prefix=dest_prefix)
    except Exception as e:
        print(f"[it_blog] 글 생성 실패: {e}")
        try:
            requests.patch(
                f"{BACK_API}/api/blog-jobs/{job_id}/fail",
                json={"error": f"generation: {e}"},
                timeout=10,
            )
        except Exception as e2:
            print(f"[it_blog] fail 보고 실패: {e2}")
        return

    # 4) 완료 보고 — 백엔드가 posts 에 INSERT + DONE 마킹
    try:
        complete = requests.patch(
            f"{BACK_API}/api/blog-jobs/{job_id}/complete",
            json={"content": final_html, "thumbnail_url": thumbnail_url},
            timeout=20,
        )
        complete.raise_for_status()
        data = complete.json()
        print(f"[it_blog] 발행 완료: post_id={data.get('post_id')} url={data.get('result_url')}")
    except Exception as e:
        print(f"[it_blog] complete 실패: {e}")
        # 글은 만들어졌지만 저장이 실패한 케이스 — FAILED 로 기록
        try:
            requests.patch(
                f"{BACK_API}/api/blog-jobs/{job_id}/fail",
                json={"error": f"complete: {e}"},
                timeout=10,
            )
        except Exception as e2:
            print(f"[it_blog] fail 보고 실패: {e2}")


# ─── HTML 출력 공통 스타일 (인라인) ──────────────────────────
# 인라인 CSS 를 쓰는 이유:
#   1) 클라이언트의 prose / reset CSS 와 무관하게 일관된 렌더
#   2) 네이버/카카오 등 외부 블로그에 그대로 붙여넣어도 거의 비슷하게 보임
# 수정 포인트:
#   - 문단 사이 여백 → _PARA_STYLE 의 margin
#   - 이미지 위/아래 여백 → _IMG_BLOCK_STYLE 의 margin
#   - 전체 가운데 정렬 → _WRAPPER_STYLE 의 text-align: center

_PARA_STYLE = "margin: 1.4em 0; line-height: 1.85;"
_H_STYLE = "margin: 1.8em 0 0.8em; line-height: 1.4; font-weight: 800;"
_LIST_STYLE = "margin: 1.4em auto; padding: 0; list-style: none; max-width: 90%;"
_LI_STYLE = "margin: 0.6em 0; line-height: 1.7;"
_BLOCKQUOTE_STYLE = (
    "margin: 1.8em auto; padding: 1em 1.2em; "
    "border-left: 3px solid #cbd5e1; background: #f8fafc; "
    "max-width: 90%; line-height: 1.75; border-radius: 6px;"
)
# 표는 border 진하게 + 외곽선까지 둘러서 한눈에 표인 게 보이도록.
_TABLE_STYLE = (
    "margin: 1.8em auto; border-collapse: collapse; "
    "border: 2px solid #475569;"
)
_TD_STYLE = "border: 1px solid #475569; padding: 0.7em 1em;"
_TH_STYLE = (
    "border: 1px solid #475569; padding: 0.7em 1em; "
    "background: #e2e8f0; font-weight: 700; color: #0f172a;"
)

# 이미지 — 위아래 여백 충분히. line-height:0 으로 위아래 미세 빈공간 제거.
_IMG_BLOCK_STYLE = "margin: 2.4em 0; text-align: center; line-height: 0;"
_IMG_STYLE = (
    "max-width: 100%; height: auto; display: inline-block; "
    "border-radius: 8px; vertical-align: middle;"
)

# 전체 래퍼 — 가운데 정렬 + 기본 line-height
_WRAPPER_STYLE = "text-align: center; line-height: 1.85;"


def build_blog_html(article: str, image_urls: list[str],
                    dest_prefix: str = "community/blog") -> tuple[str, str | None]:
    """article + 네이버 이미지 URL 리스트 → (본문 HTML, 썸네일 GCS URL).

    Args:
        dest_prefix: GCS 업로드 시 저장될 폴더 prefix. 백엔드 /due 응답의
                     board_slug/sub_slug 조합으로 만든 값 (예: 'community/blog').
                     백엔드 AI_BLOG_GCS_PREFIX 와 일치시켜야 위치 어긋남 없음.

    1) article 을 HTML 블록으로 변환 (clean_and_convert_to_html — 스타일 인라인 포함)
    2) 문단 수에 따라 image_urls 에서 랜덤 2~3개 선택 → 다운로드 → GCS 업로드
    3) **첫 성공 픽의 원본 바이트로 썸(600px webp) 도 같이 만들어 GCS 업로드**
    4) 블록 사이에 균등 간격으로 <img> 삽입
    5) 전체를 가운데 정렬 컨테이너로 감싸 반환
    반환: (본문 HTML, 썸 GCS 풀 URL 또는 None)
    """
    blocks = [b for b in clean_and_convert_to_html(article).split('\n') if b.strip()]
    n_blocks = len(blocks)

    # 본문이 없거나 이미지가 없으면 텍스트만 래핑해 반환 (썸도 없음)
    if n_blocks == 0:
        return f'<div style="{_WRAPPER_STYLE}"></div>', None
    if not image_urls:
        return f'<div style="{_WRAPPER_STYLE}">{chr(10).join(blocks)}</div>', None

    # 문단(블록) 수에 따라 1~3개
    if n_blocks < 4:
        n_images = 1
    elif n_blocks < 8:
        n_images = 2
    else:
        n_images = 3
    n_images = min(n_images, len(image_urls))

    # 랜덤 추출 → 각 URL 다운로드 → 본문용 GCS 업로드
    # 첫 성공한 다운로드의 raw bytes 를 재활용해 썸도 만들어 업로드.
    picks = random.sample(image_urls, n_images)
    ts = int(time.time())
    gcs_urls: list[str] = []
    thumb_url: str | None = None
    for i, src in enumerate(picks):
        dl = download_image(src)
        if not dl:
            continue
        raw, ct = dl
        gcs = upload_image_to_gcs(raw, f"itblog_{ts}_{i}.jpg", ct, dest_prefix=dest_prefix)
        if not gcs:
            continue
        gcs_urls.append(gcs)
        # 첫 성공 픽 → 같은 raw 로 썸도 만든다. 이미 body 에 들어간 이미지라 매칭됨.
        if thumb_url is None:
            thumb_url = upload_thumbnail_to_gcs(raw, dest_prefix=dest_prefix)

    if not gcs_urls:
        return f'<div style="{_WRAPPER_STYLE}">{chr(10).join(blocks)}</div>', None

    # 블록 사이 균등 위치 계산 (예: 블록 9개 / 이미지 2개 → step=3 → [3, 6])
    step = max(1, n_blocks // (len(gcs_urls) + 1))
    positions = [(i + 1) * step for i in range(len(gcs_urls))]

    # 뒤에서부터 삽입해야 앞쪽 인덱스가 깨지지 않음
    for pos, url in zip(reversed(positions), reversed(gcs_urls)):
        img_html = (
            f'<p style="{_IMG_BLOCK_STYLE}">'
            f'<img src="{url}" alt="" style="{_IMG_STYLE}" />'
            f'</p>'
        )
        blocks.insert(pos, img_html)

    return f'<div style="{_WRAPPER_STYLE}">\n{chr(10).join(blocks)}\n</div>', thumb_url




def search_naver_image(query: str, display: int = 1, sort: str = "sim",
                       filter_size: str = "large") -> list[str]:
    """
    네이버 이미지 검색 API로 이미지 URL 리스트를 반환.

    Args:
        query: 검색어
        display: 가져올 이미지 개수 (1~100)
        sort: "sim"(정확도순) / "date"(날짜순)
        filter_size: "all" / "large" / "medium" / "small"

    Returns:
        이미지 URL 리스트 (썸네일 아닌 원본 link 기준)
    """
    url = "https://openapi.naver.com/v1/search/image"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query": query,
        "display": max(1, min(display, 30)),
        "sort": sort,
        "filter": filter_size,
    }
    r = requests.get(url, headers=headers, params=params, timeout=10)
    r.raise_for_status()
    items = r.json().get("items", [])
    return [it["link"] for it in items]


def naver_image_tag(query: str, alt: str | None = None,
                    width: str = "100%") -> str:
    """
    네이버에서 이미지 1장 검색해서 바로 붙일 수 있는 <img> 태그 문자열로 반환.
    검색 결과가 없으면 빈 문자열.
    """
    urls = search_naver_image(query, display=1)
    if not urls:
        return ""
    safe_alt = (alt or query).replace('"', '&quot;')
    return f'<img src="{urls[0]}" alt="{safe_alt}" style="width:{width};height:auto;" />'



def generate_it_post(topic, keyword):
    system_prompt = """
    너는 10년 차 IT 전문 블로거이자 휴대폰 성지에 대해 조사하는 '찍고' 플랫폼 마케터야.
    [절대 규칙]
    1. AI 특유의 기계적인 인사말(안녕하세요 등), 뻔한 미사여구 절대 금지.
    2. 모든 정보는 최신 실시간 검색 결과를 바탕으로 팩트(숫자, 가격, 정책) 위주로 작성할 것.
    3. 타사(경쟁사) 이름이나 특정 대리점 추천 및 언급은 절대 하지 말고, 오직 '찍고' 플랫폼을 어필하되, 키워드 2~3번 정도만 자연스럽게 어필할것.
    4. 특수문자는 (. , ? ' ")만 허용하며, [1], [2] 같은 검색 출처 인용구는 출력에서 완전히 제거할 것.
    """


    user_prompt = f"핵심 키워드 : {keyword} / 주제: {topic}\n라는 주제로 IT 정보성 글을 작성해주고, 바로 업로드 할 수 있는 블로그 글로 만들어주고, 해당 내용은 '찍고' 사이트에서 확인 가능하다고 언급해줘, 필요하면 표 같은것도 넣고 600자 이상 ~ 1300자 미만으로 자연스럽게 작성 해줘"

    response = client.chat.completions.create(
        model="sonar", # 2. 퍼플렉시티의 빠르고 저렴한 최신 검색 모델
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7
    )
    
    return response.choices[0].message.content


# 마크다운 구조(헤딩 #, 리스트 -/*/숫자., 표 |, 인용 >) 라인 감지용 —
# 이런 블록은 문장 단위 dedupe 을 건너뛴다 (문장 split 이 구조를 깨므로).
_STRUCT_LINE_RE = re.compile(r'^\s*(?:[#*\->|]|\d+\.)', re.MULTILINE)


def _dedupe_units(units: list[str]) -> list[str]:
    """같은 유닛이 다시 나오는 순간부터 이후를 버린 리스트를 반환.
    비교는 공백을 다 제거한 정규화 문자열 기준."""
    seen: set[str] = set()
    kept: list[str] = []
    for u in units:
        norm = re.sub(r'\s+', '', u)
        if not norm:
            continue
        if norm in seen:
            break
        seen.add(norm)
        kept.append(u.strip())
    return kept


def _dedupe_repeated_paragraphs(article: str) -> str:
    """같은 문단/문장이 다시 등장하는 순간부터 이후를 전부 버린다.

    퍼플렉시티가 간헐적으로 동일 문단(빈 줄로 구분) 또는 한 문단 안에서
    동일 문장을 무한 반복하는 이슈 대응 — 반복 감지 지점부터 이후는 버림.
    산문 문단만 문장 단위로 자르고, 마크다운 구조 블록은 그대로 둔다.
    """
    # 1) 문단 단위 dedupe (빈 줄 기준)
    paragraphs = _dedupe_units(re.split(r'\n\s*\n', article))

    # 2) 문장 단위 dedupe — 산문 문단에만 적용
    result: list[str] = []
    for para in paragraphs:
        if _STRUCT_LINE_RE.search(para):
            result.append(para)
            continue
        sentences = re.split(r'(?<=[.!?])\s+', para)
        deduped = _dedupe_units(sentences)
        if deduped:
            result.append(' '.join(deduped))
    return '\n\n'.join(result)


def _inline_format(text: str) -> str:
    """줄 안쪽의 인라인 마크다운 처리 (**, 남은 *, # 제거)."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = text.replace('*', '')
    text = text.replace('#', '')
    return text.strip()


def clean_and_convert_to_html(article: str) -> str:
    """
    퍼플렉시티 결과물(article) 정리 후 HTML로 변환.

    처리 내용:
      - [1], [2][5] 같은 출처 표시 제거
      - --- (수평선) 제거
      - #, ## 헤딩 -> <h1>, <h2> ...
      - **bold** -> <strong>
      - 마크다운 표 -> <table>
      - - / * / 숫자. 리스트 -> <ul>, <ol>
      - > 인용 -> <blockquote>
      - 일반 문장 -> <p>
    """
    # 1) 출처 표시 제거: [숫자] 모두 제거
    text = re.sub(r'\[\d+\]', '', article)

    # 2) 들여쓰기/끝쪽 공백 정리
    lines = [ln.strip() for ln in text.split('\n')]

    html_parts: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # 빈 줄
        if not line:
            i += 1
            continue

        # 수평선
        if re.fullmatch(r'-{3,}', line):
            i += 1
            continue

        # 헤딩
        m = re.match(r'^(#{1,6})\s+(.+)$', line)
        if m:
            level = len(m.group(1))
            html_parts.append(
                f'<h{level} style="{_H_STYLE}">{_inline_format(m.group(2))}</h{level}>'
            )
            i += 1
            continue

        # 인용문
        if line.startswith('>'):
            content = line.lstrip('>').strip()
            html_parts.append(
                f'<blockquote style="{_BLOCKQUOTE_STYLE}">{_inline_format(content)}</blockquote>'
            )
            i += 1
            continue

        # 표 (헤더 다음 줄이 |---|---| 형태)
        if line.startswith('|') and line.endswith('|') \
                and i + 1 < len(lines) and re.fullmatch(r'\|[\s\-:|]+\|', lines[i + 1]):
            header_cells = [c.strip() for c in line.strip('|').split('|')]
            i += 2
            body_rows = []
            while i < len(lines) and lines[i].startswith('|') and lines[i].endswith('|'):
                body_rows.append([c.strip() for c in lines[i].strip('|').split('|')])
                i += 1

            buf = [f'<table style="{_TABLE_STYLE}">']
            buf.append('<thead><tr>')
            buf.extend(
                f'<th style="{_TH_STYLE}">{_inline_format(c)}</th>' for c in header_cells
            )
            buf.append('</tr></thead><tbody>')
            for row in body_rows:
                buf.append('<tr>')
                buf.extend(
                    f'<td style="{_TD_STYLE}">{_inline_format(c)}</td>' for c in row
                )
                buf.append('</tr>')
            buf.append('</tbody></table>')
            html_parts.append(''.join(buf))
            continue

        # 번호 리스트 — list-style:none 이라 1./2./... 를 직접 prefix
        if re.match(r'^\d+\.\s+', line):
            items = []
            n = 1
            while i < len(lines) and re.match(r'^\d+\.\s+', lines[i]):
                content = re.sub(r'^\d+\.\s+', '', lines[i])
                items.append(f'<li style="{_LI_STYLE}">{n}. {_inline_format(content)}</li>')
                i += 1
                n += 1
            html_parts.append(f'<ol style="{_LIST_STYLE}">' + ''.join(items) + '</ol>')
            continue

        # 불릿 리스트 (- 또는 *)
        if re.match(r'^[-*]\s+', line):
            items = []
            while i < len(lines) and re.match(r'^[-*]\s+', lines[i]):
                content = re.sub(r'^[-*]\s+', '', lines[i])
                # 가운데 정렬이라 불릿 대신 · 한 글자만 앞에
                items.append(f'<li style="{_LI_STYLE}">· {_inline_format(content)}</li>')
                i += 1
            html_parts.append(f'<ul style="{_LIST_STYLE}">' + ''.join(items) + '</ul>')
            continue

        # 일반 문단
        html_parts.append(f'<p style="{_PARA_STYLE}">{_inline_format(line)}</p>')
        i += 1

    return '\n'.join(html_parts)