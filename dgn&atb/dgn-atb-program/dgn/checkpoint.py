"""last_check_time.txt 체크포인트 읽기/쓰기.

원본 dgn_scrap/func.py 에서 이 부분만 떼어왔다. func.py 는 playwright·pyautogui 등
무거운 모듈을 끌고 와서, 시트 전송만 하는 여기선 필요 없다.
"""
import os
import re
import sys
import json
from datetime import datetime

# exe 로 묶였으면 exe 옆 dgn/ 에 둔다
_BASE_DIR = (os.path.join(os.path.dirname(sys.executable), "dgn") if getattr(sys, "frozen", False)
             else os.path.dirname(os.path.abspath(__file__)))
LAST_CHECK_FILE = os.path.join(_BASE_DIR, 'last_check_time.txt')

def parse_mail_date(date_str):
    """오전/오후 HH:MM (오늘) 또는 MM.DD HH:MM (연도 없음) 형식 → datetime"""
    date_str = date_str.strip()
    now = datetime.now()
    if '오전' in date_str or '오후' in date_str:
        is_pm = '오후' in date_str
        time_part = re.sub(r'오전|오후', '', date_str).strip()
        h, m = map(int, time_part.split(':'))
        if is_pm and h != 12:
            h += 12
        elif not is_pm and h == 12:
            h = 0
        return now.replace(hour=h, minute=m, second=0, microsecond=0)
    else:
        # "07.01 20:25", "07. 01 20:25", "07/01 13:17" 형식 모두 처리
        normalized = re.sub(r'\s*[./]\s*', '/', date_str)
        parts = normalized.split()
        month, day = map(int, parts[0].split('/'))
        if len(parts) >= 2:
            h, m = map(int, parts[1].split(':'))
        else:
            h, m = 0, 0
        year = now.year
        candidate = datetime(year, month, day, h, m)
        # 파싱된 날짜가 미래면 작년 메일로 간주
        if candidate > now:
            candidate = datetime(year - 1, month, day, h, m)
        return candidate

def read_last_check_time(key='dgnmail', default='오전 11:00'):
    seed = {'dgnmail': '오전 11:00'}
    if not os.path.exists(LAST_CHECK_FILE):
        with open(LAST_CHECK_FILE, 'w', encoding='utf-8') as f:
            json.dump(seed, f, ensure_ascii=False, indent=2)
        return seed.get(key, default)
    try:
        with open(LAST_CHECK_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get(key, default)
    except json.JSONDecodeError:
        # 기존 plain text → JSON으로 마이그레이션
        with open(LAST_CHECK_FILE, 'r', encoding='utf-8') as f:
            old_value = f.read().strip()
        data = {'dgnmail': old_value}
        with open(LAST_CHECK_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data.get(key, default)

def write_last_check_time(time_str=None, key='dgnmail'):
    if time_str is None:
        now = datetime.now()
        time_str = f"{now.month:02d}.{now.day:02d} {now.hour:02d}:{now.minute:02d}"
    if os.path.exists(LAST_CHECK_FILE):
        try:
            with open(LAST_CHECK_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}
    data[key] = time_str
    with open(LAST_CHECK_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"기준 시간 저장 [{key}]: {time_str}")
