# Vercel + Local Backend + Supabase/SQLite 하이브리드 런북

목표: 오버스펙(AWS/K8s) 없이 빠르게 운영 가능한 형태를 기본 운영안으로 사용한다.

## 운영 원칙

1. Frontend는 Vercel 배포 (`dashboard-next`)
2. Backend/Worker는 로컬 PC에서 24시간 구동
3. DB는 Postgres(Supabase) 우선, 장애 시 SQLite fallback
4. Queue는 초기 `local`, 병렬/부하 증가 시 `redis`로 전환

## 환경 변수 프로파일

`ops/profiles/vercel_local_backend_hybrid.env.example`를 `.env`로 복사해서 사용한다.

핵심 값:

- `ARCHITECTURE_DB_BACKEND=hybrid`
- `ARCHITECTURE_POSTGRES_DSN=<supabase postgres dsn>`
- `ARCHITECTURE_DB_PATH=.agent_architecture.db`
- `ARCHITECTURE_QUEUE_BACKEND=local`
- `ARCHITECTURE_API_KEY=<strong secret>`

## 로컬 백엔드 24시간 실행

```bash
bash scripts/run_backend_local_24h.sh
```

로그: `./logs/backend.log`

## 런타임 상태 점검

```bash
bash scripts/smoke_runtime_profile.sh
```

확인 포인트:

- `/api/runtime/profile`의 `db.active_backend`
- `/api/ready`의 `ok` 값
- `/api/metrics` 카운터 증가

## Vercel 설정

Vercel 환경 변수(프로젝트 Settings → Environment Variables):

- `NEXT_PUBLIC_API_BASE=https://<your-backend-domain-or-tunnel>`
- `NEXT_PUBLIC_WS_BASE=wss://<your-backend-domain-or-tunnel>`
- `NEXT_PUBLIC_ARCHITECTURE_API_KEY=<ARCHITECTURE_API_KEY와 동일 값>`

> 브라우저에서 직접 API/WS에 붙기 때문에, 로컬 백엔드가 외부에서 접근 가능해야 한다.
> (예: cloudflared tunnel, ngrok, tailscale funnel 등)

## 장애 시 운영 전략

- Supabase 장애 또는 네트워크 이슈 시:
  - `hybrid` 모드가 자동으로 SQLite fallback
  - `/api/runtime/profile`에서 `fallback_active=true` 확인 가능

## 확장 시점

- 로컬 리소스 한계 또는 다중 워커 필요 시:
  - Queue를 `redis`로 변경
  - Worker 프로세스를 2개 이상 실행
- 그 다음 단계에서만 Docker Compose 상시 운영 또는 K8s/ECS 검토

