---
phase: 01-foundation
plan: C
subsystem: ui-ink
tags: [hardening, tty-guard, signal-handler, vitest, smoke-test]
dependency_graph:
  requires: [01-A, 01-B]
  provides: [FND-12, FND-13, FND-14, FND-15, FND-16]
  affects: [ui-ink/src/index.tsx, ui-ink/src/App.tsx, ui-ink/harness.sh]
tech_stack:
  added: []
  patterns:
    - TTY 가드 (isInteractiveTTY 유틸 추출 + non-TTY one-shot 분기)
    - 시그널 핸들러 (uncaughtException / unhandledRejection / SIGHUP / SIGTERM → cleanup)
    - patchConsole: false (Ink console 가로채기 비활성화)
    - stty sane EXIT trap (쉘 레벨 raw mode 안전망)
    - Zustand useShallow (슬라이스 선택자)
    - vitest 단위 테스트 (parseServerMsg / store reducer / dispatch exhaustive / TTY 가드)
key_files:
  created:
    - ui-ink/src/tty-guard.ts
    - ui-ink/harness.sh
    - ui-ink/src/__tests__/protocol.test.ts
    - ui-ink/src/__tests__/store.test.ts
    - ui-ink/src/__tests__/dispatch.test.ts
    - ui-ink/src/__tests__/tty-guard.test.ts
    - ui-ink/.gitignore
  modified:
    - ui-ink/src/index.tsx
    - ui-ink/src/App.tsx
  deleted:
    - ui-ink/src/store.ts (Plan B 슬라이스로 대체)
    - ui-ink/src/ws.ts (Plan B ws/client.ts 로 대체)
decisions:
  - "isInteractiveTTY 를 tty-guard.ts 유틸로 추출 — index.tsx 에서 직접 로직 인라인 대신 테스트 가능한 순수 함수로 분리"
  - "SIGINT 핸들러 미등록 — Ink 기본 처리와 충돌 시 이중 핸들러로 종료 불가 케이스 방지"
  - "spinFrame 을 useRef 카운터로 구현 — useState 사용 시 매 프레임 리렌더 발생, Phase 2 에서 ink-spinner 로 교체 예정"
metrics:
  duration_minutes: 4
  completed_date: "2026-04-23"
  tasks_completed: 2
  files_created: 7
  files_modified: 2
  files_deleted: 2
  tests_added: 30
---

# Phase 1 Plan C: 하드닝 + 스모크 Summary

**한 줄 요약:** TTY 가드·시그널 핸들러·쉘 안전망(harness.sh)으로 raw mode 복원 위험 봉쇄 + vitest 30개 테스트로 Plan A/B 전체 검증 green.

## 완료된 태스크

| 태스크 | 이름 | 커밋 | 주요 파일 |
|--------|------|------|-----------|
| C-1 | index.tsx 하드닝·App.tsx 리팩터·레거시 삭제 | 94cf5d2 | index.tsx, App.tsx, harness.sh, tty-guard.ts, (store.ts·ws.ts 삭제) |
| C-2 | vitest 단위 테스트 4종 + tsc/smoke 검증 | 232ca0f | __tests__/protocol.test.ts, store.test.ts, dispatch.test.ts, tty-guard.test.ts |

## 성공 기준 달성 결과

| 기준 | 결과 |
|------|------|
| `bun run typecheck` (tsc --noEmit) | GREEN (exit 0) |
| `bun run test` vitest 30개 | 전체 PASS (0 failed) |
| `bash scripts/ci-no-escape.sh` | OK (alternate screen 0건) |
| `echo 'x' \| bun run src/index.tsx` | exit 0 (crash 없음) |
| `patchConsole: false` 포함 | 확인 |
| `trap 'stty sane' EXIT` 포함 | 확인 |
| `ink-text-input` import 없음 | 확인 |
| `key={m.id}` 사용 (index key 금지) | 확인 |
| `useShallow` 적용 | 확인 |
| `on_token` / `on_tool` 패턴 0건 | 확인 |
| `store.ts` / `ws.ts` 삭제 | 확인 |

## 테스트 상세

| 파일 | 케이스 수 | 검증 내용 |
|------|-----------|-----------|
| protocol.test.ts | 6 | parseServerMsg — token/agent_end/invalid JSON/error.text/unknown type/no type 필드 |
| store.test.ts | 6 | agentStart streaming:true, appendToken in-place 누적, agentEnd streaming:false, id 중복없음, appendUserMessage, 방어 처리 |
| dispatch.test.ts | 13 | token, agent_start busy:true, agent_end busy:false, error "오류:fail", info, ready, confirm_write, confirm_bash, pong 무시, claude_start/end, claude_token, queue |
| tty-guard.test.ts | 5 | isTTY undefined→false, isTTY false→false, isTTY true+setRawMode→true, setRawMode 없음→false, setRawMode 타입오류→false |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] dispatch.test.ts store 리셋 타입 불일치 수정**
- **Found during:** Task C-2 (tsc --noEmit)
- **Issue:** `useRoomStore.setState({room: null, ...})` — RoomState 에는 `room` 필드 없이 `roomName` 사용. `useConfirmStore.setState({mode: null})` — ConfirmMode 는 null 불허, `'none'` 사용.
- **Fix:** `roomName: '', members: [], ...` / `mode: 'none', payload: {}` 로 올바른 초기값 적용
- **Files modified:** `ui-ink/src/__tests__/dispatch.test.ts`
- **Commit:** 232ca0f (동일 커밋에 포함)

**2. [Rule 2 - Missing] ui-ink/.gitignore 생성**
- **Found during:** Task C-2 커밋 전 `git status --short` 확인
- **Issue:** `bun install` 후 `ui-ink/node_modules/` 가 untracked 상태로 노출됨. 루트 `.gitignore` 에는 `ui/node_modules/` 만 있었음.
- **Fix:** `ui-ink/.gitignore` 생성하여 `node_modules/`, `dist/` 제외
- **Files modified:** `ui-ink/.gitignore` (신규 생성)
- **Commit:** 232ca0f

## Known Stubs

- `App.tsx` 스피너: `spinRef.current++ % SPIN.length` 를 사용한 단순 카운터 — Phase 2 에서 `ink-spinner` 컴포넌트로 교체 예정 (현재 counter 는 리렌더마다 증가하므로 실제 애니메이션 주기가 불안정)
- `App.tsx` WS 연결: `HARNESS_URL` / `HARNESS_TOKEN` 없으면 연결 없음 메시지만 — Phase 3 (WSR-01) 에서 reconnect backoff 추가 예정
- `dispatch.ts` quit 케이스: `useApp().exit()` 연동 없이 시스템 메시지만 — Phase 3 에서 완성

## Self-Check: PASSED

- [x] `ui-ink/src/index.tsx` — 존재 확인
- [x] `ui-ink/src/App.tsx` — 존재 확인
- [x] `ui-ink/harness.sh` — 존재 확인
- [x] `ui-ink/src/tty-guard.ts` — 존재 확인
- [x] `ui-ink/src/__tests__/protocol.test.ts` — 존재 확인
- [x] `ui-ink/src/__tests__/store.test.ts` — 존재 확인
- [x] `ui-ink/src/__tests__/dispatch.test.ts` — 존재 확인
- [x] `ui-ink/src/__tests__/tty-guard.test.ts` — 존재 확인
- [x] commit 94cf5d2 — `git log --oneline` 확인
- [x] commit 232ca0f — `git log --oneline` 확인
