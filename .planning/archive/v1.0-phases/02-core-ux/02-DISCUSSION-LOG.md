# Phase 2: Core UX — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 02-core-ux
**Areas discussed:** 레이아웃 구조, 슬래시 카탈로그 소스, Ctrl+C 취소 범위, SlashPopup 세부 동작

---

## 레이아웃 구조

### 수직 배치

| Option | Description | Selected |
|--------|-------------|----------|
| Static 위 / input 아래 | [Static 히스토리] → [active slot] → [input] → [status bar]. Claude Code 흐름. | ✓ |
| Status bar 위 / input 아래 | [status bar] → [Static] → [active] → [input]. 상태바 항상 눈에 보임. | |

**User's choice:** Static 위 / input 아래 (Claude Code 스타일)

### 구분선 — active slot ↔ input

| Option | Description | Selected |
|--------|-------------|----------|
| 없음 | 빈 줄 1행만. Claude Code 스타일. | |
| 있음 | `─`×터미널 폭 구분선. Phase 1 스켈레톤과 유사. | ✓ |

**User's choice:** 구분선 있음

### 구분선 — input ↔ status bar

| Option | Description | Selected |
|--------|-------------|----------|
| 없음 | input과 status bar 사이 데항 색 차이로만 분리. | |
| 있음 | `─`×터미널 폭 구분선. | ✓ |

**User's choice:** 구분선 있음

### Confirm 교체 방식

| Option | Description | Selected |
|--------|-------------|----------|
| Input 영역 조건부 대체 | confirm 모드일 때 InputArea 대신 ConfirmDialog. 동일 위치. | ✓ |
| Active slot 뒤 인라인 삽입 | active slot 아래에 다이얼로그, input은 disabled. | |

**User's choice:** Input 영역 조건부 대체

---

## 슬래시 카탈로그 소스

| Option | Description | Selected |
|--------|-------------|----------|
| 정적 JSON 하드코딩 | `src/slash-catalog.ts` 고정. 단순, 동기화 수동. | ✓ |
| WS 이벤트 | harness_server가 접속 시 `slash_catalog` broadcast. PEXT 추가 필요. | |
| harness CLI 호출 | `python harness_core --list-commands` 실행. ESLint 금지 규칙 충돌. | |

**User's choice:** 정적 JSON 하드코딩

---

## Ctrl+C 취소 범위

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 2: 클라이언트 stub | `cancel` 타입 추가 + 전송만. 서버 처리는 Phase 3. | ✓ |
| Phase 3으로 이동 | INPT-09 전체를 Phase 3 재배치. Phase 2 Ctrl+C는 exit만. | |

**User's choice:** Phase 2: 클라이언트 stub
**Notes:** ClientMsg에 `cancel` 타입 추가하고 전송 구현. 서버는 무시하지만 클라이언트 코드는 올바른 상태.

---

## SlashPopup 세부 동작

### 트리거 타이밍

| Option | Description | Selected |
|--------|-------------|----------|
| / 입력 즉시 표시 | `/` 누르면 즉시 전체 목록 노출. Claude Code 스타일. | ✓ |
| / + 한 글자 이상 | `/s` 입력 시 노출. 실수 화면 줄어듦. | |

**User's choice:** `/` 입력 즉시

### Tab 동작

| Option | Description | Selected |
|--------|-------------|----------|
| 명령 보완 후 유지 | Tab = 입력창 채움 + 팝업 닫힘. Enter로 제출. | ✓ |
| 즉시 제출 | Tab = 바로 제출. | |

**User's choice:** 명령 보완 후 유지

### 팝업 노출 위치

| Option | Description | Selected |
|--------|-------------|----------|
| 입력창 바로 위 | `flexDirection='column'` 인라인. scrollback 밀어냄. | ✓ |
| Active slot 아래/input 위 | Static history와 input 사이. 위치 고정. | |

**User's choice:** 입력창 바로 위 인라인

---

## Claude's Discretion

- resize clear 구현 방식 (RND-04)
- ctx 미터 리렌더 격리 방법 (RND-09)
- 테마 자동 감지 fallback 팔레트 (RND-10)
- Tab 인자 자동완성 범위 (INPT-08)
- ToolCard 상세 펼침 트리거 UX

## Deferred Ideas

- WS 이벤트 기반 slash catalog — Phase 3 PEXT 논의 시 재검토
- PEXT-05 서버 cancel 처리 — Phase 3
