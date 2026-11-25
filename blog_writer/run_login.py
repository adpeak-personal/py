"""로그인까지만 — 초안.

하는 일:
  1. 찍고에 운영진으로 들어가 프로필(IP) 과 계정을 받는다
  2. 프로필마다, 그 안의 아이디마다 크롬을 열고 로그인한다
  3. 결과를 찍고에 보고한다 (실패한 아이디는 '쓸 수 없음'으로 내려간다)

글쓰기·발행은 아직 없다. 여기까지가 바탕이다.

    python run_login.py                # 전부
    python run_login.py prof-01        # 그 프로필만
"""
from __future__ import annotations

import random
import sys
import time

from browser import current_ip, launch
from config import Account, Profile, Settings
from naver_login import FAILED, NEED_HUMAN, OK, login
from zzikko import Zzikko, ZzikkoError

# 아이디 사이에 쉬는 시간. 같은 IP 에서 쉼 없이 셋을 연달아 로그인하지 않는다
PAUSE_RANGE = (8, 20)


def run_account(profile: Profile, account: Account, settings: Settings, api: Zzikko) -> str:
    with launch(profile, account, headless=settings.headless) as context:
        result = login(context, account)

        if result == NEED_HUMAN:
            # 창을 띄워 둔 채 사람이 풀 때까지 기다린다. 자동으로 뚫지 않는다.
            input("     → 창에서 확인을 마친 뒤 Enter 를 누르세요 (건너뛰려면 그냥 Enter): ")
            page = context.pages[0] if context.pages else None
            if page is not None:
                from naver_login import logged_in

                result = OK if logged_in(page, timeout=5) else NEED_HUMAN

        # 사람 확인이 필요했던 건 '실패'로 적지 않는다 — 아이디가 막힌 게 아니다
        if result in (OK, FAILED):
            try:
                api.report_login(account, ok=(result == OK), profile=profile.name)
            except ZzikkoError as error:
                print(f"     보고 실패: {error}")
        return result


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        settings = Settings.load()
    except (FileNotFoundError, ValueError) as error:
        print(error)
        return 1

    api = Zzikko(settings)
    try:
        api.login()
        profiles = api.profiles(only)
    except ZzikkoError as error:
        print(error)
        return 1

    if not profiles:
        print("돌릴 프로필이 없습니다. 찍고 어드민 → 블로그 프로필에서 추가해 주세요.")
        return 1

    tally = {OK: 0, FAILED: 0, NEED_HUMAN: 0}

    for profile in profiles:
        print(f"\n[{profile.name}] 계정 {len(profile.accounts)}개"
              f"{' · IP ' + profile.proxy_host if profile.proxy_host else ' · 직접 연결'}")
        if not profile.accounts:
            print("  붙은 계정이 없습니다 (네이버 계정 화면에서 프로필 이름을 적어주세요)")
            continue

        for index, account in enumerate(profile.accounts):
            if index:
                pause = random.uniform(*PAUSE_RANGE)
                print(f"  {pause:.0f}초 쉬는 중…")
                time.sleep(pause)

            try:
                result = run_account(profile, account, settings, api)
            except Exception as error:  # 한 계정이 넘어져도 나머지는 돌린다
                print(f"  {account.login_id}: 열지 못했습니다 — {type(error).__name__}: {error}")
                result = FAILED
            tally[result] = tally.get(result, 0) + 1

    print(f"\n끝났습니다 — 성공 {tally[OK]} · 실패 {tally[FAILED]} · 사람 확인 필요 {tally[NEED_HUMAN]}")
    return 0


def check_ip(profile_name: str) -> None:
    """프록시가 제대로 물렸는지만 보고 싶을 때: python -c "import run_login; run_login.check_ip('prof-01')" """
    settings = Settings.load()
    api = Zzikko(settings)
    api.login()
    profiles = api.profiles(profile_name)
    if not profiles:
        print(f"프로필 {profile_name} 을 찾지 못했습니다")
        return
    profile = profiles[0]
    probe = profile.accounts[0] if profile.accounts else Account(id=0, login_id="_ip_check", password="")
    with launch(profile, probe, headless=True) as context:
        print(f"{profile.name} → {current_ip(context)}")


if __name__ == "__main__":
    raise SystemExit(main())
