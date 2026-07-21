"""계정 정보 및 경로 설정."""
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CRED_FILE = BASE_DIR / "id_pwd.txt"
BLOG_DIR = BASE_DIR / "blog"
PROFILE_ROOT = BLOG_DIR / "profiles"


@dataclass
class Account:
    user_id: str
    password: str
    profile: str

    @property
    def profile_dir(self) -> Path:
        return PROFILE_ROOT / self.profile


def load_account(path: Path = CRED_FILE) -> Account:
    """id_pwd.txt 를 읽어 계정 정보를 만든다.

    형식: 아이디|비밀번호|프로필명   (한 줄에 하나)
    """
    if not path.exists():
        raise FileNotFoundError(f"계정 파일이 없습니다: {path}")

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3:
            raise ValueError(f"형식이 잘못된 줄입니다 (아이디|비번|프로필): {line}")
        return Account(*parts)

    raise ValueError(f"계정 정보가 비어 있습니다: {path}")
