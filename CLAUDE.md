# CLAUDE.md — TeamWP 프로젝트 컨텍스트

Claude Code가 이 프로젝트에서 작업할 때 읽는 문서입니다.

---

## 프로젝트 목적

**TeamWP**는 "진짜 동작하는 AI 에이전트 팀 회사"입니다.
사람이 지시를 내리면 5명의 AI 에이전트 팀이 GitHub PR까지 만들어 냅니다.

```
채널 (GitHub Issues / Web Dashboard)
        ↓
   Task Queue  ← {product_id, instruction}
        ↓
  Orchestrator  ← product workspace repo 목록 조회
        ↓
  CrewAI Crew  (바이스 → 아주르 → 플뢰르 → 엘시 → 베델)
        ↓
  GitHub PR 생성 → 사람 머지 → CI/CD
        ↓
  Discord 알림 + Dashboard 업데이트
```

---

## 에이전트 팀

| 이름 | 역할 | AgentRole | env 변수 |
|------|------|-----------|----------|
| 바이스 (Vice) | PM / 요구사항 분석 + 팀 구성 | `VICE` | `AGENT_LLM_VICE` |
| 아주르 (Azure) | UI 디자인 + 퍼블리싱 | `AZURE` | `AGENT_LLM_AZURE` |
| 플뢰르 (Fleur) | 코드 구현 (메인 개발자) | `FLEUR` | `AGENT_LLM_FLEUR` |
| 엘시 (Elsi) | Devil's Advocate / 비판적 검토 | `ELSI` | `AGENT_LLM_ELSI` |
| 베델 (Bethel) | QA / 최종 검증 | `BETHEL` | `AGENT_LLM_BETHEL` |

- 실행 흐름: 바이스가 이슈를 분석해 팀 구성 JSON을 출력 → 동적으로 선발된 에이전트 크루 실행
- 브랜치 규칙: `feature/issue-{N}` (개발), `design/issue-{N}` (아주르)
- CrewAI는 실행 엔진으로만 사용 (비즈니스 로직은 `core/`에 있음)

---

## 디렉토리 구조

```
TeamWP/
├── core/                   # Worker Architecture (핵심 계층)
│   ├── models.py           # 도메인 모델 (Project, WorkTask, Instruction, AgentRole 등)
│   ├── repository.py       # SQLite/Postgres CRUD (ArchitectureRepository 파사드)
│   ├── orchestrator.py     # Task 생성 + 상태 관리 (ManagerOrchestrator)
│   ├── workflow.py         # 실제 CrewAI 실행 엔진 (TaskWorkflowEngine)
│   ├── channel.py          # 채널 추상화 (GithubIssueAdapter, DashboardAdapter)
│   ├── queue.py            # Task Queue (Local / Redis 플러그인)
│   ├── worker.py           # WorkerRuntime (큐에서 꺼내 workflow 실행)
│   └── llm_config.py       # 역할별 LLM 선택 (get_llm(AgentRole))
│
├── agents/
│   └── agents.py           # CrewAI Agent 객체 정의 (manager_agent, dev_agent 등)
│
├── tasks/
│   └── tasks.py            # CrewAI Task 팩토리 함수 + AGENT_HEADER_MAP
│
├── tools/                  # CrewAI 도구
│   ├── github_tools.py     # GitHub 이슈 읽기/댓글/PR 생성
│   ├── discord_tools.py    # Discord 메시지 전송
│   └── vercel_tools.py     # Vercel 배포 트리거
│
├── dashboard/
│   └── server.py           # FastAPI 서버 (포트 3000)
│                           # API: /api/products, /api/instructions, /api/tasks
│                           # WS:  /ws/tasks/{task_id}
│                           # Webhook: /webhooks/github
│
├── dashboard-next/         # Next.js 프론트엔드 (포트 3001)
│   └── app/page.tsx        # 단일 페이지 (제품 관리 + 지시 입력 + 실시간 피드)
│
├── main.py                 # CLI 진입점 (--issue / --watch / --dashboard)
├── worker_main.py          # 독립 워커 프로세스
├── usage_tracking.py       # LLM 사용량 추적 + Discord 알림
├── usage_hooks.py          # CrewAI before/after LLM 훅 등록
├── dashboard_state.py      # 인메모리 실행 상태 스냅샷 (레거시 호환)
│
├── docs/                   # 에이전트가 읽고 쓰는 문서
│   ├── plan/               # 스프린트·기술 스펙 (매니저 참조·작성)
│   ├── skill/              # 스택·가이드라인 (전 에이전트 참조)
│   └── issues/             # 이슈별 스펙·결과 (issue-{N}.md)
│
├── infra/                  # Docker Compose / ECS / k8s 설정
├── scripts/                # 로컬 실행·스모크 테스트 스크립트
└── tests/                  # pytest 테스트 (core/, API)
```

---

## 실행 방법

### 로컬 개발

```bash
# 1. 환경 설정
cp .env.example .env
# .env에 OPENAI_API_KEY 또는 ANTHROPIC_API_KEY, GITHUB_TOKEN, GITHUB_REPO 입력

# 2. Python 패키지
pip3 install -r requirements.txt

# 3-A. 백엔드 서버 (FastAPI, 포트 3000)
python3 main.py --dashboard

# 3-B. Next.js 프론트엔드 (포트 3001)
cd dashboard-next && npm run dev

# 4. GitHub 이슈 단건 처리
python3 main.py --issue 42

# 5. GitHub 이슈 자동 감시
python3 main.py --watch --interval 300
```

### DB / Queue 백엔드

| 항목 | 기본값 | 운영 변경 |
|------|--------|-----------|
| DB | SQLite (`.agent_architecture.db`) | `ARCHITECTURE_DB_BACKEND=postgres` |
| Queue | 인메모리 Local | `ARCHITECTURE_QUEUE_BACKEND=redis` |

Postgres와 Redis 없이 SQLite + Local 큐로 이 컴퓨터에서 바로 실행 가능합니다.

---

## 핵심 환경변수

```bash
# LLM (둘 중 하나 필수)
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...

# GitHub
GITHUB_TOKEN=...
GITHUB_REPO=owner/repo

# 역할별 LLM (선택, 기본값 openai/gpt-4o)
AGENT_LLM_VICE=openai/gpt-4o
AGENT_LLM_FLEUR=anthropic/claude-opus-4-6   # 예: 플뢰르만 Claude로
AGENT_LLM_BETHEL=openai/gpt-4o-mini

# Discord 알림 (선택)
DISCORD_BOT_TOKEN=...
DISCORD_CHANNEL_ID=...

# GitHub Webhook (선택, PR 머지 감지)
GITHUB_WEBHOOK_SECRET=...

# 사용량 상한 (선택)
USAGE_LIMIT_TOKENS=500000
USAGE_LIMIT_CALLS=100
```

---

## 설계 원칙

1. **CrewAI는 실행 레이어** — 비즈니스 로직은 `core/`에, CrewAI는 `core/workflow.py` 안에서만 사용
2. **채널 무관 진입** — GitHub Issues든 Web Dashboard든 `ChannelAdapter → TaskQueue`로 동일하게 처리
3. **Human Gate** — 에이전트는 PR까지만 책임, 머지는 사람이 결정
4. **SQLite 우선** — 로컬·스테이징은 SQLite, 운영만 Postgres로 교체 (코드 변경 불필요)
5. **멀티 LLM** — 역할별 env 변수 하나만 바꾸면 GPT ↔ Claude 전환 가능

---

## 코딩 컨벤션

- Python 3.11+, `from __future__ import annotations`
- 도메인 모델은 `@dataclass`로, `slots=True`는 필드 기본값이 없을 때만
- DB 접근은 반드시 `ArchitectureRepository` 파사드를 통해 (SQLite/Postgres 구현체 직접 호출 금지)
- 새 채널 추가 시 `core/channel.py`에 `ChannelAdapter` 구현체 추가
- 에이전트 이름은 코드에서 `AgentRole` enum 사용 (문자열 하드코딩 금지)
- 테스트에서 crewai mocking: `sys.modules['crewai'] = types.ModuleType('crewai')`

---

## 테스트

```bash
# core 계층 단위 테스트
python3 -m pytest tests/test_phase2_core.py -v

# API 통합 테스트
python3 -m pytest tests/test_architecture_api.py -v

# TypeScript 타입 검사
cd dashboard-next && node_modules/.bin/tsc --noEmit
```

---

## 관련 문서

- `docs/agent-convention.md` — 에이전트가 대상 저장소의 `docs/` 구조를 읽고 쓰는 규칙
- `docs/agent-ideas.md` — 에이전트 확장 아이디어
- `Agent Conversation team.md` — 프로젝트 비전 원문
- `.env.example` — 전체 환경변수 목록 및 설명
- `infra/README.md` — Docker/ECS/k8s 배포 가이드
