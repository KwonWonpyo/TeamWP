# 토큰 사용량 저장 구조 개선 계획

현재 JSON 파일 기반의 단순 누적 방식을 구간별·메타데이터 기반 분석이 가능한 구조로 전환하기 위한 계획.

---

## 현재 구조 요약

- **저장 위치**: 프로젝트 루트 `.agent_usage.json`
- **저장 방식**: 누적 합계만 보관 (input_tokens, output_tokens, calls)
- **담당 모듈**: `usage_tracking.py` — `add_usage()` / `get_usage()` / `reset_usage()`
- **대시보드**: 로컬 Flask 서버 (`dashboard/server.py`)에서 조회

## 현재 구조의 문제점

1. **구간별 조회 불가**: 언제 얼마나 썼는지 기록이 없어 일별/주별/월별 분석이 불가능
2. **메타데이터 없음**: 어느 이슈, 어느 에이전트가 토큰을 소모했는지 추적 불가
3. **동시성 위험**: JSON 파일을 읽고 쓰는 사이 race condition 가능성 (현재 `threading.Lock`으로 부분 방어 중이나 근본적 한계 존재)
4. **로컬 전용**: 대시보드가 로컬에서만 실행되며 외부 접근 불가
5. **리셋 시 이력 소멸**: `reset_usage()` 호출 시 과거 데이터가 완전 삭제됨

---

## 개선 목표

1. **구간별 사용량 조회**: 일/주/월 단위 집계, 기간 범위 선택 가능
2. **이슈별 사용량 추적**: `issue_number` 태깅으로 이슈 처리 비용 파악
3. **에이전트별 사용량 추적**: `agent_name` 태깅으로 어느 에이전트가 비용을 많이 쓰는지 분석
4. **이력 보존**: 리셋 없이 전체 히스토리 유지, 기간 필터로 조회
5. **외부 접근 가능한 대시보드**: Vercel 배포로 어디서든 실시간 확인

---

## 개선 방향

### 데이터 모델 변경

현재 누적 합계 구조에서 **호출 이벤트 단위 레코드** 구조로 전환.

```
현재: { input_tokens: 총합, output_tokens: 총합, calls: 총합 }

개선: 각 LLM 호출마다 1행 INSERT
{
  timestamp,
  input_tokens,
  output_tokens,
  issue_number,   // 새로 추가
  agent_name,     // 새로 추가
  model,          // 새로 추가 (비용 계산 정확도 향상)
}
```

집계는 쿼리 시점에 `GROUP BY`로 처리.

### `add_usage()` 인터페이스 변경 (선행 작업)

DB 연동 전에 인터페이스를 먼저 확장해두면 마이그레이션 비용 최소화.

```python
# 현재
add_usage(input_tokens=100, output_tokens=50)

# 개선 후 (하위 호환 유지)
add_usage(
    input_tokens=100,
    output_tokens=50,
    issue_number=42,      # 선택적
    agent_name="coder",   # 선택적
    model="gpt-4o",       # 선택적
)
```

### 추천 스택

| 옵션 | 특징 | 적합한 경우 |
|------|------|------------|
| **Vercel Postgres** (Neon) | SQL, 집계 쿼리 자유로움, Vercel 통합 간단 | 장기 이력 + 복잡한 집계 |
| **Upstash Redis** | 빠름, 무료 티어 충분, 간단한 시계열 | 실시간 카운터 위주 |
| **Turso (LibSQL)** | SQLite 계열, 마이그레이션 쉬움 | 기존 구조 유지하며 점진 전환 |

현재 구조에서 가장 이전이 쉬운 것은 **Turso** (SQLite → LibSQL), 대시보드 기능 확장성은 **Vercel Postgres** 추천.

### 대시보드 개선

- Vercel에 배포하여 외부 접근 가능
- 구간 선택기 (일/주/월/커스텀)
- 이슈별 비용 테이블
- 에이전트별 사용량 차트

---

## 작업 우선순위 (미착수)

1. `add_usage()` 인터페이스에 `issue_number`, `agent_name`, `model` 파라미터 추가 (하위 호환)
2. 호출 측(`usage_hooks.py` 등)에서 메타데이터 전달하도록 수정
3. DB 스택 결정 및 스키마 설계
4. `usage_tracking.py` 저장 레이어를 DB로 교체
5. 대시보드 구간별 조회 UI 추가
6. Vercel 배포 설정

---

*작성일: 2026-02-22*
