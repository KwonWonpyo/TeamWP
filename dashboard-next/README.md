# Phase 3 Frontend (Next.js + Tailwind)

`dashboard-next`는 Phase 3 요구사항(Next.js/React/Tailwind/WebSocket)을 반영한 프론트엔드입니다.

## 실행

1) 백엔드 실행 (기존 FastAPI):

```bash
python3 main.py --dashboard --port 3000
```

2) 프론트엔드 실행:

```bash
cd dashboard-next
npm run dev -- --port 3001
```

브라우저:

- Frontend: `http://127.0.0.1:3001`
- Backend API: `http://127.0.0.1:3000`

## 환경 변수

`dashboard-next/.env.local` 예시:

```bash
NEXT_PUBLIC_API_BASE=http://127.0.0.1:3000
NEXT_PUBLIC_WS_BASE=ws://127.0.0.1:3000
# 선택: write API 보호가 켜진 경우
# NEXT_PUBLIC_ARCHITECTURE_API_KEY=your-api-key
```

## 제공 기능

- 프로젝트 등록/선택
- 태스크 생성(+자동 큐 적재)
- 워커 1회 실행
- `/ws/tasks/{task_id}` 기반 실시간 Conversation Feed 표시
