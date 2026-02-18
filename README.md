# 🤖 My Agent Team

CrewAI 기반 AI 에이전트 팀 프로젝트.  
GitHub 이슈를 감지하여 자동으로 React 컴포넌트를 개발하고 QA합니다.

## 프로젝트 구조

```
my-agent-team/
├── agents/
│   └── agents.py         # 매니저 / 개발 / QA 에이전트 정의
├── tasks/
│   └── tasks.py          # 각 에이전트의 태스크 정의
├── tools/
│   └── github_tools.py   # GitHub API 커스텀 툴
├── main.py               # 진입점 (단일 이슈 or 감시 모드)
├── requirements.txt
└── .env.example
```

## 에이전트 역할

| 에이전트 | 역할 | 주요 툴 |
|----------|------|---------|
| Manager | 이슈 분석 및 기술 스펙 작성 | list/get/comment issue |
| Developer | React 컴포넌트 작성 및 PR 생성 | read/write file, create PR |
| QA | 코드 리뷰 및 버그 리포트 | read file, comment issue |

## 설치 및 실행

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 입력

# 3-A. 특정 이슈 처리
python main.py --issue 42

# 3-B. 감시 모드 (5분마다 새 이슈 체크)
python main.py --watch --interval 300
```

## 이슈 감시 방식

감시 모드는 **`agent-todo` 라벨**이 달린 이슈만 처리합니다.

```
GitHub 이슈에 'agent-todo' 라벨 추가
        ↓
main.py가 감지 (폴링)
        ↓
Manager → Developer → QA 순서로 처리
        ↓
라벨이 'agent-done'으로 교체됨
```

이렇게 하면 모든 이슈가 자동처리되는 것을 방지하고,  
에이전트에게 맡길 작업을 선택적으로 제어할 수 있습니다.

## 에이전트 확장하기

같은 패턴으로 DevOps, SNS 에이전트를 추가할 수 있습니다.

```python
# agents/agents.py에 추가
devops_agent = Agent(
    role="DevOps Engineer",
    goal="CI/CD 파이프라인 관리 및 AWS 배포",
    tools=[AwsDeployTool(), GithubActionsTool()],
    ...
)
```

## 비용 관리 팁

- 이슈 하나당 약 3~5번의 LLM API 호출 발생
- 감시 모드는 폴링 자체에는 비용 없음 (GitHub API만 사용)
- Claude Haiku 또는 GPT-4o-mini로 LLM을 변경하면 비용 절감 가능
