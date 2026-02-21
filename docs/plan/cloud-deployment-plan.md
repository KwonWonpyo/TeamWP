# 클라우드 배포 및 멀티 레포지토리 확장 계획

현재 로컬 단일 레포지토리 감시 구조를 **Vercel 대시보드 + 로컬(홈 PC) 에이전트 런타임** 형태로 전환하고,
향후 여러 레포지토리를 독립적으로 감시·운영할 수 있도록 확장하기 위한 계획.

1인 개발자 기준으로 구현·유지보수 가능한 수준으로 설계.

---

## 현재 구조 요약

```
[로컬 PC]
  main.py --dashboard --watch
    ├─ FastAPI 대시보드 (localhost:3000)
    ├─ GitHub 이슈 폴링 (GITHUB_REPO 하나, .env에서 읽음)
    └─ CrewAI 에이전트 실행 (동기 처리)
```

- 대시보드와 에이전트 런타임이 같은 프로세스에서 동작
- 레포지토리가 `.env`의 `GITHUB_REPO` 하나로 고정
- 로컬 외부에서 대시보드 접근 불가

---

## 목표 구조

```
[Vercel]                               [홈 PC (상시 실행)]
  Next.js / FastAPI 대시보드            main.py --watch --multi-repo
    ├─ 레포지토리별 탭 UI               ├─ 레포 A 감시 스레드
    ├─ 에이전트 상태 실시간 조회 →       ├─ 레포 B 감시 스레드
    ├─ 이슈 수동 실행 트리거  →         ├─ CrewAI 에이전트 풀
    └─ 토큰 사용량 대시보드             └─ 상태 API 서버 (외부 노출)
                                              ↕ ngrok / Cloudflare Tunnel
```

핵심 원칙:
- **Vercel에는 에이전트를 올리지 않는다.** Vercel 서버리스 함수는 실행 시간이 최대 60초(Pro)로 제한되어 수 분~수십 분이 걸리는 에이전트 런타임에 구조적으로 부적합.
- **에이전트 런타임은 홈 PC(또는 VPS)에서 상시 실행.** Vercel 대시보드는 상태 조회·트리거 역할만 담당.
- **통신은 HTTPS API.** Vercel ↔ 홈 PC 간 통신은 ngrok 또는 Cloudflare Tunnel로 홈 PC API를 외부에 노출.

---

## 단계별 구현 계획

### 1단계: 홈 PC API를 외부에서 접근 가능하게 (난이도: 낮음)

현재 `localhost:3000`인 FastAPI 서버를 외부에서 접근할 수 있도록 터널링.

**옵션 A: ngrok** (빠른 시작, 무료 티어 있음)
```bash
ngrok http 3000
# → https://xxxx.ngrok-free.app 주소 생성
```

**옵션 B: Cloudflare Tunnel** (무료, 고정 도메인 가능, 장기 운영 추천)
```bash
cloudflared tunnel --url http://localhost:3000
```

- 고정 도메인을 쓰려면 Cloudflare 계정 + 도메인 필요 (무료)
- 홈 PC가 꺼지면 외부 접근 불가 — 별도 처리 불필요 (대시보드만 Vercel에 있으면 해결)

**이 단계에서 얻는 것**: Vercel 없이도 스마트폰 등 외부에서 대시보드 접근 가능.

---

### 2단계: 멀티 레포지토리 지원 (난이도: 중간)

현재 `.env`의 `GITHUB_REPO` 하나 → 여러 레포지토리를 독립적으로 감시.

#### 설정 파일 방식 (`repos.yaml`)

```yaml
# repos.yaml
repos:
  - id: project-a
    repo: owner/project-a
    label: agent-todo
    interval: 300
    agents: [manager, dev, qa]        # 이 레포에서 사용할 에이전트 세트
  - id: project-b
    repo: owner/project-b
    label: agent-todo
    interval: 600
    agents: [manager, dev]
```

#### `main.py` 변경 방향

```python
# 현재: 단일 레포
watch_new_issues(interval=300)

# 개선: 레포별 독립 스레드
for repo_config in load_repos():
    t = threading.Thread(target=watch_repo, args=(repo_config,), daemon=True)
    t.start()
```

- 레포별로 `processed_issues` 딕셔너리 분리 (`{repo_id: set()}`)
- 에이전트 풀은 공유하되, 레포 설정에서 사용 가능한 에이전트 ID를 제한 가능
- `dashboard_state`에 `repo_id` 필드 추가 → 현재 어느 레포의 이슈를 처리 중인지 표시

#### API 변경

```
GET  /api/repos               → 등록된 레포 목록
GET  /api/status?repo=project-a  → 레포별 상태 스냅샷
POST /api/run                 → { repo: "project-a", issue: 42 }
```

---

### 3단계: Vercel 대시보드 분리 (난이도: 중간)

현재 `dashboard/static/index.html` (단일 HTML)을 Vercel에 배포 가능한 형태로 분리.

#### 옵션 A: 현재 HTML을 Vercel Static으로 배포 (최소 변경)

- `index.html`의 API 호출 URL을 환경변수(`VITE_API_BASE_URL` 등)로 분리
- `fetch('/api/status')` → `fetch('${API_BASE}/api/status')`
- `vercel.json`에 환경변수 설정으로 홈 PC API 주소 지정
- 빌드 없이 정적 파일만 배포 가능

```json
// vercel.json
{
  "env": {
    "API_BASE_URL": "https://your-tunnel.cloudflareaccess.com"
  }
}
```

#### 옵션 B: Next.js 앱으로 전환 (장기 권장)

- 레포별 탭 UI, 토큰 사용량 차트 등 복잡한 UI를 React 컴포넌트로 관리
- Vercel과 네이티브 통합, 자동 배포 (main 브랜치 push → 자동 갱신)
- `pages/api/proxy.ts`에서 홈 PC API 호출을 서버사이드에서 처리 (CORS 우회)

1인 개발자 기준으로 **1단계 → 옵션 A**로 빠르게 시작하고, 필요해지면 옵션 B로 전환 권장.

---

### 4단계: 레포별 탭 대시보드 UI (난이도: 낮음~중간)

Vercel에 배포된 대시보드에서 레포지토리별 탭을 구성.

```
[대시보드 레이아웃]
┌─────────────────────────────────────────────┐
│  [project-a 탭] [project-b 탭]              │
├─────────────────────────────────────────────┤
│  현재 선택된 레포의 에이전트 상태 카드        │
│  (바이스, 플뢰르, 베델... 각자 영역)         │
├─────────────────────────────────────────────┤
│  토큰 사용량  │  처리된 이슈 목록            │
└─────────────────────────────────────────────┘
```

- `GET /api/repos`로 탭 목록 동적 생성
- 탭 전환 시 `GET /api/status?repo=project-a` 호출
- 에이전트 카드는 기존 `game-style-dashboard-plan.md` 레이아웃 그대로 재사용

---

## 홈 PC 상시 실행 관리

에이전트 런타임이 홈 PC에서 돌아야 하므로, 프로세스 관리가 필요.

**Windows 환경 (현재)**
```powershell
# 작업 스케줄러에 등록하거나, 간단하게는 bat 스크립트
# start-agent.bat
cd C:\Users\commi\TeamWP
python main.py --dashboard --watch --multi-repo
```

- 재시작 자동화: Windows 작업 스케줄러로 시스템 시작 시 자동 실행
- 로그: stdout을 파일로 리다이렉트 (`>> logs\agent.log 2>&1`)

**장기: VPS 이전 시**
- Railway, Fly.io, Hetzner VPS 등에서 `python main.py --watch --multi-repo`를 systemd 서비스로 등록
- 홈 PC가 꺼져도 에이전트 상시 실행 가능

---

## 보안 고려사항

홈 PC API를 외부에 노출할 때 최소한의 인증 필요.

- **API Key 헤더**: `X-Agent-Key: <secret>` — 간단하고 충분
- `.env`에 `AGENT_API_KEY=...` 추가, FastAPI 미들웨어에서 검증
- Vercel 환경변수에도 동일 키 저장, 프록시 요청 시 헤더에 포함
- Cloudflare Tunnel 사용 시 Cloudflare Access로 추가 인증 가능

---

## 전체 마이그레이션 순서

| 순서 | 작업 | 예상 난이도 | 선행 조건 |
|------|------|------------|----------|
| 1 | Cloudflare Tunnel으로 localhost:3000 외부 노출 | 낮음 | - |
| 2 | `repos.yaml` 기반 멀티 레포 감시 지원 (`main.py`) | 중간 | - |
| 3 | `dashboard_state`에 `repo_id` 추가, API 레포 파라미터 지원 | 중간 | 2 |
| 4 | `index.html` API URL 환경변수화 → Vercel Static 배포 | 낮음 | 1 |
| 5 | 레포별 탭 UI 추가 | 낮음~중간 | 3, 4 |
| 6 | API Key 인증 미들웨어 추가 | 낮음 | 1 |
| 7 | (선택) Next.js 앱으로 대시보드 전환 | 높음 | 4, 5 |
| 8 | (선택) VPS 이전으로 상시 실행 | 중간 | 2 |

1~6번까지 완료하면 **1인 개발자가 유지보수 가능한 수준의 멀티 레포 클라우드 대시보드** 완성.

---

*작성일: 2026-02-22*
