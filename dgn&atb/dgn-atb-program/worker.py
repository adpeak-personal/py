"""작업 한 개를 이 프로세스 안에서 실행한다.

실행기(main.py)가 자기 자신을 `--job <키> --log <파일> -- <인자...>` 로 다시 띄우면
여기로 온다. exe 로 묶였을 때도 파이썬 없이 같은 코드가 돈다.

창 없는 exe 는 표준출력이 없으므로, print 출력은 전부 로그 파일로 돌린다.
"""
from __future__ import annotations

import os
import sys
import traceback

from jobs import ATB_DIR, DGN_DIR


def run(argv: list[str]) -> int:
    key = argv[argv.index("--job") + 1]
    log_path = argv[argv.index("--log") + 1]
    args = argv[argv.index("--") + 1:] if "--" in argv else []

    log = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log
    try:
        if key == "dgn":
            # 개발 실행 땐 import 경로가 필요하고, exe 에선 이미 묶여 있다
            sys.path.insert(0, str(DGN_DIR))
            os.chdir(DGN_DIR)
            import daagn_api
            daagn_api.run_once()
            return 0

        sys.path.insert(0, str(ATB_DIR))
        os.chdir(ATB_DIR)
        # 정적 import 여야 PyInstaller 가 찾아서 묶는다
        if key == "trades":
            import run_trades as mod
        elif key == "geocode":
            import run_geocode as mod
        elif key == "presale":
            import run_presale as mod
        elif key == "kapt":
            import run_kapt as mod
        else:
            print(f"알 수 없는 작업: {key}")
            return 1
        return int(mod.main(args) or 0)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        log.flush()
