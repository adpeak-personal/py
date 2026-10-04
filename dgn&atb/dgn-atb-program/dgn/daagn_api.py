import os
import sys
import time
import gspread
import requests
from datetime import datetime, timezone, timedelta
from google.auth.transport.requests import Request, AuthorizedSession
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# 체크포인트(last_check_time.txt) 읽기/쓰기 — 원본 dgn_scrap/func.py 에서 이것만 떼어온 것
from checkpoint import read_last_check_time, write_last_check_time, parse_mail_date

# 1. 접근 권한 범위(Scope) 설정
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly"  # 내 드라이브 파일 목록을 읽기 위한 권한
]

# 자격증명 파일 위치. 실행 위치(CWD)와 무관하게 dgn/ 폴더로 고정.
# exe 로 묶였으면 exe 옆 dgn/ (임시 추출 폴더에 토큰을 쓰지 않도록)
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.join(os.path.dirname(sys.executable), "dgn")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 여러 계정 지원: 계정마다 OAuth 클라이언트 시크릿과 토큰 파일을 짝으로 둠
# (토큰이 곧 "로그인된 계정"이므로 계정마다 토큰 파일을 반드시 분리)
ACCOUNTS = [
    {"name": "top",  "secrets": "daggn-top.json",  "token": "token-top.json",  "route": "https://api.adpeak.kr/zapier/dgn/topby"},
    {"name": "rich", "secrets": "daggn-rich.json", "token": "token-rich.json", "route": "https://api.richby.co.kr/zapier/dgn/richby"},
    {"name": "with", "secrets": "daggn-with.json", "token": "token-with.json", "route": "https://api.withby.kr/zapier/dgn/withby"},
]

# 한국 표준시 (Drive의 UTC 시각을 현재 시간대에 맞춰 보정하기 위함)
KST = timezone(timedelta(hours=9))

# 이 키워드가 제목에 포함된 시트만 열어서 데이터를 확인
AD_KEYWORD = "[당근광고]"

def _parse_drive_time(s):
    """Drive의 UTC 시각 문자열(...Z)을 KST 기준 datetime으로 변환. 없으면 None."""
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(KST)

def load_checkpoint_time():
    """last_check_time.txt의 dgnmail 시각을 KST datetime으로 반환. 실패 시 None."""
    try:
        raw = read_last_check_time("dgnmail")  # "07.15 13:32" 또는 "오전 11:00" 등
        # parse_mail_date는 로컬(KST) 기준 naive datetime을 돌려주므로 KST 표시만 부여
        return parse_mail_date(raw).replace(tzinfo=KST)
    except Exception as e:
        print(f"체크포인트(last_check_time.txt) 로드 실패, 시간 필터 없이 진행: {e}")
        return None

def save_checkpoint_now():
    """last_check_time.txt의 dgnmail 값을 현재 시각('MM.DD HH:MM')으로 갱신."""
    write_last_check_time(key="dgnmail")  # time_str=None → 현재 시각 자동 기록

def get_credentials(account):
    """계정별 토큰/시크릿으로 인증 자격증명을 반환. 최초 1회는 브라우저 로그인."""
    secrets_path = os.path.join(BASE_DIR, account["secrets"])
    token_path = os.path.join(BASE_DIR, account["token"])

    creds = None
    # 이전에 로그인해서 발급받은 토큰이 있는지 확인
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # 저장된 토큰이 없거나 만료된 경우 재인증
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # 해당 계정의 OAuth 클라이언트 시크릿으로 로그인을 진행합니다.
            flow = InstalledAppFlow.from_client_secrets_file(
                secrets_path, SCOPES
            )
            # 로컬에서 브라우저를 열어 인증을 진행합니다 (최초 1회만 실행됨)
            creds = flow.run_local_server(port=0)

        # 다음 실행 시에는 로그인을 건너뛸 수 있도록 토큰을 파일로 저장합니다.
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return creds

def authenticate_all():
    """모든 계정의 인증을 미리 완료 (계정마다 브라우저 로그인 최초 1회)."""
    for account in ACCOUNTS:
        print(f"[{account['name']}] 계정 인증 확인 중...")
        try:
            get_credentials(account)
            print(f"[{account['name']}] 인증 완료")
        except Exception as e:
            print(f"[{account['name']}] 인증 실패: {e}")

def get_gspread_client(account=None):
    return gspread.authorize(get_credentials(account or ACCOUNTS[0]))

def list_recent_spreadsheets(creds, limit=20):
    """내가 마지막으로 열어본 순(viewedByMeTime desc)으로 스프레드시트 목록을 반환."""
    session = AuthorizedSession(creds)
    resp = session.get(
        "https://www.googleapis.com/drive/v3/files",
        params={
            "q": "mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
            "orderBy": "viewedByMeTime desc",
            "fields": "files(id,name,viewedByMeTime)",
            "pageSize": limit,
        },
    )
    if not resp.ok:
        # Google이 보내주는 상세 사유(예: Drive API 미활성 = SERVICE_DISABLED)를 그대로 노출
        raise RuntimeError(f"Drive API 오류 {resp.status_code}: {resp.text}")
    return resp.json().get("files", [])

def monitor_spreadsheets():
    """등록된 모든 계정을 순회하며 스프레드시트를 확인."""
    total_found = 0
    for account in ACCOUNTS:
        print(f"\n########## [{account['name']}] 계정 확인 ##########")
        total_found += monitor_account(account)

    # 기준 시간 이후로 검색된 스프레드시트가 하나라도 있으면 dgnmail 시각을 현재로 갱신
    if total_found > 0:
        save_checkpoint_now()

def monitor_account(account):
    """해당 계정의 스프레드시트를 확인/전송하고, 처리한 시트 개수를 반환."""
    try:
        creds = get_credentials(account)
        client = gspread.authorize(creds)

        # 1. 내가 마지막으로 열어본 순으로 스프레드시트 목록 가져오기
        print("최근 열어본 스프레드시트 목록을 불러오는 중...")
        files = list_recent_spreadsheets(creds, limit=20)

        # 제목에 [당근광고]가 포함된 시트만 대상으로 필터링
        files = [f for f in files if AD_KEYWORD in f.get("name", "")]

        # last_check_time.txt의 dgnmail 시각 이후에 열어본 것까지만 대상으로 필터링
        checkpoint = load_checkpoint_time()
        if checkpoint:
            print(f"기준 시각(dgnmail): {checkpoint.strftime('%Y-%m-%d %H:%M')} 이후만 검색")
            files = [
                f for f in files
                if (_parse_drive_time(f.get("viewedByMeTime")) or datetime.min.replace(tzinfo=KST)) >= checkpoint
            ]

        if not files:
            print("조회 가능한 스프레드시트가 없습니다.")
            return 0

        print(f"총 {len(files)}개 (내가 마지막으로 열어본 순)\n")

        # 2. 각 시트에서 데이터를 읽어 해당 사이트로 전송
        for f in files:
            viewed = _parse_drive_time(f.get("viewedByMeTime"))
            viewed_str = viewed.strftime("%Y-%m-%d %H:%M:%S") if viewed else "-"
            print(f"■ {f['name']} (열어본 시각: {viewed_str}, ID: {f['id']})")

            try:
                # ID로 시트를 열고 첫 번째 워크시트 선택
                worksheet = client.open_by_key(f['id']).get_worksheet(0)
                # 데이터가 있는 행까지 전부 읽기 (뒤쪽 빈 행은 자동으로 제외됨)
                rows = worksheet.get_all_values()

                if not rows:
                    raise ValueError("시트가 비어있음")

                # 시트마다 컬럼 순서가 다를 수 있어(이름/연락처가 뒤로 밀린 시트도 있음)
                # 헤더에서 필요한 3개 컬럼 위치를 찾아 그 순서대로 정렬해서 전송한다.
                header = rows[0]
                idx_date = header.index('응답 일시')
                idx_name = header.index('이름')
                idx_phone = header.index('연락처')

                filtered_rows = [
                    [row[idx_date], row[idx_name], row[idx_phone]] for row in rows
                ]

                print(f"  └ 데이터 {len(filtered_rows)}행:")
                for i, row in enumerate(filtered_rows, start=1):
                    print(f"     {i:>3}: {row}")

                # 시트 제목에서 [당근광고]를 뺀 텍스트를 targetText로 사용
                target_text = f['name'].replace(AD_KEYWORD, "").strip()
                route = account["route"]
                payload = {
                    "targetText": target_text,
                    "excelData": filtered_rows,
                }
                print(f"요청 URL: {route}")
                try:
                    res = requests.post(route, json=payload, timeout=10)
                    print(f"요청 완료: {res.status_code} / {res.text}")
                except Exception as req_err:
                    print(f"요청 실패: {req_err}")
            except Exception as e:
                # 권한이 뷰어로만 되어있거나 시트가 비어있는 등의 예외 처리
                print(f"  └ 데이터를 읽는 중 오류 발생: {e}")
            print("-" * 50)

        return len(files)

    except Exception as e:
        print(f"[{account['name']}] 에러 발생: {e}")
        return 0

def run_once():
    """한 번만 확인하고 끝낸다 (통합 실행기가 5분마다 부른다)."""
    print(f"=== 데이터 확인 시작 ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===")
    monitor_spreadsheets()

# --- 주기적 모니터링 실행 영역 ---
if __name__ == "__main__":
    # --once: 한 번만 확인하고 종료
    if "--once" in sys.argv:
        run_once()
        sys.exit(0)

    INTERVAL_MINUTES = 5  # 몇 분 단위로 실행할지 설정 (예: 5분)

    print("스프레드시트 모니터링을 시작합니다.")

    # 시작 전에 모든 계정 인증을 먼저 받아둔다 (계정마다 브라우저 로그인 최초 1회)
    authenticate_all()

    while True:
        print(f"\n=== 데이터 확인 시작 ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===")
        monitor_spreadsheets()
        
        print(f"\n{INTERVAL_MINUTES}분 대기 후 다시 확인합니다...")
        time.sleep(INTERVAL_MINUTES * 60)  # 초 단위로 변환하여 대기