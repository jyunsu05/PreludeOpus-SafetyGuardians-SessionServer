# Prelude Opus Session Server

발연질산 누출 VR의 **세션·이벤트·이수/통계** 서버입니다. 밸브·붐·응시 판정은 Unity가 하고, 이 서버는 받은 JSON만 저장합니다.

- 이 레포: [github.com/jyunsu05/PreludeOpus-SafetyGuardians-SessionServer](https://github.com/jyunsu05/PreludeOpus-SafetyGuardians-SessionServer)
- VR 클라이언트: [seoulit-SLA/PreludeOpus-SafetyGuardians-Final](https://github.com/seoulit-SLA/PreludeOpus-SafetyGuardians-Final)

## Windows에서 쓰기

Python 3.11+ 가 한 번만 있으면 됩니다. [python.org](https://www.python.org/downloads/) 설치 때 **Add python.exe to PATH** 를 체크하세요.

1. GitHub에서 **Code → Download ZIP**
2. 압축을 푼다
3. **`start.bat` 을 더블클릭**한다

서버가 켜지고, 잠시 후 브라우저가 [http://127.0.0.1:8080](http://127.0.0.1:8080) 으로 열립니다.  
`sessions.db` 는 없을 때 `data` 폴더에 자동으로 만들어집니다. 이 창을 닫으면 서버가 꺼집니다.

이미 켜져 있으면 `start.bat` 을 다시 눌러도 서버를 또 켜지 않고 브라우저만 엽니다. `대시보드.url` 도 같은 화면입니다.

## 기록 백업

세션 DB는 GitHub에서 받아 오지 않습니다. **`data` 폴더만 복사**하면 기록이 그대로 옮겨집니다.

- 파일: `data/sessions.db` (처음 실행 때 자동 생성)
- 백업: `backup.bat` 을 더블클릭하면 `backups\data-날짜시간` 으로 복사됩니다
- 또는 `data` 폴더를 USB나 다른 디스크에 복사
- 복원: 복사해 둔 `data` 를 이 프로그램 폴더에 다시 넣기

`.venv` 는 백업하지 마세요. 패키지 캐시입니다.

## Unity 연결

`Assets/SafetyGuardians/Resources/ServerSessionConfig.asset`

- `apiBaseUrl` 이 비어 있어도, 이 서버가 켜져 있으면 Play 때 `http://127.0.0.1:8080/v1` 로 자동 연결됩니다
- 같은 PC가 아니면 `http://<이 PC의 IP>:8080/v1`
- `deviceId`: 기기마다 다르게 (예: `quest-edu-03`)
- `deviceToken`: 비워 두면 로컬은 인증을 건너뜁니다

서버가 꺼져 있어도 VR은 로컬 JSONL로 플레이합니다.

## 직접 명령으로 실행

```bat
cd PreludeOpus-SafetyGuardians-SessionServer
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

헬스: [http://127.0.0.1:8080/health](http://127.0.0.1:8080/health)

## VR이 보내는 API

| 메서드 | 경로 |
|--------|------|
| POST | `/v1/sessions` |
| POST | `/v1/sessions/{id}/events` |
| POST | `/v1/sessions/{id}/complete` |

같은 `clientSessionId` / `batchSeq` / complete는 멱등입니다.

## 대시보드에서 파일 받기

- 교육/체험 CSV: `/v1/export/sessions.csv`
- 세션 원문 JSONL: `/v1/sessions/{id}/events.jsonl`

## Docker (선택)

```bat
docker build -t preludeopus-session-server .
docker run --rm -p 8080:8080 -v %cd%\data:/app/data preludeopus-session-server
```
