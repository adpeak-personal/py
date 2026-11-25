"""찍고(zzikko) 어드민 API 클라이언트.

작업에 필요한 것(계정·비밀번호·프로필·IP)을 전부 여기서 받아 온다.
**이 프로그램은 아이디 목록을 들고 있지 않는다** — 찍고가 정본이다.

쓰는 길:
  POST /api/v1/auth/login            운영진으로 로그인 (쿠키 세션)
  GET  /api/v1/admin/blog/runner     프로필 + 계정(비밀번호 포함)
  POST /api/v1/admin/blog/login-result  로그인 결과 보고
"""
from __future__ import annotations

import requests

from config import Account, Profile, Settings


class ZzikkoError(RuntimeError):
    pass


class Zzikko:
    def __init__(self, settings: Settings) -> None:
        self.base = f"{settings.api_base}/api/v1"
        self.settings = settings
        self.session = requests.Session()
        # 사람이 쓰는 브라우저인 척할 이유가 없다. 우리 프로그램이라고 밝힌다
        self.session.headers["User-Agent"] = "zzikko-blog-writer/0.1"

    # ------------------------------------------------------------------
    def login(self) -> None:
        res = self.session.post(
            f"{self.base}/auth/login",
            json={"email": self.settings.admin_email, "password": self.settings.admin_password},
            timeout=20,
        )
        if not res.ok:
            raise ZzikkoError(f"찍고 로그인 실패({res.status_code}): {self._message(res)}")
        me = res.json()
        if me.get("role") != "운영진":
            raise ZzikkoError(f"운영진 계정이 아닙니다 (지금: {me.get('role')})")

    # ------------------------------------------------------------------
    def profiles(self, only: str | None = None) -> list[Profile]:
        """돌릴 프로필과 그 안의 계정들.

        ⚠️ 응답에 **비밀번호가 들어 있다.** 로그에 찍거나 파일로 떨구지 말 것.
        """
        res = self.session.get(
            f"{self.base}/admin/blog/runner",
            params={"profile": only} if only else None,
            timeout=30,
        )
        if not res.ok:
            raise ZzikkoError(f"프로필을 받지 못했습니다({res.status_code}): {self._message(res)}")

        out: list[Profile] = []
        for row in res.json().get("items", []):
            out.append(
                Profile(
                    id=row["id"],
                    name=row["name"],
                    proxy_host=row.get("proxyHost") or "",
                    proxy_port=row.get("proxyPort"),
                    proxy_user=row.get("proxyUser") or "",
                    proxy_pass=row.get("proxyPass") or "",
                    user_agent=row.get("userAgent") or "",
                    expected_ip=row.get("expectedIp") or "",
                    vpn_location=row.get("vpnLocation") or "",
                    accounts=[
                        Account(
                            id=a["id"],
                            login_id=a["loginId"],
                            password=a["password"],
                            last_login_check_at=a.get("lastLoginCheckAt"),
                        )
                        for a in row.get("accounts", [])
                    ],
                )
            )
        return out

    # ------------------------------------------------------------------
    def record_ip(self, profile: Profile, ip: str) -> None:
        """브라우저에서 잰 IP 를 그 프로필에 적어 둔다 (찍고가 비어 있을 때만 받는다)."""
        res = self.session.post(
            f"{self.base}/admin/blog/profiles/{profile.id}/ip", json={"ip": ip}, timeout=20
        )
        if not res.ok:
            raise ZzikkoError(f"IP 를 기록하지 못했습니다({res.status_code}): {self._message(res)}")

    # ------------------------------------------------------------------
    def report_login(self, account: Account, ok: bool, profile: str | None = None) -> None:
        """로그인 결과를 알린다. 실패로 보고하면 그 계정이 '쓸 수 없음'으로 내려간다."""
        body: dict[str, object] = {"accountId": account.id, "ok": ok}
        if ok and profile:
            body["profile"] = profile
        res = self.session.post(f"{self.base}/admin/blog/login-result", json=body, timeout=20)
        if not res.ok:
            raise ZzikkoError(f"결과를 보고하지 못했습니다({res.status_code}): {self._message(res)}")

    # ------------------------------------------------------------------
    @staticmethod
    def _message(res: "requests.Response") -> str:
        try:
            return str(res.json().get("message", res.text[:200]))
        except Exception:
            return res.text[:200]
