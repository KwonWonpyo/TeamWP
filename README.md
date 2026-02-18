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
├── main.py               # 진입점 (단일 이슈 or 감시 모드)
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

## 설치 및 실행

```bash
pip install -r requirements.txt
cp .env.example .env
# .env에 GITHUB_TOKEN, GITHUB_REPO, ANTHROPIC_API_KEY 등 입력

python main.py --issue 42              # 이슈 #42 처리
python main.py --watch --interval 300   # 5분마다 agent-todo 이슈 감시
```

## 이슈 감시

- **`agent-todo`** 라벨이 달린 이슈만 처리합니다.
- 처리 후 라벨을 **`agent-done`**으로 바꿉니다.

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
