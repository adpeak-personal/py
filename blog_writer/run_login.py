"""로그인까지 — IP 를 먼저 확인하고 돌린다.

흐름:
  1. 찍고에서 프로필(기대 IP) 과 계정을 받는다
  2. 브라우저로 **지금 밖에서 보이는 IP** 를 잰다
  3. 그 IP 가 기대 IP 인 프로필을 찾는다 — 없으면 멈춘다
  4. 그 프로필의 아이디를 차례로 로그인한다 (아이디마다 IP 를 다시 잰다)
  5. 다음 프로필 차례가 되면 VPN 을 바꾸라고 하고 기다린다

⚠️ **IP 가 맞지 않으면 로그인하지 않는다.** 엉뚱한 IP 로 한 번 로그인하면 그 계정이
   그 IP 에 묶여 버린다. 틀린 채로 도는 것보다 멈추는 게 낫다.

    python run_login.py                # 프로필 전부 (하나씩, VPN 바꿔 가며)
    python run_login.py prof-01        # 그 프로필만
    python run_login.py prof-01 --shot # 성공해도 화면을 shots/ 에 남긴다
    python run_login.py prof-01 --no-keep  # 안 멈추고 줄줄이 돌린다
"""
from __future__ import annotations

import random
import sys
import threading
import time

# 윈도우 콘솔은 cp949 다. 출력을 파일로 넘기면 한글·기호에서 터지므로 미리 막아 둔다
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from browser import launch, measure_ip, save_shot
import shutil

from config import PROFILE_ROOT, Account, Profile, Settings
from naver_login import FAILED, NEED_HUMAN, OK, login, logged_in
from vpn import switch_vpn
from zzikko import Zzikko, ZzikkoError

# 아이디 사이에 쉬는 시간. 같은 IP 에서 쉼 없이 셋을 연달아 로그인하지 않는다
PAUSE_RANGE = (8, 20)

# ── 바깥에서 갈아끼우는 고리 ──────────────────────────────
# 터미널에서는 그대로 print/input 이고, GUI(`gui.py`)는 자기 것으로 바꿔 끼운다.
# 작업 코드가 화면을 모르게 두려고 이렇게 했다.
say = print
ask = input
#: 중지 버튼용. GUI 가 넣어 주면 틈틈이 들여다본다
stop_flag: "threading.Event | None" = None


def stopped() -> bool:
    """중지를 눌렀는지. 긴 작업 사이사이에서 본다."""
    return stop_flag is not None and stop_flag.is_set()


def nap(seconds: float) -> None:
    """쉬되, 중지를 누르면 곧바로 깬다."""
    if stop_flag is None:
        time.sleep(seconds)
        return
    stop_flag.wait(seconds)


def current_ip(profile: Profile, settings: Settings) -> str | None:
    """지금 밖에서 보이는 IP. 프로필의 프록시 설정을 그대로 태워서 잰다."""
    probe = Account(id=0, login_id="_ip", password="")
    say("  IP 를 재는 중... (크롬을 잠깐 띄웁니다. 창은 안 보입니다)")
    try:
        with launch(profile, probe, headless=True) as context:
            return measure_ip(context)
    except Exception as error:
        say(f"  IP 를 재지 못했습니다. {type(error).__name__}: {error}")
        return None


def hold(label: str) -> None:
    """작업을 멈추고 **창을 띄워** 기다린다.

    로그인이 끝난 화면을 눈으로 보라고 두는 자리다. 터미널에서는 `pyautogui.alert`,
    화면(`gui.py`)에서는 그쪽 창이 뜬다 — 어느 쪽이든 확인을 눌러야 다음으로 간다.

    ⚠️ Ctrl+C 로 기다리게 하지 않는다. GUI 에는 Ctrl+C 가 없고, 터미널에서도
    "멈춘 건지 기다리는 건지" 구분이 안 됐다.
    """
    say("     ---------------------------------------------------")
    say(f"     {label} 창을 열어 둡니다. 눈으로 확인하세요.")
    say("     확인을 누르면 창을 닫고 다음으로 갑니다.")
    say("     ---------------------------------------------------")

    if stop_flag is not None:
        # 화면에서 돌 때는 GUI 가 끼워 준 물음 창이 뜬다
        ask(f"{label} 창을 다 보셨으면 확인을 누르세요")
    else:
        try:
            import pyautogui

            pyautogui.alert(
                text=f"{label} 로그인 화면을 확인하세요." + chr(10) + "확인을 누르면 창을 닫습니다.",
                title="블로그 작업기",
            )
        except Exception:
            # 창을 못 띄우면 터미널로 묻는다
            ask("     확인을 마쳤으면 Enter: ")
    say("     창을 닫습니다")


def run_account(
    profile: Profile, account: Account, settings: Settings, api: Zzikko, shot: bool = False, keep: bool = True
) -> str:
    say(f"  {account.login_id}: 크롬 창을 엽니다...")
    with launch(profile, account, headless=settings.headless) as context:
        # 작업 직전에 한 번 더 확인한다 — 도중에 VPN 이 끊기면 사무실 IP 로 글을 쓰게 된다
        seen = measure_ip(context)
        if profile.expected_ip and seen != profile.expected_ip:
            say(f"  {account.login_id}: IP 가 {seen} 로 바뀌었습니다. 건너뜁니다")
            return NEED_HUMAN

        result = login(context, account, log=say)

        # 막힌 자리는 사진으로 남긴다 — 글자만으로는 캡차인지 기기등록인지 모른다
        if shot or result != OK:
            path = save_shot(context, f"{account.login_id}-{result}")
            if path:
                say(f"     화면을 남겼습니다: {path}")

        if result == NEED_HUMAN:
            # 창을 띄워 둔 채 사람이 풀 때까지 기다린다. 자동으로 뚫지 않는다.
            say("     ---------------------------------------------------")
            say("     크롬 창에서 직접 확인을 끝내 주세요 (창이 뒤에 숨어 있을 수 있습니다)")
            say("     프로그램은 여기서 사장님을 기다립니다. 멈춘 게 아닙니다.")
            say("     ---------------------------------------------------")
            ask("     끝나면 Enter (건너뛰려면 그냥 Enter): ")
            page = context.pages[0] if context.pages else None
            result = OK if page is not None and logged_in(page, timeout=5) else NEED_HUMAN
            after = save_shot(context, f"{account.login_id}-after")
            if after:
                say(f"     확인 뒤 화면: {after}")

        # 사람 확인이 필요했던 건 '실패'로 적지 않는다 — 아이디가 막힌 게 아니다
        if result in (OK, FAILED):
            try:
                api.report_login(account, ok=(result == OK), profile=profile.name)
            except ZzikkoError as error:
                say(f"     보고 실패: {error}")

        if keep:
            hold(account.login_id)
        return result


def run_profile(
    profile: Profile, settings: Settings, api: Zzikko, tally: dict[str, int], shot: bool = False, keep: bool = True
) -> None:
    say("")
    say(f"[{profile.name}] 아이디 {len(profile.accounts)}개")
    if not profile.accounts:
        # 찍고가 쓸 수 있는 계정만 내려주므로, 여기서는 두 경우를 구분할 수 없다
        say("  돌릴 아이디가 없습니다")
        say("     - 네이버 계정 화면에서 블로그 프로필 칸에 이 이름을 적었는지")
        say("     - 그 아이디가 '사용 불가' 로 꺼져 있지는 않은지")
        return
    if len(profile.accounts) > 1:
        # 프로필 하나에 아이디 하나가 원칙이다. 어긋났으면 알리고 그대로 돈다
        say("  !! 아이디가 여러 개 붙어 있습니다. 어드민에서 하나만 남겨주세요")

    # ── VPN 을 이 프로필 자리로 옮긴다 (자동이면 명령으로, 아니면 사람에게 부탁)
    switch_vpn(profile, settings)

    seen = current_ip(profile, settings)
    if seen is None:
        return

    if not profile.expected_ip:
        # 처음이면 지금 IP 를 그 프로필의 것으로 적어 둔다 (손으로 적다 오타 나는 걸 막는다)
        say(f"  지금 IP {seen} 를 이 프로필의 IP 로 기록합니다")
        try:
            api.record_ip(profile, seen)
        except ZzikkoError as error:
            say(f"  기록 실패: {error}")
        profile.expected_ip = seen
    elif seen != profile.expected_ip:
        say(f"  !! IP 가 맞지 않습니다, 지금 {seen} / 이 프로필은 {profile.expected_ip}")
        say("     VPN 을 이 프로필 자리로 바꾸고 다시 돌려주세요. 로그인하지 않습니다.")
        return
    else:
        say(f"  IP 확인 {seen}")

    for index, account in enumerate(profile.accounts):
        if index:
            pause = random.uniform(*PAUSE_RANGE)
            say(f"  {pause:.0f}초 쉬는 중...")
            nap(pause)
        if stopped():
            say("  중지했습니다")
            return
        try:
            result = run_account(profile, account, settings, api, shot, keep)
        except Exception as error:  # 한 계정이 넘어져도 나머지는 돌린다
            say(f"  {account.login_id}: 열지 못했습니다. {type(error).__name__}: {error}")
            result = FAILED
        tally[result] = tally.get(result, 0) + 1


def clean_pending(api: Zzikko) -> None:
    """찍고에서 '삭제' 로 표시한 프로필을 치운다.

    **폴더를 먼저 지우고 행을 지운다.** 순서가 바뀌면 표시가 사라져서 폴더가 영영 남는다
    (그 안에 로그인된 쿠키가 들어 있다). 폴더를 못 지우면 행도 두고 다음 번에 다시 시도한다.
    """
    try:
        pending = api.pending_delete()
    except ZzikkoError as error:
        say(f"치울 목록을 받지 못했습니다: {error}")
        return
    if not pending:
        return

    say(f"지우기로 표시된 프로필 {len(pending)}개를 치웁니다")
    for profile_id, name in pending:
        folder = PROFILE_ROOT / name
        try:
            if folder.exists():
                shutil.rmtree(folder)
                say(f"  {name}: 폴더 지움")
            else:
                say(f"  {name}: 폴더가 없습니다 (이 PC 에서 안 돌린 프로필)")
        except Exception as error:
            # 크롬이 떠 있으면 폴더가 잠겨 있다. 행을 남겨 다음 번에 다시 한다
            say(f"  {name}: 폴더를 지우지 못했습니다. {type(error).__name__}: {error}")
            continue
        try:
            api.delete_profile(profile_id)
            say(f"  {name}: 목록에서 지움")
        except ZzikkoError as error:
            say(f"  {name}: 목록에서 지우지 못했습니다. {error}")


def run(only: str | None = None, shot: bool = False, keep: bool = True) -> int:
    """실제로 도는 몸통. 터미널(`main`)과 화면(`gui.py`)이 같이 쓴다."""

    try:
        settings = Settings.load()
    except (FileNotFoundError, ValueError) as error:
        say(error)
        return 1

    api = Zzikko(settings)
    try:
        api.login()
    except ZzikkoError as error:
        say(error)
        return 1

    # 돌리기 전에 치운다 — 지울 프로필로 로그인하는 일이 없게
    clean_pending(api)

    try:
        profiles = api.profiles(only)
    except ZzikkoError as error:
        say(error)
        return 1

    if not profiles:
        say("돌릴 프로필이 없습니다. 찍고 어드민 > 블로그 프로필에서 추가해 주세요.")
        return 1

    if keep and settings.headless:
        # 창이 안 뜨는데 붙잡아 봐야 볼 것이 없다
        say("settings.json 의 headless 가 true 라 창이 뜨지 않습니다. false 로 바꿔 주세요.")
        return 1

    tally = {OK: 0, FAILED: 0, NEED_HUMAN: 0}
    for index, profile in enumerate(profiles):
        if stopped():
            say("중지했습니다")
            break
        run_profile(profile, settings, api, tally, shot, keep)
        if index < len(profiles) - 1 and not settings.vpn_command:
            nxt = profiles[index + 1]
            # 다음 프로필이 **같은 IP** 면 VPN 을 그대로 둬도 된다 (목록이 IP 순으로 온다)
            if nxt.expected_ip and nxt.expected_ip == profile.expected_ip:
                say(f"  다음 [{nxt.name}] 도 같은 IP 입니다. VPN 그대로 이어갑니다")
                continue
            where = f" ({nxt.vpn_location})" if nxt.vpn_location else ""
            say("")
            answer = ask(f"다음은 [{nxt.name}]{where} 입니다. VPN 을 바꾸고 Enter (그만두려면 q): ")
            if answer.strip().lower() == "q":
                break

    say(f"\n끝났습니다. 성공 {tally[OK]} · 실패 {tally[FAILED]} · 사람 확인 필요 {tally[NEED_HUMAN]}")
    return 0


def main() -> int:
    """터미널에서 들어오는 자리. 옵션만 읽어 `run` 에 넘긴다."""
    options = {"--shot", "--keep", "--no-keep"}
    args = [a for a in sys.argv[1:] if a not in options]
    return run(
        only=args[0] if args else None,
        # --shot 을 붙이면 성공했을 때도 화면을 남긴다 (문제를 같이 들여다볼 때)
        shot="--shot" in sys.argv,
        # 로그인이 끝나면 창을 띄워 기다린다. 줄줄이 돌리고 싶으면 --no-keep
        keep="--no-keep" not in sys.argv,
    )


def check_ip(profile_name: str) -> None:
    """프록시·VPN 이 제대로 물렸는지만 본다.

    python -c "import run_login; run_login.check_ip('prof-01')"
    """
    settings = Settings.load()
    api = Zzikko(settings)
    api.login()
    profiles = api.profiles(profile_name)
    if not profiles:
        say(f"프로필 {profile_name} 을 찾지 못했습니다")
        return
    profile = profiles[0]
    seen = current_ip(profile, settings)
    expected = profile.expected_ip or "(아직 없음)"
    mark = "" if not profile.expected_ip else (" 맞음" if seen == profile.expected_ip else " 다름!")
    say(f"{profile.name}: 지금 {seen} / 기대 {expected}{mark}")


if __name__ == "__main__":
    raise SystemExit(main())
