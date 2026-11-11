# 수집기를 새 노트북에 올리기

통합 실행기(`dgn-atb`)는 당근광고와 부동산 수집을 한 창에서 돌린다. 노트북이
켜져 있고 인터넷만 되면 된다 — 웹 서버와는 무관하다.

부동산 수집은 **DB 서버(158.247.244.167)의 MySQL** 에 직접 쓴다. 집 인터넷은 IP 가
바뀌어 방화벽에 고정할 수 없고, 3306 을 인터넷에 열면 여러 프로젝트가 같이 쓰는
DB 서버가 통째로 공격 대상이 되므로 **SSH 터널**로 붙는다.

```
노트북 ──SSH(22)──> DB 서버 ──> MySQL(3306)
       127.0.0.1:3307 로 붙으면 서버 MySQL 로 연결된다
```

실행기가 터널을 직접 열고 유지한다. 따로 띄울 것은 없다.

---

## 1. 노트북 준비

- **Python 3.11 이상** — 설치할 때 "Add Python to PATH" 체크
- **Git**
- **OpenSSH 클라이언트** — 윈도우 10/11 기본 포함 (`ssh -V` 로 확인)

## 2. 코드 받기

```powershell
git clone https://github.com/adpeak-personal/py.git C:\project\py
cd "C:\project\py\dgn&atb\dgn-atb-program"
.\setup.bat
```

폴더 이름에 `&` 가 들어 있다. PowerShell 에서 `&` 는 특수문자라 **경로를 반드시
따옴표로 묶는다** (`cd "...dgn&atb..."`). 안 묶으면 `'atb' 용어가 인식되지 않습니다`
가 뜬다.

`setup.bat` 이 `.venv` 를 만들고 `requirements.txt` 를 설치한다.

## 3. SSH 키 만들고 등록 ★ 여기서 두 번 막혔다

노트북에서:

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\atb_tunnel" -C "laptop-dgn-atb" -N '""'
ssh-keygen -y -f "$env:USERPROFILE\.ssh\atb_tunnel"
```

둘째 줄은 **개인키를 직접 읽어** 공개키를 뽑는다. 암호가 걸려 있으면
`Enter passphrase:` 를 묻는다. **암호가 걸리면 안 된다** — 터널은 `BatchMode=yes` 로
붙어서 암호를 물어볼 수 없다. 물어보면 암호 없이 다시 만든다.
(`-N '""'` 는 PowerShell 에서 빈 암호를 넘기는 관용구다.)

출력된 줄을 **DB 서버** `~/.ssh/authorized_keys` 에 넣는다:

```bash
echo 'restrict,port-forwarding,permitopen="127.0.0.1:3306" ssh-ed25519 AAAA... laptop-dgn-atb' >> ~/.ssh/authorized_keys && tail -1 ~/.ssh/authorized_keys | ssh-keygen -lf -
```

앞의 옵션 세 개를 **그대로** 써야 한다:

| 옵션 | 뜻 |
|---|---|
| `restrict` | 쉘·에이전트·X11·**포트포워딩까지 전부** 막는다 |
| `port-forwarding` | 그중 포트포워딩만 다시 켠다 ← **빠뜨리면 안 된다** |
| `permitopen="127.0.0.1:3306"` | 포워딩 대상을 MySQL 한 곳으로 좁힌다 |

`restrict,permitopen=...` 만 쓰면 **인증은 되는데 데이터가 안 지나간다.** 터널이
열린 것처럼 보여서 알아채기 어렵고, 실제로 하루를 날렸다. 서버 로그에
`refused local port forward` 가 찍힌다.

이렇게 묶어두면 노트북을 잃어버려도 그 키로는 **MySQL 터널만** 되고 서버 쉘은
열리지 않는다.

## 4. 터널이 실제로 통하는지 확인 ★

**창이 멈춰 있는 것만으로는 확인이 안 된다.** 로컬 포워딩(`-L`)은 접속할 때가
아니라 데이터가 지나갈 때 거부되므로, `ssh -N` 은 거부돼도 가만히 있는다.
`ExitOnForwardFailure` 도 이건 못 잡는다.

한 창에서 터널을 띄우고:

```powershell
ssh -i "$env:USERPROFILE\.ssh\atb_tunnel" -o BatchMode=yes -o StrictHostKeyChecking=accept-new -N -L 3307:127.0.0.1:3306 root@158.247.244.167
```

**다른 창에서** 바이트를 읽어 본다. MySQL 은 붙는 즉시 인사 패킷을 보낸다:

```powershell
$c = New-Object Net.Sockets.TcpClient('127.0.0.1',3307); $s = $c.GetStream(); $s.ReadTimeout = 3000; $b = New-Object byte[] 80; $n = $s.Read($b,0,80); "읽은 바이트: $n"; if ($n -gt 5) { "MySQL 응답: " + [Text.Encoding]::ASCII.GetString($b[5..($n-1)]) }; $c.Close()
```

- `읽은 바이트: 70` 쯤 + `MySQL 응답: 8.0.xx` → **정상**
- `읽은 바이트: 0` → 포워딩이 거부되는 상태. 3번의 `port-forwarding` 을 확인한다

확인했으면 `Ctrl+C` 로 터널을 끊는다 (실행기가 자기 걸 따로 연다).

## 5. `atb\.env` 만들기

`atb\.env.example` 을 복사해 채운다. **키 값들은 기존 기계의 `.env` 에서 그대로
복사**한다 (저장소에는 없다).

```
DATA_AUTH_KEY=공공데이터포털 인증키
JUSO_SEARCH_KEY=주소검색 승인키
JUSO_COORD_KEY=좌표제공 승인키

# 터널로 붙으므로 127.0.0.1 이고, 포트가 3307 인 것에 주의
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_USER=atb
MYSQL_PASSWORD=DB 서버에서 만든 비밀번호
MYSQL_DATABASE=atb_db

SSH_HOST=158.247.244.167
SSH_USER=root
SSH_LOCAL_PORT=3307
SSH_KEY=C:\Users\사용자명\.ssh\atb_tunnel
```

**`SSH_KEY` 를 꼭 적는다.** `atb_tunnel` 은 ssh 가 기본으로 찾는 이름이 아니라서
경로를 알려주지 않으면 그 키를 쓰지 않는다. 그러면 내놓을 키가 없어 서버 로그에
`Connection reset by authenticating user root [preauth]` 가 1분마다 쌓인다.

`DATA_AUTH_KEY` 가 비어 있으면 모든 수집이 **코드 1** 로 떨어진다.
당근 쪽 비밀값(`dgn\daggn-*.json`, `dgn\token-*.json`)도 같이 옮긴다.

## 6. 실행

```powershell
.\start.bat
```

파이썬이 없는 기계에 쓰려면 `build.bat` 으로 `dist\dgn-atb\` 를 만들어
그 폴더째 옮기고 `dgn-atb.exe` 를 띄운다. **폴더를 통째로 덮지 않는다** —
`atb\.env`, `dgn\token-*.json`, `logs\state.json` 이 날아간다. 프로그램 파일
(`dgn-atb.exe`, `_internal\`)만 바꾼다.

exe 로 쓰는 경우 `git pull` 만으로는 반영되지 않는다. **`build.bat` 을 다시
돌려야** 한다.

## 7. 노트북 설정

- **절전 끄기** — 설정 > 시스템 > 전원 > 화면·절전 → "안 함"
- **덮개를 닫아도 안 꺼지게** — 제어판 > 전원 옵션 > 덮개를 닫을 때 → "아무 것도 안 함"
- **자동 로그인** — 재부팅 후 로그인 상태여야 실행기가 뜬다

실행기가 떠 있는 동안은 프로그램이 절전을 막는다(`SetThreadExecutionState`).
하지만 실행기가 꺼져 있으면 아무것도 안 돈다.

## 8. 기존 기계 정리 ★

**빠뜨리면 같은 수집이 두 곳에서 돌아 공공 API 하루 한도를 두 배로 쓴다.**

- 기존 노트북에서 실행기를 **종료**한다 (창을 닫고 "확인")
- 예전 방식(작업 스케줄러)으로 등록해 둔 기계면
  `all_that_realestate\atb-program\scheduler\unregister_tasks.bat` 도 돌린다.
  실행기가 뜰 때 남아 있으면 경고로 알려준다.
- 기존 노트북을 더 안 쓰면 DB 서버에서 그 키를 지운다:
  `sed -i '/옛키주석$/d' ~/.ssh/authorized_keys`

---

## 도는 작업

| 시점 | 작업 | 범위 |
|---|---|---|
| 5분마다 | 당근광고 시트 → 서버 | |
| 02:00 | 아파트 전월세 | 최근 3개월 |
| 02:40 | 오피스텔 전월세 | 최근 3개월 |
| 03:00 | 아파트 실거래가 | 최근 3개월 |
| 03:40 | 오피스텔 실거래가 | 최근 3개월 |
| 04:00 | 단지 좌표 | 좌표 없는 단지 + 오류 재시도 |
| 06:00 | 청약홈 분양공고 | 최신 |
| 09:00 | K-apt 단지 동기화 | 전국 (새벽엔 포털이 막혀 낮에) |

"최근 3개월" 은 `jobs.py` 의 `RECENT_MONTHS` 다. 실거래·전월세 신고 기한이 계약
후 30일이고 공개까지 더 걸려서, 2개월로 뒀다가 월초에 전전달이 창에서 빠지며
지연 신고를 영구히 놓쳤다.

노트북이 예약 시각에 꺼져 있었으면 켠 뒤 바로 따라잡는다. `logs\state.json` 이
"오늘 돌았는지"를 들고 있어서, 재시작해도 이미 돈 작업은 다시 돌지 않는다.

## 한 번만 해야 하는 것 — 전월세 과거분

매일 도는 작업은 최근 3개월만 본다. 그 이전은 한 번 받아야 한다 (며칠 걸리고,
오래된 달부터 오름차순으로 돌며 저장이 멱등해서 끊겨도 다시 돌리면 이어진다):

```powershell
.venv\Scripts\python atb\run_rents.py --all --recent
.venv\Scripts\python atb\run_rents.py --type=OFFI --all --recent
```

`--years=1` 처럼 기간을 줄일 수 있다 (기본 3년).

## 확인

실행기 화면의 작업별 상태를 본다. 그리고 하루 뒤:

- `logs\` 의 그날 로그 — `종료 (코드 0)` 이면 성공, `코드 2` 는 API 일일 한도
  (정상, 다음 날 이어서), **`코드 1` 은 실패**
- 사이트 어드민(`https://atb.co.kr/admin`)의 **수집 상태** 카드
- 로그 창에 `⚠` 경고가 있으면 그게 먼저다

### 자주 나오는 실패

| 증상 | 원인 |
|---|---|
| 상태가 `-` 로 비어 있고 조용함 | 터널이 안 붙음. 작업은 시작 기록도 안 남기고 넘어간다. `logs\ssh-tunnel.log` 를 본다 |
| 전부 `실패 (코드 1)`, 로그에 `Lost connection to MySQL server during query` | 터널은 붙었는데 포워딩이 거부됨 → 3번의 `port-forwarding` |
| 전부 `실패 (코드 1)`, 로그에 `DATA_AUTH_KEY 가 설정되지 않았습니다` | `.env` 가 없거나 키가 빈 값 |
| 서버 로그에 `[preauth]` 가 1분마다 | 내놓을 키가 없음 → `.env` 의 `SSH_KEY` 경로 |
| 월·화에 적재량이 바닥 | **정상이다.** 국토교통부가 공개를 수요일에 몰아 올린다 |
