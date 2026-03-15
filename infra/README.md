# Phase 4 Runtime 인프라 가이드

## 구성 파일

- `docker-compose.phase4.yml`
  - `api` (FastAPI)
  - `worker` (queue consumer)
  - `postgres`
  - `redis`
  - `frontend` (Next.js)
- `k8s/*.yaml`
  - `api` / `worker` / `frontend` Deployment + Service
  - `worker-hpa` autoscaling 예시
- `ecs/taskdef-*.json`
  - API / Worker / Frontend Fargate task definition 템플릿

## 로컬 실행

```bash
docker compose -f infra/docker-compose.phase4.yml up --build
```

서비스:

- API: `http://127.0.0.1:3000`
- Frontend: `http://127.0.0.1:3001`
- Postgres: `127.0.0.1:5432`
- Redis: `127.0.0.1:6379`

## 주의

- `k8s`와 `ecs` 매니페스트의 이미지/시크릿 값은 실제 환경에 맞게 수정 필요.
- Phase 4는 런타임 배포 골격 제공 단계이며, 운영 환경 IAM/네트워크 정책은 Phase 5에서 강화.

