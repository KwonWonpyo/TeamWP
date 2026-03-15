# Vercel 연결 전 최종 체크리스트 (실행형)

아래 체크를 모두 통과하면 Vercel 배포를 진행한다.

## 1) 로컬 백엔드 실행 (권장: hybrid)

```bash
ARCHITECTURE_DB_BACKEND=hybrid \
ARCHITECTURE_POSTGRES_DSN="<supabase dsn>" \
ARCHITECTURE_DB_PATH=.agent_architecture.db \
ARCHITECTURE_API_KEY="<strong-secret>" \
python3 -m uvicorn dashboard.server:app --host 127.0.0.1 --port 3010
```

Supabase 연결 실패 시 sqlite fallback이어도 서비스는 유지된다.

## 2) 프론트 로컬 연결 검증

```bash
cd dashboard-next
NEXT_PUBLIC_API_BASE=http://127.0.0.1:3010 \
NEXT_PUBLIC_WS_BASE=ws://127.0.0.1:3010 \
NEXT_PUBLIC_ARCHITECTURE_API_KEY="<strong-secret>" \
npm run dev -- --port 3001
```

## 3) 자동 사전검증 실행

```bash
BACKEND_BASE_URL=http://127.0.0.1:3010 \
ARCHITECTURE_API_KEY="<strong-secret>" \
EXPECTED_FRONTEND_ORIGIN=https://your-project.vercel.app \
FRONTEND_ENV_FILE=/workspace/dashboard-next/.env.local \
bash scripts/vercel_preflight_check.sh
```

검증 항목:

- `/api/health`, `/api/ready`, `/api/runtime/profile`, `/api/metrics`
- API key 미적용 mutation 차단(401)
- API key 적용 mutation 성공
- 프론트 `.env.local` API/WS 주소 형식 검증
- CORS에 Vercel 도메인 포함 여부 검증

## 4) Vercel 환경 변수 입력

`ops/profiles/vercel_frontend_env.example`를 참고해 Vercel 프로젝트에 입력:

- `NEXT_PUBLIC_API_BASE`
- `NEXT_PUBLIC_WS_BASE`
- `NEXT_PUBLIC_ARCHITECTURE_API_KEY`

## 5) 배포 직후 확인

- Vercel URL 접속 후 프로젝트 생성/태스크 생성/워커 실행
- Live Conversation Feed 업데이트 확인
- 백엔드 `/api/metrics`에서 `http_requests_total`, `ws_connections_total` 증가 확인

