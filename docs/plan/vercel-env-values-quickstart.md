# Vercel 연결용 환경변수 값 정리 (복붙용)

아래 값만 맞추면, Vercel 연결/세팅 후 바로 실행 가능하다.

## 1) 로컬 백엔드(.env) 값

> 백엔드는 로컬 PC에서 24시간 실행, DB는 hybrid 모드( Supabase 우선 + SQLite fallback )

```bash
# 필수
OPENAI_API_KEY=<your_openai_key>
ARCHITECTURE_API_KEY=<strong_secret_same_as_vercel>

# DB (hybrid)
ARCHITECTURE_DB_BACKEND=hybrid
ARCHITECTURE_POSTGRES_DSN=postgresql://<user>:<password>@<supabase-host>:5432/postgres
ARCHITECTURE_DB_PATH=.agent_architecture.db

# Queue (초기 로컬)
ARCHITECTURE_QUEUE_BACKEND=local
# ARCHITECTURE_REDIS_URL=redis://127.0.0.1:6379/0

# CORS (반드시 Vercel 도메인 포함)
ARCHITECTURE_CORS_ORIGINS=http://127.0.0.1:3001,http://localhost:3001,https://<your-project>.vercel.app

# Worker 튜닝(선택)
WORKER_POLL_INTERVAL_SECONDS=0.5
WORKER_DEQUEUE_TIMEOUT_SECONDS=1
```

백엔드 실행:

```bash
python3 -m uvicorn dashboard.server:app --host 0.0.0.0 --port 3010
```

## 2) Vercel 프로젝트 환경변수 값

Vercel → Project Settings → Environment Variables

```bash
NEXT_PUBLIC_API_BASE=https://<your-backend-public-domain>
NEXT_PUBLIC_WS_BASE=wss://<your-backend-public-domain>
NEXT_PUBLIC_ARCHITECTURE_API_KEY=<strong_secret_same_as_backend>
```

중요:

- `NEXT_PUBLIC_ARCHITECTURE_API_KEY` 값은 로컬 백엔드의 `ARCHITECTURE_API_KEY`와 동일해야 한다.
- `NEXT_PUBLIC_API_BASE`/`NEXT_PUBLIC_WS_BASE`는 브라우저에서 접근 가능한 백엔드 공개 도메인(터널 포함)이어야 한다.

## 3) 연결 전 자동 점검 (권장)

```bash
BACKEND_BASE_URL=http://127.0.0.1:3010 \
ARCHITECTURE_API_KEY=<strong_secret_same_as_backend> \
EXPECTED_FRONTEND_ORIGIN=https://<your-project>.vercel.app \
FRONTEND_ENV_FILE=/workspace/dashboard-next/.env.local \
bash scripts/vercel_preflight_check.sh
```

모든 단계가 통과하면 Vercel 연결 준비 완료.

