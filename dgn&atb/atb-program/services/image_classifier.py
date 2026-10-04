"""Places365 ResNet18 기반 '건물/아파트 외관' 이미지 분류기.

torchvision ResNet18 + Places365(365개 장면 클래스) 사전학습 가중치로
이미지의 장면을 분류하고, 건물 외관 계열 카테고리의 확률 합이 임계값 이상이면
'아파트(건물) 이미지'로 판정한다. (로고/평면도/지도/포스터/실내 등은 낮게 나옴)

- 모델 가중치(~45MB)와 카테고리 파일은 최초 1회 자동 다운로드해 models/ 에 캐시.
- torch/torchvision 미설치 시 ClassifierUnavailable 예외 → 호출측에서 필터링 건너뜀.
- CPU 전용으로도 한 장당 수십 ms 수준.
"""
from __future__ import annotations

import io
import threading
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
WEIGHTS_PATH = MODELS_DIR / "resnet18_places365.pth.tar"
CATEGORIES_PATH = MODELS_DIR / "categories_places365.txt"
IO_PATH = MODELS_DIR / "IO_places365.txt"

WEIGHTS_URL = "http://places2.csail.mit.edu/models_places365/resnet18_places365.pth.tar"
CATEGORIES_URL = (
    "https://raw.githubusercontent.com/csailvision/places365/master/categories_places365.txt"
)
IO_URL = "https://raw.githubusercontent.com/csailvision/places365/master/IO_places365.txt"

# 건물 외관 계열로 인정할 Places365 카테고리 키워드 (부분일치)
POSITIVE_KEYWORDS = (
    "apartment", "building", "residential", "house", "skyscraper",
    "tower", "downtown", "street", "facade", "neighborhood", "mansion",
    "courtyard", "hotel", "office", "hospital", "balcony", "construction",
    "plaza", "alley", "driveway", "parking",
)

# 건물 계열 확률 합이 이 값 이상이면 '아파트 이미지'로 판정 (보정 가능)
THRESHOLD = 0.20


class ClassifierUnavailable(RuntimeError):
    """torch/torchvision 미설치 또는 모델 로드 실패."""


_lock = threading.Lock()
_state: dict = {"loaded": False, "model": None, "categories": None,
                "positive_idx": None, "outdoor_mask": None, "transform": None}


# ─── 다운로드 ─────────────────────────────────────────────────────────────────
def _download(url: str, dest: Path):
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as resp, open(tmp, "wb") as f:
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
    tmp.replace(dest)


# ─── 로드 (lazy, 스레드 안전) ─────────────────────────────────────────────────
def _ensure_loaded():
    if _state["loaded"]:
        return
    with _lock:
        if _state["loaded"]:
            return
        try:
            import torch
            from torchvision import models, transforms
        except ImportError as e:
            raise ClassifierUnavailable(
                "torch/torchvision 미설치. 설치:\n"
                "  pip install torch torchvision --index-url "
                "https://download.pytorch.org/whl/cpu"
            ) from e

        if not WEIGHTS_PATH.exists():
            _download(WEIGHTS_URL, WEIGHTS_PATH)
        if not CATEGORIES_PATH.exists():
            _download(CATEGORIES_URL, CATEGORIES_PATH)
        if not IO_PATH.exists():
            _download(IO_URL, IO_PATH)

        # 카테고리 로드: 각 줄 '/a/apartment_building/outdoor 8'
        categories: list[str] = []
        for line in CATEGORIES_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            name = line.split(" ")[0]
            categories.append(name)

        # 실내/실외 라벨: 각 줄 '/a/airfield 2' (1=indoor, 2=outdoor), 순서 동일
        outdoor_mask: list[bool] = []
        for line in IO_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            io_label = line.split(" ")[-1]
            outdoor_mask.append(io_label == "2")

        positive_idx = [
            i for i, name in enumerate(categories)
            if any(kw in name.lower() for kw in POSITIVE_KEYWORDS)
        ]

        # ResNet18 (365 클래스) + Places365 가중치
        model = models.resnet18(num_classes=365)
        try:
            ckpt = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=False)
        except TypeError:  # 구버전 torch (weights_only 인자 없음)
            ckpt = torch.load(WEIGHTS_PATH, map_location="cpu")
        state_dict = {k.replace("module.", ""): v
                      for k, v in ckpt["state_dict"].items()}
        model.load_state_dict(state_dict)
        model.eval()

        transform = transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

        import torch as _torch
        outdoor_idx = [i for i, v in enumerate(outdoor_mask) if v]
        _state.update(loaded=True, model=model, categories=categories,
                      positive_idx=positive_idx,
                      outdoor_idx=_torch.tensor(outdoor_idx, dtype=_torch.long),
                      transform=transform)


# ─── 분류 ─────────────────────────────────────────────────────────────────────
def classify(image_bytes: bytes) -> dict:
    """이미지 바이트 → 분류 결과 dict.

    - score        : 건물 외관 계열 카테고리 확률 합
    - is_building  : score >= THRESHOLD
    - outdoor_prob : 실외(outdoor) 카테고리 확률 합
    - is_outdoor   : outdoor_prob >= 0.5 (실내보다 실외일 가능성 높음)
    - top_category / top_prob : 최상위 장면
    """
    _ensure_loaded()
    import torch
    from PIL import Image

    pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = _state["transform"](pil).unsqueeze(0)
    with torch.no_grad():
        logits = _state["model"](tensor)
        probs = torch.softmax(logits, dim=1)[0]

    score = float(probs[_state["positive_idx"]].sum())
    outdoor_prob = float(probs[_state["outdoor_idx"]].sum())
    top_prob, top_idx = torch.max(probs, dim=0)
    return {
        "is_building": score >= THRESHOLD,
        "score": score,
        "outdoor_prob": outdoor_prob,
        "is_outdoor": outdoor_prob >= 0.5,
        "top_category": _state["categories"][int(top_idx)],
        "top_prob": float(top_prob),
    }


def is_building_image(image_bytes: bytes) -> bool:
    """간단 판정. 분류 불가(예외)는 호출측에서 처리."""
    return classify(image_bytes)["is_building"]
