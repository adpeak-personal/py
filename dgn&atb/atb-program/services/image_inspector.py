"""이미지 검수기 — '글씨 없는 아파트 외관' 1장을 고르기 위한 판정.

판정 기준:
  1) 아파트(건물) 외관일 것      → Places365 (is_building)
  2) 실내 사진이 아닐 것          → Places365 (is_outdoor)
  3) 글씨(텍스트)가 없을 것       → Tesseract OCR

inspect() 는 {passed, reason, detail} 을 반환한다.
검수기를 쓸 수 없으면(torch/tesseract 미설치 등) InspectorUnavailable 예외.
"""
from __future__ import annotations

import io
import re

import config
from services import image_classifier

# ── '진짜 글자' 판정 임계값 ───────────────────────────────────────────────────
# OCR 은 텍스처(창문·하늘·나뭇잎)를 2~3글자 라틴/단일 한글로 환각하므로,
# 노이즈를 걸러내려고 '신뢰도 높은 한글 2자+ / 4자리+ 숫자 / @핸들 / 긴 라틴단어'
# 만 진짜 글자(워터마크/캡션)로 인정한다.
_HANGUL = re.compile(r"[가-힣]")

_HANGUL_MIN = 2     # 한글은 2자 이상 (단일 한글은 환각)
_HANGUL_CONF = 65
_DIGIT_CONF = 60    # 4자리 이상 숫자 (매물번호/가격/전화)
_HANDLE_CONF = 50   # @핸들 (인스타 등 워터마크)
_LATIN_MIN = 5      # 라틴 단어는 5자 이상
_LATIN_CONF = 63

_OCR_MIN_WORDS = 1
_UPSCALE_TARGET = 1400  # 전체 이미지 OCR 시 최소 긴변(px)


def _is_text_token(word: str, conf: float) -> bool:
    n_h = len(_HANGUL.findall(word))
    latin = sum(1 for ch in word if ch.isascii() and ch.isalpha())
    return (
        (n_h >= _HANGUL_MIN and conf >= _HANGUL_CONF)
        or (re.search(r"\d{4,}", word) and conf >= _DIGIT_CONF)
        or ("@" in word and len(word) >= 4 and conf >= _HANDLE_CONF)
        or (latin >= _LATIN_MIN and conf >= _LATIN_CONF)
    )


class InspectorUnavailable(RuntimeError):
    pass


# ─── 전처리 ───────────────────────────────────────────────────────────────────
def _prep(pil):
    """흑백 + 대비강조 — 흐릿/반투명 워터마크 글자를 또렷하게."""
    from PIL import ImageOps
    g = ImageOps.grayscale(pil)
    return ImageOps.autocontrast(g, cutoff=1)


def _upscale(pil, target_long: int):
    """긴 변이 target 보다 작으면 확대 (작은 글자 OCR 향상)."""
    w, h = pil.size
    long_side = max(w, h)
    if long_side >= target_long or long_side == 0:
        return pil
    scale = target_long / long_side
    from PIL import Image as _Image
    return pil.resize((max(1, int(w * scale)), max(1, int(h * scale))), _Image.LANCZOS)


def _ocr_words(pil) -> list[str]:
    """전처리된 이미지 1장에서 신뢰도 높은 글자 단어 목록."""
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_EXE
    cfg = f"--oem 1 --psm 11 --tessdata-dir {config.TESSDATA_DIR}"
    try:
        data = pytesseract.image_to_data(
            pil, lang="kor+eng", config=cfg, output_type=pytesseract.Output.DICT
        )
    except pytesseract.TesseractError as e:
        raise InspectorUnavailable(f"Tesseract 실행 실패: {e}") from e
    except pytesseract.TesseractNotFoundError as e:
        raise InspectorUnavailable(f"Tesseract 실행파일을 찾을 수 없음: {e}") from e

    out: list[str] = []
    for word, conf in zip(data["text"], data["conf"]):
        w = word.strip()
        try:
            c = float(conf)
        except (ValueError, TypeError):
            c = -1
        if _is_text_token(w, c):
            out.append(w)
    return out


def _detect_text_words(image_bytes: bytes) -> list[str]:
    """글자/워터마크 검출. 전체 1회(싼 검사) → 구석·띠 확대 스캔(정밀).

    워터마크는 주로 하단/구석에 반투명으로 박히므로, 전체에서 못 잡으면
    하단띠·상단띠·좌우하단 코너를 확대해서 다시 본다. 하나라도 잡히면 즉시 반환.
    """
    try:
        from PIL import Image
    except ImportError as e:
        raise InspectorUnavailable(f"PIL 미설치: {e}") from e

    pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # 1) 전체 이미지 (업스케일 + 전처리)
    words = _ocr_words(_prep(_upscale(pil, _UPSCALE_TARGET)))
    if words:
        return words

    # 2) 워터마크 빈출 영역을 잘라 2배 확대 후 정밀 스캔
    w, h = pil.size
    if w < 8 or h < 8:
        return []
    regions = [
        (0, int(h * 0.78), w, h),                 # 하단 띠
        (0, 0, w, int(h * 0.20)),                 # 상단 띠
        (int(w * 0.52), int(h * 0.55), w, h),     # 우하단 코너
        (0, int(h * 0.55), int(w * 0.48), h),     # 좌하단 코너
        (int(w * 0.52), 0, w, int(h * 0.40)),     # 우상단 코너
    ]
    for box in regions:
        crop = pil.crop(box)
        words = _ocr_words(_prep(_upscale(crop, max(crop.size) * 2)))
        if words:
            return words
    return []


# ── 우하단/하단 워터마크(dongA.com 류) 전용 검출 ─────────────────────────────
# 중앙 반투명 워터마크는 출처 차단으로 거르고, 여기서는 '하단 코너의 읽히는 글씨'만 본다.
_DOMAIN_RE = re.compile(
    r"(co\.?kr|[a-z]{2,}\.com|\.com|\.net|\.kr|news|press|©|ⓒ|daum|naver|"
    r"donga|chosun|joins|hankyung|yna|yonhap|newsis|edaily|herald|seoul|"
    r"\.co\b|뉴스|일보|경제|신문)", re.I)


def _ocr_tokens(pil, psm: int) -> list[tuple[str, float]]:
    """(단어, 신뢰도) 목록. 코너 워터마크 분석용 (필터 없이 원시 토큰)."""
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_EXE
    cfg = f"--oem 1 --psm {psm} --tessdata-dir {config.TESSDATA_DIR}"
    try:
        data = pytesseract.image_to_data(
            pil, lang="kor+eng", config=cfg, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractError as e:
        raise InspectorUnavailable(f"Tesseract 실행 실패: {e}") from e
    except pytesseract.TesseractNotFoundError as e:
        raise InspectorUnavailable(f"Tesseract 실행파일을 찾을 수 없음: {e}") from e
    out: list[tuple[str, float]] = []
    for word, conf in zip(data["text"], data["conf"]):
        w = word.strip()
        try:
            c = float(conf)
        except (ValueError, TypeError):
            c = -1
        if w:
            out.append((w, c))
    return out


def _corner_watermark(image_bytes: bytes) -> bool:
    """하단(우/좌/전폭)의 또렷한 사이트·언론사 워터마크(dongA.com 류) 검출.

    워터마크는 보통 구석에 작게 박히므로 '타이트하게 잘라 5배 확대'해야 OCR 이 읽는다.
    글자가 거의 없는 코너에 단어 같은 토큰이 여러 개 = 워터마크로 본다.
    """
    from PIL import Image, ImageOps
    pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = pil.size
    if w < 24 or h < 24:
        return False

    # (rx0, ry0, rx1, ry1) 비율 — 하단 구석을 좁게
    regions = [
        (0.58, 0.85, 1.00, 1.00),   # 우하단
        (0.00, 0.85, 0.42, 1.00),   # 좌하단
        (0.00, 0.90, 1.00, 1.00),   # 하단 전폭
    ]

    def alnum(s: str) -> int:
        return sum(1 for c in s if c.isalnum())

    for rx0, ry0, rx1, ry1 in regions:
        crop = pil.crop((int(w * rx0), int(h * ry0), int(w * rx1), int(h * ry1)))
        cw, ch = crop.size
        if cw < 12 or ch < 6:
            continue
        # 작은 워터마크는 2~3배가 적당 (과확대하면 글자가 뭉개져 안 읽힘)
        for zoom in (3, 2):
            big = crop.resize((cw * zoom, ch * zoom), Image.LANCZOS)
            g = ImageOps.autocontrast(ImageOps.grayscale(big), cutoff=2)
            tokens = _ocr_tokens(g, 6) + _ocr_tokens(g, 7)

            joined = " ".join(t for t, _ in tokens)
            words3 = [(t, c) for t, c in tokens if alnum(t) >= 3 and c >= 55]
            # 단어 같은 토큰 2개 이상 / 5자 이상 한 단어 / 도메인 패턴
            if (len(words3) >= 2
                    or any(alnum(t) >= 5 and c >= 55 for t, c in tokens)
                    or (_DOMAIN_RE.search(joined)
                        and sum(alnum(t) for t, _ in tokens) >= 4)):
                return True
    return False


def detect_text_words(image_bytes: bytes) -> list[str]:
    """진단용 — 검출된 글자 단어 목록 반환."""
    return _detect_text_words(image_bytes)


def _count_text_words(image_bytes: bytes) -> int:
    return len(_detect_text_words(image_bytes))


def has_text(image_bytes: bytes) -> bool:
    return _count_text_words(image_bytes) >= _OCR_MIN_WORDS


# ─── 종합 검수 ────────────────────────────────────────────────────────────────
def inspect(image_bytes: bytes) -> dict:
    """{passed: bool, reason: str, detail: dict}.

    reason: 'ok' | 'not_building' | 'indoor' | 'has_text'
    """
    # 1·2) 외관/실내 판정
    try:
        cls = image_classifier.classify(image_bytes)
    except image_classifier.ClassifierUnavailable as e:
        raise InspectorUnavailable(str(e)) from e

    detail = {
        "score": round(cls["score"], 3),
        "outdoor_prob": round(cls["outdoor_prob"], 3),
        "top_category": cls["top_category"],
    }

    if not cls["is_outdoor"]:
        return {"passed": False, "reason": "indoor", "detail": detail}
    if not cls["is_building"]:
        return {"passed": False, "reason": "not_building", "detail": detail}

    # 3) 인물 제외 — 사람이 앞에 크게 나온 사진 (작은 배경 행인은 통과)
    try:
        from services import person_detector
        if person_detector.has_prominent_person(image_bytes):
            return {"passed": False, "reason": "has_person", "detail": detail}
    except person_detector.PersonDetectorUnavailable:
        pass  # torchvision 미설치 등 — 사람검사 건너뜀

    # 4) 글씨 검출 — (a) 전체/구석 강한토큰 + (b) 우하단 사이트 워터마크
    n_words = _count_text_words(image_bytes)
    detail["text_words"] = n_words
    if n_words >= _OCR_MIN_WORDS or _corner_watermark(image_bytes):
        return {"passed": False, "reason": "has_text", "detail": detail}

    return {"passed": True, "reason": "ok", "detail": detail}
