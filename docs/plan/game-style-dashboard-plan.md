# 게임형 에이전트 대시보드 레이아웃

대시보드를 "캐릭터 수집형 게임에서 캐릭터들이 대화하는" 레이아웃으로 바꾸고, 에이전트별 인격/이미지 메타는 대시보드 전용 모듈로 분리해 LLM에는 영향 없이 적용한다.

---

## 현재 구조 요약

- **에이전트**: `agents/agents.py`에 매니저(바이스), 개발(플뢰르), QA(베델) 3명 정의. `role` / `goal` / `backstory`만 있고, 대시보드 전용 메타는 없음.
- **상태**: `dashboard_state.py`의 `AgentState(id, role, state)`와 `CurrentRun.completed_tasks`(태스크 완료 시 순서대로 요약 문자열 추가)가 이미 있음.
- **대시보드**: `dashboard/static/index.html`에서 에이전트 카드를 `minmax(180px, 1fr)` 그리드로 표시하고, 하단에 **공통** `last-result` 한 칸만 있음. 아바타는 8x8 픽셀 placeholder.

**목표**: 레이아웃을 "에이전트별로 넓은 영역 + 각자 말(최종 답변)"으로 바꾸고, 인격/이미지는 대시보드 전용으로만 추가.

---

## 1. 에이전트 "인격/성격" (대시보드 전용)

- **agents.py는 수정하지 않음.** LLM용 정의는 그대로 둠.
- **대시보드 전용 메타**를 새 모듈에서 관리:
  - 예: `dashboard/agent_meta.py` (또는 `dashboard/agent_assets.py`)
  - 에이전트 식별자(현재 `dashboard_state`에서 쓰는 `id`: role 기반, 예 `바이스(vice)_—_project_manager` 등)에 매핑:
    - **display_name**: 표시 이름 (예: "바이스", "플뢰르", "베델")
    - **personality**: 한 줄 성격/인격 문구 (대시보드 캐릭터 카드용, LLM 미사용)
    - **avatar_path**: 대시보드용 이미지 경로 (예: `"/avatars/vice.png"`). 없으면 기존 placeholder 유지
  - 이미지 파일은 `dashboard/static/avatars/` 등에 두고, 해당 모듈에서는 경로만 정의. (이미지 리소스는 사용자가 추가하는 형태로 안내.)

이렇게 하면 "인격"은 대시보드에서만 보이고, Crew/LLM에는 기존 `role` / `backstory`만 사용된다.

---

## 2. 대시보드 레이아웃: 에이전트별 영역 확대 + "하고 싶은 말" 영역

- **에이전트별 영역 확대**
  - 그리드를 "에이전트당 한 블록"이 잘 보이도록 변경:
    - 예: `grid-template-columns: 1fr` (한 줄에 1명) 또는 `repeat(3, 1fr)` (3열 고정), 카드 `min-width` / `min-height`로 최소 크기 확보.
  - 픽셀 아바타 대신, `agent_meta`에 `avatar_path`가 있으면 `<img>`로 표시, 없으면 기존 placeholder 유지.

- **에이전트마다 "final answer / 하고 싶은 말" 표시**
  - 이미 `get_snapshot()`에 `current_run.completed_tasks`가 **순서대로** (매니저 → 개발 → QA) 들어감.
  - 프론트에서 `agents[i]`와 `completed_tasks[i]`를 1:1로 매칭해, **각 에이전트 카드 안**에 전용 영역을 두고:
    - 해당 에이전트가 완료되기 전: 빈 칸 또는 "대기 중" 등
    - 완료 후: `completed_tasks[i]` 내용 표시 (스크롤 가능한 텍스트 영역)
  - 기존 하단 단일 `last-result`는 "전체 런 요약" 용도로 유지하거나, 선택적으로 제거해도 됨.

즉, **데이터는 이미 있음** — 스냅샷의 `agents` 순서와 `completed_tasks` 인덱스만 맞춰서 카드별로 넣어주면 된다.

---

## 3. 이미지 리소스 위치 (agents.py 제외)

- **에이전트 이미지/리소스**는 `agents/agents.py`가 아닌 **대시보드 쪽**에서만 참조:
  - `dashboard/agent_meta.py`(또는 `dashboard/agent_assets.py`)에서 경로만 정의.
  - 실제 파일: `dashboard/static/avatars/vice.png`, `fleur.png`, `bethel.png` 등 (이름 규칙은 정해두면 됨).
- 서버는 이미 `dashboard/static`을 StaticFiles로 서빙하므로, `/avatars/xxx.png`로 접근 가능하게 두면 됨.
- 이미지가 없을 때는 기존 픽셀 placeholder 또는 간단한 이니셜/아이콘으로 fallback.

---

## 4. API 확장 (선택)

- 현재 `GET /api/status`가 `get_snapshot()`을 그대로 반환하므로, `agents`와 `current_run.completed_tasks`만으로도 위 레이아웃 구현 가능.
- **옵션**: 대시보드에서 메타를 한 번에 쓰기 위해, `dashboard/agent_meta`를 읽어서 `GET /api/status` 응답에 `agent_meta: [{ id, display_name, personality, avatar_path }, ...]`를 추가. 순서를 `agents`와 맞추면 프론트 매칭이 쉬움.
- 구현이 단순해지려면, 첫 단계에서는 **프론트에서 id/role 기반으로 고정 매핑**으로 `display_name` / `personality` / avatar 경로를 써도 됨. 나중에 에이전트가 늘어나면 API로 넘기는 편이 유지보수에 좋음.

---

## 5. 구현 시 유의사항

- **에이전트 순서**: `main.py`의 `agents_for_crew` 및 `init_agents_from_crew` 순서와, `process_issue`의 `tasks` 순서가 동일하므로 `completed_tasks[i]`와 `agents[i]`가 같은 에이전트를 가리킴.
- **디자인**: 처음에는 기존 UI 톤(색, 폰트 등) 유지하고, **레이아웃만** "캐릭터별 넓은 칸 + 각자 말"로 바꾸면 됨. Live-2D/일본풍 감성은 이후 단계에서 적용 가능.

---

## 제안 작업 순서

1. **dashboard/agent_meta.py** (또는 agent_assets.py) 추가: 에이전트 id → display_name, personality, avatar_path 매핑. `agents.py`는 수정하지 않음.
2. **dashboard_state** 또는 **API**: (선택) `get_snapshot()` 호출부 또는 `GET /api/status`에서 `agent_meta` 리스트를 붙여서 반환. 없으면 프론트에서 id/role로 매핑.
3. **dashboard/static/index.html**
   - 에이전트 그리드: 에이전트당 영역을 크게 (1열 또는 2~3열 고정, 카드 최소 크기 확대).
   - 각 카드 내부: 아바타(이미지 또는 placeholder) + 이름 + personality 한 줄 + 상태 + **해당 에이전트의 "하고 싶은 말"** (`completed_tasks[i]`) 전용 영역.
   - 기존 `last-result`는 전체 요약용으로 유지할지 결정 후 반영.
4. **dashboard/static/avatars/** 디렉터리 생성 및 README 또는 주석으로 "에이전트별 이미지 배치 위치" 안내.

이 순서로 진행하면 "캐릭터 수집형 게임처럼 각 에이전트가 자기 영역에서 말하는" 레이아웃을 가져가면서, 인격/이미지는 대시보드 전용으로만 분리할 수 있다.
