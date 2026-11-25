"""VPN 자리 바꾸기.

VPN 프로그램마다 명령이 다르므로, **명령 틀은 `settings.json` 에 둔다.**
찍고에는 자리 이름(`vpnLocation`)만 저장한다.

    "vpn_command": "nordvpn.exe -c -n \\"{location}\\"",
    "vpn_wait_seconds": 8

⚠️ **명령을 찍고(서버)에 저장하지 않는 이유**: 서버가 내려준 문자열을 이 PC 에서
   그대로 실행하게 되면, 어드민 계정이 하나 뚫렸을 때 사무실 PC 에서 아무 명령이나
   돌릴 수 있는 길이 된다. 서버는 **자리 이름이라는 데이터만** 주고, 무엇을 실행할지는
   이 PC 의 설정 파일이 정한다.

`vpn_command` 가 비어 있으면 아무것도 하지 않는다 — 사람이 직접 바꾸는 방식이다.
"""
from __future__ import annotations

import subprocess
import time

from config import Profile, Settings


def switch_vpn(profile: Profile, settings: Settings) -> bool:
    """이 프로필 자리로 VPN 을 옮긴다. 자동 전환을 안 쓰면 False."""
    if not settings.vpn_command:
        return False
    if not profile.vpn_location:
        print(f"  [{profile.name}] VPN 위치 이름이 비어 있어 자동 전환을 건너뜁니다")
        return False

    command = settings.vpn_command.replace("{location}", profile.vpn_location)
    print(f"  VPN 전환: {profile.vpn_location}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print("  VPN 전환 명령이 끝나지 않았습니다 (120초)")
        return False

    if result.returncode != 0:
        out = (result.stderr or result.stdout or "").strip()[:200]
        print(f"  VPN 전환 실패 (코드 {result.returncode}): {out}")
        return False

    # 연결이 실제로 붙을 때까지 잠깐 기다린다. 명령이 끝나도 터널은 아직인 경우가 많다
    time.sleep(settings.vpn_wait_seconds)
    return True
