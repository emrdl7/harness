---
phase: "01-foundation"
plan: "B"
subsystem: "ui-ink/ws-protocol"
tags: ["ws-protocol", "zustand", "typescript", "discriminated-union"]
dependency_graph:
  requires: []
  provides:
    - "ui-ink/src/protocol.ts — ServerMsg/ClientMsg discriminated union"
    - "ui-ink/src/ws/{parse,dispatch,client}.ts — WS 레이어"
    - "ui-ink/src/store/{messages,input,status,room,confirm,index}.ts — Zustand 5슬라이스"
  affects:
    - "ui-ink/src/App.tsx (Plan C 에서 교체 예정)"
    - "ui-ink/src/ws.ts (Plan C 에서 삭제 예정)"
tech_stack:
  added:
    - "zustand/create — 5개 독립 슬라이스"
    - "ws 패키지 — HarnessClient 클래스"
  patterns:
    - "discriminated union + assertNever exhaustive switch"
    - "appendToken in-place 스트리밍 패턴 (매 토큰 새 push 금지)"
    - "crypto.randomUUID() React key 패턴"
key_files:
  created:
    - "ui-ink/src/protocol.ts"
    - "ui-ink/src/ws/parse.ts"
    - "ui-ink/src/ws/dispatch.ts"
    - "ui-ink/src/ws/client.ts"
    - "ui-ink/src/store/messages.ts"
    - "ui-ink/src/store/input.ts"
    - "ui-ink/src/store/status.ts"
    - "ui-ink/src/store/room.ts"
    - "ui-ink/src/store/confirm.ts"
    - "ui-ink/src/store/index.ts"
  modified:
    - "ui-ink/src/ws.ts (레거시 이벤트 이름 교정 — Plan C 삭제 예정)"
decisions:
  - "레거시 ws.ts / store.ts 는 Plan C(App.tsx 교체) 전까지 유지 — App.tsx 가 여전히 참조"
  - "dispatch.ts 는 assertNever 로 exhaustive switch 강제 — 컴파일 타임 미처리 이벤트 탐지"
  - "appendToken 은 마지막 assistant streaming 메시지에 in-place append — Zustand set 최소화"
metrics:
  duration: "약 5분"
  completed: "2026-04-24"
  tasks_completed: 2
  files_created: 10
  files_modified: 1
---

# Phase 1 Plan B: WS 프로토콜 교정 + Store 슬라이스 분할 Summary

**한 줄 요약:** harness_server.py ground truth 기준 25종 ServerMsg discriminated union 신설, Zustand 5슬라이스 분리, exhaustive switch dispatch 로 프로토콜 이름 불일치 및 단일 store 구조 전면 교정.

## 완료된 태스크

| 태스크 | 커밋 | 파일 |
|--------|------|------|
| B-1: protocol.ts 신설 (25종 discriminated union) | 459f1b4 | ui-ink/src/protocol.ts |
| B-2: store 5슬라이스 + ws 모듈 신설 | 5c60f1c | ui-ink/src/store/*.ts, ui-ink/src/ws/*.ts |
| Deviation: 레거시 ws.ts 이벤트 이름 교정 | 220ac55 | ui-ink/src/ws.ts |

## 산출물 상세

### protocol.ts
- `ServerMsg` discriminated union (25종): token / tool_start / tool_end / agent_start / agent_end / error / info / confirm_write / confirm_bash / cplan_confirm / ready / room_joined / room_member_joined / room_member_left / room_busy / state_snapshot / state / slash_result / quit / queue / queue_ready / pong / claude_start / claude_end / claude_token
- `ClientMsg` discriminated union (5종): input / confirm_write_response / confirm_bash_response / slash / ping
- `assertNever` 헬퍼: exhaustive switch 컴파일 가드

### store/ (5슬라이스)
- **messages.ts**: `appendToken` in-place 스트리밍 패턴, `crypto.randomUUID()` id, streaming 플래그
- **input.ts**: 입력 버퍼 슬라이스
- **status.ts**: 연결상태 · 워킹디렉토리 · 모델 · 모드 · 턴 · busy
- **room.ts**: 룸명 · 멤버 · turn-taking activeInputFrom (Phase 3 확장 예정)
- **confirm.ts**: ConfirmMode 타입 + payload (Phase 2 완성 예정)
- **index.ts**: 5슬라이스 통합 re-export

### ws/ (3파일)
- **parse.ts**: JSON → ServerMsg 안전 파서 (실패 시 null 반환, T-01B-01 완화)
- **dispatch.ts**: ServerMsg exhaustive switch — 25개 case 전부 처리
- **client.ts**: HarnessClient 클래스 (heartbeat 30s / connect / send / close)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 레거시 ws.ts 금지 패턴 교정**
- **발견 시점:** Task B-2 완료 후 전체 검증 시
- **문제:** 성공 기준 "on_token/on_tool/error.message 가 codebase 에서 0건" 이지만 구 ws.ts 에 `on_token`, `on_tool`, `error.message` 가 잔존
- **수정:** ws.ts 의 이벤트 이름을 `token`, `tool_start`, `tool_end` 로 교정, `error.message` → `msg.text` 로 교정
- **Note:** ws.ts 파일 자체는 Plan C 에서 App.tsx 교체 후 삭제 예정 — 이번 plan 에서는 내용만 교정
- **커밋:** 220ac55

## 위협 모델 구현 상태

| Threat ID | 조치 |
|-----------|------|
| T-01B-01 (Tampering) | parseServerMsg 에서 JSON.parse 실패 시 null 반환 — dispatch 에서 null guard |
| T-01B-02 (Spoofing) | HARNESS_TOKEN env var 를 x-harness-token 헤더로 전송 — 코드 하드코딩 없음 |
| T-01B-03 (DoS) | appendToken in-place 업데이트로 Zustand set 최소화 |
| T-01B-04 (Info Disclosure) | assertNever 컴파일 가드로 미처리 타입 탐지 |

## Known Stubs

- `ws/dispatch.ts` — `case 'slash_result':` 는 `/{cmd} 완료` 시스템 메시지로만 표시. Phase 2 에서 cmd 별 처리 확장 예정.
- `ws/dispatch.ts` — `case 'quit':` 는 `useApp().exit()` 연동 없음. Phase 3 에서 완성 예정.
- `store/room.ts` — `activeInputFrom` / `activeIsSelf` 는 Phase 3 turn-taking UX 에서 사용 예정.
- `store/confirm.ts` — Phase 2 confirm 다이얼로그 컴포넌트 완성 전까지 payload 저장만.

## Self-Check: PASSED

```
FOUND: ui-ink/src/protocol.ts
FOUND: ui-ink/src/ws/parse.ts
FOUND: ui-ink/src/ws/dispatch.ts
FOUND: ui-ink/src/ws/client.ts
FOUND: ui-ink/src/store/messages.ts
FOUND: ui-ink/src/store/input.ts
FOUND: ui-ink/src/store/status.ts
FOUND: ui-ink/src/store/room.ts
FOUND: ui-ink/src/store/confirm.ts
FOUND: ui-ink/src/store/index.ts
FOUND commit: 459f1b4 (protocol.ts)
FOUND commit: 5c60f1c (store + ws 모듈)
FOUND commit: 220ac55 (ws.ts 교정)
```
