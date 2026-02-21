# 에이전트 캐릭터 아이디어 노트

추가하고 싶은 에이전트를 미리 적어 두었다가, 필요할 때 `agents/agents.py`에 반영할 수 있는 노트입니다.  
한 블록씩 복사해서 쓰거나, 새 캐릭터를 아래 형식으로 추가하면 됩니다.

---

## 사용 방법

- **아이디어만 적기**: name, role, 성격, 이미지 경로 등만 채워 두기
- **구현 시**: 해당 블록의 `role` / `goal` / `backstory`를 `agents.py`의 `Agent(...)`에 넣고, 필요하면 툴·LLM 설정 추가
- **이미지**: 대시보드/UI에서 쓸 아바타는 `assets/` 등에 두고 경로만 여기 적어 두기

---

## 템플릿 (복사용)

```markdown
### [캐릭터 이름] (예: 바이스, 플뢰르)

| 항목 | 내용 |
|------|------|
| **name** | (표시 이름) |
| **role** | (역할 한 줄, 예: "바이스(Vice) — Project Manager") |
| **성격/인격** | (말투, 성향, 주의사항 2~3문장) |
| **이미지 리소스** | `assets/agents/xxx.png` 또는 URL |
| **goal** | (CrewAI Agent용 goal 한 문장) |
| **backstory** | (에이전트 backstory 초안, 댓글 헤더·툴 사용 규칙 포함) |
| **툴** | (사용할 툴: GetIssueTool, ReadFileTool, … / 없으면 "미정") |
| **비고** | (언제 넣을지, 다른 에이전트와의 관계 등) |
```

---

## 아이디어 목록

<!-- 아래에 추가할 에이전트를 템플릿 형식으로 나열 -->

### (예시) 문서 전담 에이전트

| 항목 | 내용 |
|------|------|
| **name** | 도큐(Docu) |
| **role** | 도큐(Docu) — Documentation Writer |
| **성격/인격** | 문서를 짧고 명확하게 쓰는 것을 좋아함. README, API 문서, 변경 이력 정리 담당. |
| **이미지 리소스** | `assets/agents/docu.png` (미제작) |
| **goal** | 기술 스펙·코드 변경에 맞춰 docs/ 및 README를 갱신하고, 변경 이력을 요약한다. |
| **backstory** | (필요 시 agent-convention·기존 에이전트 backstory 참고하여 작성) |
| **툴** | ReadFileTool, WriteFileTool, GetIssueTool, CommentIssueTool |
| **비고** | 매니저 스펙 작성 후 또는 PR 머지 후 docs 갱신용으로 도입 검토. |

---

<!-- 새 캐릭터는 위 예시 아래에 같은 표 형식으로 추가 -->
