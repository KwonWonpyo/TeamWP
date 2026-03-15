# AI Agent Worker Architecture 전체 개편 로드맵

`Agent_Conversaion_Team.md`의 목표를 실제 구현 단계로 옮기기 위한 실행 계획.

## 0) 기준 문서와 목표 범위

- 기준: `Agent_Conversaion_Team.md`
- 핵심 목표:
  - AI Company Simulator
  - Multi-Repo Development
  - Worker Pool + Queue
  - Conversation Dashboard

특히 **Section 16 Infrastructure**를 필수 반영 대상으로 본다.

### 진행 상태 업데이트 (2026-03-14)

- Phase 1: 완료
- Phase 2: 진행 중 (Repository 백엔드 선택 구조 + Queue/Worker + LangGraph fallback 워크플로우 스켈레톤 반영)
- Phase 3: 시작 (Next.js/Tailwind 프론트엔드 스캐폴딩 + WebSocket feed 연동)
- Phase 4: 시작 (Docker/Compose + K8s/ECS 배포 템플릿 반영)
- Phase 5: 시작 (API key 보호 + health/ready/metrics 관측 레이어 반영)

## 1) 인프라 목표 매트릭스 (Section 16 반영 체크)

### Backend

| 항목 | 목표 스택 | 현재 상태 | 반영 단계 |
| --- | --- | --- | --- |
| API 서버 | Python + FastAPI | ✅ 부분 반영 (기존 + 확장 API) | Phase 1 완료 |
| 오케스트레이션 | LangGraph | ⚠️ 스켈레톤 반영 (fallback 실행 포함) | Phase 2 진행 |
| Queue/Cache | Redis | ⚠️ 큐 인터페이스/Redis 어댑터 반영 | Phase 2 진행 |
| 영속 저장소 | Postgres | ⚠️ Postgres 어댑터 반영 (실서버 연결은 운영 설정 필요) | Phase 2 진행 |

### Frontend

| 항목 | 목표 스택 | 현재 상태 | 반영 단계 |
| --- | --- | --- | --- |
| 앱 프레임워크 | Next.js + React | ⚠️ `dashboard-next` 스캐폴딩 + UI 연결 반영 | Phase 3 진행 |
| 스타일링 | Tailwind | ⚠️ Tailwind 기반 UI 반영 | Phase 3 진행 |
| 실시간 채널 | WebSocket | ⚠️ `/ws/tasks/{task_id}` 실시간 피드 반영 | Phase 3 진행 |

### Runtime

| 항목 | 목표 스택 | 현재 상태 | 반영 단계 |
| --- | --- | --- | --- |
| 컨테이너 | Docker | ⚠️ API/Worker/Frontend Dockerfile + compose 반영 | Phase 4 진행 |
| 오케스트레이션 | AWS ECS / Kubernetes | ⚠️ K8s/ECS 템플릿 매니페스트 반영 | Phase 4 진행 |

## 2) 현재까지 반영된 1차 구현(Phase 1)

- `projects/tasks/conversations` 도메인 모델 추가
- 저장소 계층 추가 (SQLite 기반, 향후 Postgres 마이그레이션 대상)
- Manager Orchestrator 스켈레톤 추가
- 대시보드 서버에 프로젝트/태스크/대화 API 확장

> 해석: Phase 1은 “아키텍처 골격 검증” 단계이며, Section 16의 최종 스택 완전 반영 단계는 아님.

## 3) 실행 계획

### Phase 2 — Backend 정합화 (LangGraph + Redis + Postgres)

목표: Backend를 Section 16 스택으로 수렴.

1. 데이터 계층 분리
   - `ArchitectureRepository` 인터페이스화
   - `SqliteRepository`(개발용) / `PostgresRepository`(운영용) 분리
2. Postgres 연결
   - SQLAlchemy(또는 psycopg) 기반 구현
   - 마이그레이션(DDL) 추가
3. Redis Queue 도입
   - task enqueue / worker consume 구조
   - 상태 전이(pending → in_progress → done/failed) 일원화
4. LangGraph 도입
   - PM → CTO → Dev → QA → Publish를 그래프 노드로 모델링
   - 실패/재시도/분기(UI 작업 포함) 정책 반영
5. 테스트
   - API + orchestration integration test
   - queue 처리 흐름 테스트

완료 조건:
- 신규 task가 Redis 큐로 유입되고, LangGraph workflow를 통해 실행되며 결과가 Postgres conversations에 기록됨.

### Phase 3 — Frontend 전환 (Next.js + Tailwind + WebSocket)

목표: Dashboard를 목표 UI 스택으로 교체.

1. `dashboard-next/` 초기화 (Next.js + React + Tailwind)
2. API 바인딩
   - projects/tasks/conversations 조회
   - task 생성 및 상태 모니터링
3. 실시간 전송
   - WebSocket 채널(`/ws/tasks/{task_id}`) 추가
   - polling 제거 또는 fallback으로만 유지
4. 화면 구성
   - Organization View
   - Task Timeline
   - Live Conversation Feed

완료 조건:
- 브라우저에서 task 실행 시, WebSocket으로 에이전트 대화/상태가 실시간 반영됨.

### Phase 4 — Runtime 전환 (Docker + ECS/K8s)

목표: 운영 가능한 배포 단위 확보.

1. Dockerfile 분리
   - `api`, `worker`, `frontend`
2. Compose(개발) 및 Helm/ECS TaskDef(운영) 작성
3. 오토스케일 정책
   - worker replica 기준: queue depth, latency
4. 보안 정책 반영
   - 최소 권한 토큰, 네트워크 분리, 비밀관리

완료 조건:
- 컨테이너 단위로 API/Worker/Frontend가 배포되고, worker pool scale-out이 가능함.

## 4) 리스크 및 결정 필요 사항

1. DB 선택
   - 로컬 개발 SQLite 유지 여부
   - 운영 환경 Postgres 강제 여부
2. Queue 구현
   - Celery vs RQ vs custom worker
3. Frontend 마이그레이션
   - 기존 FastAPI static 대시보드 유지/폐기 전략
4. 배포 타겟
   - ECS 우선 vs Kubernetes 우선

## 5) 다음 실행 단위(즉시 착수용)

다음 커밋부터 아래 순서로 진행:

1. `Repository` 인터페이스 도입 + Postgres 어댑터 추가
2. Redis 큐 프로듀서/컨슈머 기본 루프 구현
3. LangGraph 워크플로우 스켈레톤 연결

