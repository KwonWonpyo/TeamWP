# AGENTS.md

## Cursor Cloud specific instructions

### Overview

CrewAI 기반 AI 에이전트 팀 프로젝트. GitHub 이슈를 감지해 매니저→개발→QA 파이프라인으로 처리합니다.
단일 Python 프로세스로 동작하며, Docker나 외부 데이터베이스 없이 실행됩니다.

### Prerequisites (Secrets)

실제 에이전트 실행에는 다음 환경변수가 필요합니다 (Secrets 섹션에 등록):

- `OPENAI_API_KEY` — CrewAI LLM 호출용 (또는 `ANTHROPIC_API_KEY`)
- `GITHUB_TOKEN` — GitHub API 접근용 (Personal Access Token, `repo` scope)
- `GITHUB_REPO` — 대상 저장소 (`owner/repo` 형식)

### Running the application

- **대시보드**: `python main.py --dashboard` → `http://127.0.0.1:3000`
- **단일 이슈 처리**: `python main.py --issue <number>`
- **감시 모드**: `python main.py --watch --interval 300`
- 상세 명령어: `README.md` 참조

### Testing

- `python test_main.py --list` — 등록된 테스트 프로세스 목록
- `python test_main.py --run 1` — 메타 정보 출력 (API 호출 없음)
- `python test_main.py --run 3` — 툴 클래스 로드 확인 (API 호출 없음)
- `python test_main.py --run 2` — 에이전트별 툴 목록 (OPENAI_API_KEY 필요)

### Gotchas

- `agents/agents.py` 모듈은 import 시점에 `LLM()` 객체를 생성하므로, `OPENAI_API_KEY`가 없으면 agent를 import하는 모든 코드가 실패합니다. 대시보드 기동도 마찬가지입니다.
- `.env` 파일은 프로젝트 루트에 있어야 하며, `main.py`가 `Path(__file__).resolve().parent / ".env"`로 로드합니다. 단, `load_dotenv`는 `override=False`이므로 이미 설정된 환경변수(Secrets)가 `.env` 파일보다 우선합니다.
- 이 프로젝트에는 별도의 린터(flake8, ruff 등)나 pytest 기반 자동화 테스트가 설정되어 있지 않습니다. `test_main.py`가 유일한 테스트 진입점입니다.
- `.agent_usage.json` 파일이 프로젝트 루트에 자동 생성되어 LLM 사용량을 추적합니다. 커밋하지 않도록 주의하세요.
- CrewAI 실행 시 tracing 프롬프트(`Would you like to view your execution traces?`)가 표시될 수 있습니다. 20초 타임아웃으로 자동 스킵되지만, `.env`에 `CREWAI_TRACING_ENABLED=false`를 추가하면 프롬프트를 방지할 수 있습니다.
- 대시보드 POST `/api/run` 호출 시 에이전트 실행은 백그라운드 스레드에서 수행됩니다. 완료까지 이슈 복잡도에 따라 30초~수 분 소요됩니다.
