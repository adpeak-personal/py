"""설정과 자료 모양.

찍고(zzikko)가 정본이다. 아이디·비밀번호·프로필·IP 를 전부 찍고 어드민에서 관리하고,
이 프로그램은 받아다 쓰기만 한다. 여기 파일에는 **찍고에 들어갈 열쇠만** 둔다.

settings.json 예시 (이 폴더에 두고, git 에 올리지 않는다):

    {
      "api_base": "https://zzikko.co.kr",
      "admin_email": "admin@example.com",
      "admin_password": "...",
      "headless": false
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = BASE_DIR / "settings.json"
# 크롬 프로필이 쌓이는 곳. 프로필 하나가 폴더 하나다
PROFILE_ROOT = BASE_DIR / "profiles"

# 프로필에 User-Agent 를 안 적었을 때 쓰는 값
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@dataclass
class Settings:
    api_base: str
    admin_email: str
    admin_password: str
    headless: bool = False
    # VPN 자동 전환 (비우면 사람이 직접 바꾼다). {location} 자리에 프로필의 VPN 위치가 들어간다
    vpn_command: str = ""
    vpn_wait_seconds: int = 8

    @classmethod
    def load(cls, path: Path = SETTINGS_FILE) -> "Settings":
        if not path.exists():
            raise FileNotFoundError(
                f"설정 파일이 없습니다: {path}\n"
                "settings.sample.json 을 settings.json 으로 복사해 채워 주세요."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = [k for k in ("api_base", "admin_email", "admin_password") if not data.get(k)]
        if missing:
            raise ValueError(f"설정에 빠진 값이 있습니다: {', '.join(missing)}")
        return cls(
            api_base=str(data["api_base"]).rstrip("/"),
            admin_email=data["admin_email"],
            admin_password=data["admin_password"],
            headless=bool(data.get("headless", False)),
            vpn_command=str(data.get("vpn_command", "") or ""),
            vpn_wait_seconds=int(data.get("vpn_wait_seconds", 8)),
        )


@dataclass
class Account:
    """찍고 nwork 계정 하나."""

    id: int
    login_id: str
    password: str
    last_login_check_at: str | None = None


@dataclass
class Profile:
    """크롬 프로필 하나 — **아이디 하나가 붙는다.**

    IP 는 여러 프로필이 나눠 쓸 수 있다(프로필과 한 쌍이 아니다). 묶는 단위는
    `expected_ip` 이고, 같은 IP 를 쓰는 프로필을 몇 개까지 둘지는 사람이 정한다.

    IP 를 쓰는 길이 두 가지다. **프록시**(`proxy_host`)를 적으면 브라우저만 그 서버를
    거쳐 나가고, 비워 두면 **지금 PC 가 쓰는 회선**(VPN 포함) 그대로 나간다.
    어느 쪽이든 `expected_ip` 와 실제로 보이는 IP 가 같아야 작업을 시작한다.
    """

    id: int
    name: str
    proxy_host: str = ""
    proxy_port: int | None = None
    proxy_user: str = ""
    proxy_pass: str = ""
    user_agent: str = ""
    # 이 프로필일 때 밖에서 보여야 할 IP. 비어 있으면 첫 작업 때 기록한다
    expected_ip: str = ""
    # VPN 에서 고를 자리 이름 (자동 전환에 쓴다)
    vpn_location: str = ""
    accounts: list[Account] = field(default_factory=list)

    def dir_for(self, account: "Account") -> Path:
        """크롬 프로필 폴더는 **아이디마다** 따로 둔다 (IP 는 같이 쓴다).

        ⚠️ 한 폴더에 아이디 셋을 몰면 안 된다 — 네이버는 브라우저 하나에 한 계정만
        로그인시키므로, 돌릴 때마다 로그아웃→로그인을 반복하게 된다. 그게 세션을
        유지하는 것보다 훨씬 눈에 띈다. 폴더를 나누면 각자 쿠키를 들고 있어서
        두 번째 실행부터는 로그인 자체를 안 한다.

        같은 IP 에서 계정 셋이 보이는 건 집·사무실에서도 흔한 모습이다.
        """
        return PROFILE_ROOT / self.name / account.login_id

    @property
    def proxy(self) -> dict[str, str] | None:
        """Playwright 가 받는 모양. 주소가 없으면 그냥 직접 연결한다."""
        if not self.proxy_host:
            return None
        server = self.proxy_host
        if "://" not in server:
            server = f"http://{server}"
        if self.proxy_port:
            server = f"{server}:{self.proxy_port}"
        proxy = {"server": server}
        if self.proxy_user:
            proxy["username"] = self.proxy_user
            proxy["password"] = self.proxy_pass
        return proxy

    @property
    def agent(self) -> str:
        return self.user_agent or DEFAULT_USER_AGENT
