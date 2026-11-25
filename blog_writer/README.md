# 블로그 작업기 (초안 — 로그인까지)

네이버 블로그 자동 작성기의 바탕. 지금은 **로그인까지만** 한다.

계정·비밀번호·IP 를 이 프로그램이 들고 있지 않다. **찍고(zzikko)가 정본**이고 받아다 쓴다.

```
찍고 어드민                        이 프로그램
  블로그 프로필  (IP ↔ 크롬 프로필)  ──▶  프로필마다 크롬을 띄우고
  네이버 계정    (아이디·비번)       ──▶  아이디마다 로그인
                                   ◀──  결과 보고 (실패한 아이디는 내려간다)
```

## 구조

| 파일 | 하는 일 |
|---|---|
| `config.py` | 설정 읽기, 프로필·계정 자료 모양, 폴더 경로 규칙 |
| `zzikko.py` | 찍고 어드민 API (로그인 · 프로필 받기 · 결과 보고) |
| `browser.py` | 프로필 폴더 + 그 프로필의 IP 로 크롬 띄우기 |
| `naver_login.py` | 네이버 로그인 (기존 `n_blog_writer` 코드를 옮겨 왔다) |
| `run_login.py` | 위를 엮어 전부 돌린다 |

## 준비 (처음 한 번)

```
cd C:\project\cluade\py\blog_writer
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
copy settings.sample.json settings.json
```

`settings.json` 에 **운영진 계정**과 찍고 주소를 적는다.

`settings.json` 과 `profiles/` 는 git 에 올라가지 않는다 (`.gitignore`).

## 찍고 쪽 준비

1. 어드민 → **블로그 프로필** 에서 산 IP 를 하나씩 넣는다 (이름은 `prof-01` 처럼 영문·숫자).
2. 어드민 → **네이버 계정** 에서 각 계정의 **블로그 프로필** 칸에 그 이름을 적는다 (보통 셋).

## 실행

`.venv` 의 파이썬으로 돌린다 (시스템 파이썬에는 playwright 가 없다).

```
.venv\Scripts\python.exe run_login.py              # 프로필 전부
.venv\Scripts\python.exe run_login.py prof-01      # 그 프로필만
```

IP 가 제대로 물렸는지만 보고 싶으면:

```
.venv\Scripts\python.exe -c "import run_login; run_login.check_ip('prof-01')"
```

## 알아 둘 것

- **크롬 프로필 폴더는 아이디마다 따로다** (`profiles/prof-01/blogid1`). IP 는 프로필 단위로 같이 쓴다.
  한 폴더에 아이디 셋을 몰면 네이버가 브라우저당 한 계정만 받으므로 돌릴 때마다
  로그아웃→로그인을 반복하게 되는데, 그게 세션을 유지하는 것보다 훨씬 눈에 띈다.
- **두 번째 실행부터는 로그인을 아예 안 한다.** 폴더에 쿠키가 남아 있다.
- ⚠️ **캡차·기기 등록·2단계 인증은 프로그램이 풀지 않는다.** 뜨면 창을 열어 둔 채 멈추고
  사람을 부른다. 자동으로 뚫으려 들면 계정이 더 빨리 막힌다.
- 아이디·비밀번호가 틀렸을 때만 '실패'로 보고한다 — 그 계정은 찍고에서 **쓸 수 없음**으로
  내려가 다음 실행에서 빠진다. 되살리는 건 사람이 어드민에서 한다.
- 같은 IP 에서 계정을 연달아 로그인하지 않는다 (8~20초 사이를 둔다).
- 같은 폴더를 두 번 동시에 열면 크롬이 폴더를 잠가 두 번째가 죽는다. 한 번에 하나씩 돌린다.
- 윈도우 콘솔은 cp949 라 `—` 같은 글자가 출력에 섞이면 터진다. 화면에 찍는 문구에는
  쓰지 않고, 출력을 파일로 넘길 때를 대비해 `run_login.py` 가 stdout 을 utf-8 로 돌려 둔다.

## 아직 없는 것

글감, 원고 작성, 발행, 예약. 찍고 쪽 관리 화면(`/admin/blog`)도 지금은 프로필만 있다.
