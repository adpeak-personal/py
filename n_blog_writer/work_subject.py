"""work_subject.txt 로드/저장.

한 줄에 하나, 형식: `제목|카테고리`. 제목이 비어 있으면 title_generator 로
채워야 한다. 나중에 서버로 옮길 예정이라 파일 IO 만 여기서 담당한다.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent
SUBJECT_FILE = BASE_DIR / "work_subject.txt"


@dataclass
class Subject:
    title: str
    category: str


def load_subjects(path: Path = SUBJECT_FILE) -> List[Subject]:
    if not path.exists():
        raise FileNotFoundError(f"주제 파일이 없습니다: {path}")

    subjects: List[Subject] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 1)
        if len(parts) != 2:
            raise ValueError(f"형식 오류 (제목|카테고리): {line}")
        title, category = parts[0].strip(), parts[1].strip()
        subjects.append(Subject(title=title, category=category))
    return subjects


def save_subjects(subjects: List[Subject], path: Path = SUBJECT_FILE) -> None:
    """제목이 채워진 최신 상태를 파일에 다시 쓴다."""
    lines = [f"{s.title}|{s.category}" for s in subjects]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
