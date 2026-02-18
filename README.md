# 🤖 My Agent Team

CrewAI 기반 AI 에이전트 팀.  
GitHub 이슈를 감지해 **작업 요청에 맞는 기술 스펙**을 세우고, 그 스펙대로 구현·QA합니다.  
웹 작업을 기본으로 하되 **특정 프레임워크(React 등)에 한정하지 않으며**, 이슈·스펙에 명시된 스택을 따릅니다.

## 프로젝트 구조

```
TeamWP/
├── agents/
│   └── agents.py         # 매니저 / 개발 / QA 에이전트 (스펙 기반)
├── tasks/
│   └── tasks.py          # 각 에이전트의 태스크 정의
├── tools/
│   ├── github_tools.py   # GitHub API 툴
│   ├── vercel_tools.py   # Vercel API (선택)
│   └── discord_tools.py  # Discord Bot API (선택)
├── docs/
│   └── agent-convention.md   # 에이전트 일하는 방식 (docs/plan, skill, issues 규칙)
├── dashboard/            # 웹 대시보드 (FastAPI, 실시간 진행 상황)
├── main.py               # 진입점 (단일 이슈 / 감시 모드 / 대시보드)
├── requirements.txt
└── .env.example
```

## 에이전트 역할

| 에이전트 | 역할 | 주요 툴 |
|----------|------|---------|
| Manager | 이슈 분석 및 **기술 스펙 작성**(언어·프레임워크·산출물 명시) | list/get/comment issue, (선택) Discord |
| Developer | **스펙에 맞는** 구현 및 PR 생성 | read/write file, create PR, (선택) Vercel/Discord |
| QA | 스펙·스택 기준 코드 리뷰 | read file, comment issue |

## 스펙 기반 동작

- 매니저가 이슈를 보고 **사용할 언어·프레임워크·산출물**을 기술 스펙으로 정합니다.  
  (이슈에 이미 스택이 적혀 있으면 따르고, 없으면 프로젝트 맥락에 맞게 제안.)
- 개발·QA는 **그 스펙만 보고** 작업합니다. React/Vue/Svelte, 백엔드, 스크립트 등 어떤 형태든 요청에 맞춥니다.

## 에이전트 일하는 방식 (docs/ convention)

개발은 에이전트가 수행하고 GitHub를 메인으로 쓰므로, **저장소 안에 “일하는 방식”**을 정의할 수 있습니다.  
에이전트가 작업할 **대상 저장소**에 아래 구조를 두면, 매니저/개발/QA가 이를 읽고 씁니다.

| 디렉터리 | 용도 | 에이전트 사용 |
|----------|------|----------------|
| **docs/plan/** | 계획·스프린트·기술 스펙 요약 | 매니저 참조·작성 |
| **docs/skill/** | 프로젝트 스택·가이드라인·모범 사례 | 매니저·개발·QA 참조 |
| **docs/issues/** | 이슈별 요약·스펙·결과 (issue-42.md 등) | 매니저·개발·QA 작성·참조 |

- **없는 경로**는 무시하고 이슈 댓글만으로 진행합니다.
- 상세 규칙: [docs/agent-convention.md](docs/agent-convention.md)

## 설치 및 실행

**요구 사항:** Python **3.10 이상**. CrewAI가 3.10 미만을 지원하지 않습니다. (`python --version`으로 확인 후, 필요하면 [python.org](https://www.python.org/downloads/) 또는 `winget install Python.Python.3.11` 등으로 설치)

```bash
pip install -r requirements.txt
cp .env.example .env
# .env에 GITHUB_TOKEN, GITHUB_REPO, ANTHROPIC_API_KEY 등 입력

python main.py --issue 42              # 이슈 #42 처리
python main.py --watch --interval 300   # 5분마다 agent-todo 이슈 감시
python main.py --dashboard             # 웹 대시보드만 (아래 참고)
```

### 웹 대시보드

FastAPI로 동작하는 웹 대시보드에서 **실시간으로 에이전트 진행 상황**을 볼 수 있습니다. 기본 주소는 `http://127.0.0.1:3000`입니다.

| 명령 | 설명 |
|------|------|
| `python main.py --dashboard` | 대시보드만 기동. 브라우저에서 이슈 번호를 입력해 수동 실행 |
| `python main.py --dashboard --watch --interval 300` | 대시보드 + 5분마다 `agent-todo` 이슈 자동 감시. 상시 대기하면서 화면으로 모니터링할 때 권장 |

포트를 바꾸려면 `--port` 옵션을 사용합니다.  
예: `python main.py --dashboard --port 8080`

> **참고:** `--watch`만 쓰면 감시만 하고 대시보드는 뜨지 않습니다. 대시보드에서 진행 상황을 보려면 반드시 `--dashboard`를 함께 넣어야 합니다.

### 여러 저장소(프로젝트) 감시

한 설치로 2개 이상 저장소를 매니저/개발/QA 하려면 **저장소당 프로세스 하나**씩 띄우고, 각각 다른 저장소를 지정하면 됩니다.

- **방법 A — 환경 변수**  
  `GITHUB_REPO=owner/repo-a python main.py --watch`  
  (두 번째 터미널: `GITHUB_REPO=owner/repo-b python main.py --watch`)
- **방법 C — CLI `--repo`**  
  `python main.py --watch --repo owner/repo-a`  
  (두 번째 터미널: `python main.py --watch --repo owner/repo-b`)

`--repo`를 주면 `.env`의 `GITHUB_REPO`보다 우선합니다.

## 이슈 감시

- **`agent-todo`** 라벨이 달린 이슈만 처리합니다.
- 처리 후 라벨을 **`agent-done`**으로 바꿉니다.
- QA가 후속 작업을 등록할 때 생성하는 이슈에는 **`agent-followup`**만 붙으며, 감시 루프는 이 라벨을 처리하지 않습니다 (사람이 검토 후 필요 시 `agent-todo`를 수동으로 붙일 수 있음).

### 라벨·권한 권장

- **`agent-todo`**를 붙이면 다음 폴링에 매니저→개발→QA 파이프라인이 실행되므로, **이슈 등록·라벨 편집 권한을 아무에게나 주면 안 됩니다.**
- 저장소 설정에서 협업자 권한을 제한하거나, `agent-todo` 라벨을 신뢰할 수 있는 담당자만 붙이도록 정책을 두는 것을 권장합니다.

## 외부 API / MCP 확장 (Vercel, Discord 등)

다른 API나 MCP(Model Context Protocol)를 쓰려면 **tools**에 툴을 추가하면 됩니다.

### Vercel

- `.env`에 `VERCEL_TOKEN` 설정 시, 에이전트가 다음 툴을 사용할 수 있습니다.
  - `list_vercel_projects` — 프로젝트 목록 조회
  - `create_vercel_deployment` — 지정 브랜치로 배포 트리거
- 토큰: [Vercel Account → Tokens](https://vercel.com/account/tokens)

### Discord

- `.env`에 `DISCORD_BOT_TOKEN`(및 선택으로 `DISCORD_CHANNEL_ID`) 설정 시:
  - `send_discord_message` — 지정 채널에 메시지 전송 (작업 완료 알림 등)
- 봇 생성·토큰: [Discord Developer Portal](https://discord.com/developers/applications)

### 다른 MCP·API 추가

- `tools/` 아래에 새 모듈(예: `tools/slack_tools.py`)을 만들고, CrewAI `BaseTool`을 상속한 툴을 정의합니다.
- `agents/agents.py`의 `_optional_tools()`에서 환경 변수를 보고 해당 툴을 리스트에 넣으면, 설정된 경우에만 에이전트가 사용합니다.
- MCP 서버를 툴로 쓰려면 해당 MCP 클라이언트를 호출하는 래퍼 툴을 구현하면 됩니다.

## 비용 관리

- 이슈당 약 3~5회 LLM API 호출.
- 감시 모드 폴링은 GitHub API만 사용.
- Claude Haiku / GPT-4o-mini 등으로 모델을 바꾸면 비용 절감 가능.
