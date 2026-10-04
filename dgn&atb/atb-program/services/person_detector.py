"""사람(인물) 탐지 — torchvision COCO 사전학습 탐지기(SSDLite, 경량).

이미지에 사람이 '크게' 나오면(인물 위주 사진) 걸러내기 위한 판정.
배경의 작은 행인까지 막으면 정상 외관샷도 떨궈지므로, 일정 크기 이상 + 신뢰도
이상인 사람만 '있음'으로 본다.

torch/torchvision 미설치 시 PersonDetectorUnavailable.
"""
from __future__ import annotations

import io
import threading

# COCO 에서 person 클래스 id = 1
_PERSON_LABEL = 1

# 판정 임계값 (튜닝 가능) — 값이 클수록 덜 빡셈(사람이 더 크게 나와야 걸림)
_SCORE_MIN = 0.50        # 탐지 신뢰도
_AREA_FRAC = 0.080       # 사람 박스 면적이 전체의 8% 이상
_HEIGHT_FRAC = 0.35      # 또는 사람 키가 이미지 높이의 35% 이상


class PersonDetectorUnavailable(RuntimeError):
    pass


_lock = threading.Lock()
_state: dict = {"loaded": False, "model": None, "preprocess": None}


def _ensure_loaded():
    if _state["loaded"]:
        return
    with _lock:
        if _state["loaded"]:
            return
        try:
            import torch  # noqa: F401
            from torchvision.models.detection import (
                ssdlite320_mobilenet_v3_large,
                SSDLite320_MobileNet_V3_Large_Weights,
            )
        except ImportError as e:
            raise PersonDetectorUnavailable(
                "torchvision 미설치. pip install torch torchvision") from e

        weights = SSDLite320_MobileNet_V3_Large_Weights.DEFAULT
        model = ssdlite320_mobilenet_v3_large(weights=weights)
        model.eval()
        _state.update(loaded=True, model=model, preprocess=weights.transforms())


def detect_persons(image_bytes: bytes) -> list[dict]:
    """사람 박스 목록 [{score, area_frac, height_frac}] 반환 (신뢰도순)."""
    _ensure_loaded()
    import torch
    from PIL import Image

    pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    W, H = pil.size
    batch = [_state["preprocess"](pil)]
    with torch.no_grad():
        pred = _state["model"](batch)[0]

    out: list[dict] = []
    boxes = pred["boxes"]
    labels = pred["labels"]
    scores = pred["scores"]
    for i in range(len(labels)):
        if int(labels[i]) != _PERSON_LABEL:
            continue
        score = float(scores[i])
        if score < _SCORE_MIN:
            continue
        x1, y1, x2, y2 = (float(v) for v in boxes[i])
        bw, bh = max(0.0, x2 - x1), max(0.0, y2 - y1)
        out.append({
            "score": score,
            "area_frac": (bw * bh) / (W * H) if W and H else 0.0,
            "height_frac": bh / H if H else 0.0,
        })
    out.sort(key=lambda d: d["score"], reverse=True)
    return out


def has_prominent_person(image_bytes: bytes) -> bool:
    """앞에 크게 나온 사람이 있으면 True (작은 배경 행인은 무시)."""
    for p in detect_persons(image_bytes):
        if p["area_frac"] >= _AREA_FRAC or p["height_frac"] >= _HEIGHT_FRAC:
            return True
    return False
