# Prelude Opus Session Server

발연질산 누출 VR의 **세션·이벤트·이수/통계** 서버입니다. 밸브·붐·응시 판정은 Unity가 하고, 이 서버는 받은 JSON만 저장합니다.

VR 클라이언트: `seoulit-SLA/PreludeOpus-SafetyGuardians-Final`

## 로컬에서 실행

Python 3.11+ (3.14도 됩니다).

```bat
cd PreludeOpus-SafetyGuardians-SessionServer
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

브라우저: [http://127.0.0.1:8080](http://127.0.0.1:8080)  
헬스: [http://127.0.0.1:8080/health](http://127.0.0.1:8080/health)

SQLite 파일은 `data/sessions.db`에 생깁니다. 이 폴더를 복사하면 기록도 같이 이동합니다.

## Unity 연결

`Assets/SafetyGuardians/Resources/ServerSessionConfig.asset`

- `apiBaseUrl`: `http://<이 PC의 IP>:8080/v1`  
  같은 PC에서 에디터 Play면 `http://127.0.0.1:8080/v1`
- `deviceId`: 기기마다 다르게 (예: `quest-edu-03`)
- `deviceToken`: 비워 두면 로컬은 인증을 건너뜁니다. 켜려면 서버를 `DEVICE_TOKEN=...`으로 실행하고 같은 값을 넣습니다.

서버가 꺼져 있어도 VR은 로컬 JSONL로 플레이합니다. 나중에 같은 `clientSessionId`로 다시 올립니다.

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
