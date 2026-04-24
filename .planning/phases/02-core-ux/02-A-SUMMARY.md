---
phase: 02-core-ux
plan: A
subsystem: store-protocol-dispatch
tags: [store, zustand, protocol, dispatch, tdd]
dependency_graph:
  requires: []
  provides:
    - completedMessages/activeMessage 분리 계약 (messages.ts)
    - history/slashOpen/persistence 입력 계약 (input.ts)
    - stickyDeny/resolve WS 바인딩 confirm 계약 (confirm.ts)
    - CancelMsg 프로토콜 타입 (protocol.ts)
    - slash_result cmd별 dispatch 분기 (dispatch.ts)
  affects:
    - ui-ink/src/App.tsx (messages→completedMessages+activeMessage)
    - Plan B 컴포넌트 계층 전체 (이 계약 위에서 조립)
tech_stack:
  added: []
  patterns:
    - Zustand store slice (completedMessages/activeMessage 분리)
    - 모듈 스코프 바인딩 주입 (bindConfirmClient)
    - 파일 persistence (node:fs append-only)
    - slash_result 화이트리스트 switch (T-02A-01)
key_files:
  created:
    - ui-ink/src/__tests__/store.messages.test.ts
    - ui-ink/src/__tests__/store.input.test.ts
    - ui-ink/src/__tests__/store.confirm.test.ts
  modified:
    - ui-ink/src/store/messages.ts
    - ui-ink/src/store/input.ts
    - ui-ink/src/store/confirm.ts
    - ui-ink/src/store/status.ts
    - ui-ink/src/protocol.ts
    - ui-ink/src/ws/dispatch.ts
    - ui-ink/src/ws/client.ts
    - ui-ink/src/App.tsx
    - ui-ink/src/__tests__/dispatch.test.ts
    - ui-ink/src/__tests__/components.statusbar.test.tsx
decisions:
  - "completedMessages/activeMessage 분리: agent_end 수신 시에만 completedMessages 에 push (D-04, RND-02 Static 안정성)"
  - "bindConfirmClient 모듈 스코프 바인딩: store→client 순환 의존 회피, client.ts open/close 에서 자동 관리"
  - "~/.harness/history.txt 파일 persistence: Python REPL 동일 포맷(줄 단위), 실패 swallow"
  - "cplan_confirm resolve: 서버 응답 타입 미존재로 로컬 상태만 초기화 (Phase 3 재방문)"
  - "slash_result cmd 화이트리스트 switch: unknown cmd appendSystemMessage fallback (T-02A-01)"
metrics:
  duration: "약 7분"
  completed_date: "2026-04-24"
  tasks_completed: 6
  tasks_total: 6
  files_modified: 10
  tests_added: 34
  tests_total: 80
---

# Phase 2 Plan A: store/protocol/dispatch 계층 업그레이드 Summary

**한 줄 요약:** completedMessages/activeMessage 분리·history persistence·stickyDeny·CancelMsg·slash_result cmd 분기를 단일 계약으로 완성 — Plan B 컴포넌트 조립의 기반

## 완료 태스크

| 태스크 | 설명 | 커밋 | 테스트 |
|--------|------|------|--------|
| A-1 | messages.ts completedMessages/activeMessage 분리 | b295697 | 7개 |
| A-2 | input.ts history + slashOpen + 파일 persistence | e6065ff | 13개 |
| A-3 | confirm.ts stickyDeny + resolve + WS 응답 연결 | 1586af1 | 8개 |
| A-4 | protocol.ts CancelMsg 추가 | 1d534a4 | tsc 확인 |
| A-5 | dispatch.ts slash_result cmd별 분기 확장 | b432012 | 6개 신규 |
| A-6 | 기존 테스트 회귀 수정 + tsc/lint 통과 | 5fac10b | 80/80 |

## Plan B 가 사용할 Public API

### messages.ts

```typescript
// completedMessages: <Static> 컴포넌트에 전달 (append-only, agent_end 후에만 push)
// activeMessage: 스트리밍 슬롯에 직접 렌더 (null이면 숨김)
const {completedMessages, activeMessage} = useMessagesStore(useShallow(s => ({
  completedMessages: s.completedMessages,
  activeMessage: s.activeMessage,
})))
```

### input.ts

```typescript
// history 순회: historyUp() / historyDown() → buffer 자동 갱신
// 슬래시 팝업 표시: setSlashOpen(true/false)
// 마운트 시: useEffect(() => { useInputStore.getState().hydrate() }, [])
// 전송 후: pushHistory(text) → ~/.harness/history.txt 자동 append
export {loadHistory, appendHistory, HISTORY_PATH} from './store/input.js'
```

### confirm.ts

```typescript
// 다이얼로그 accept/deny: useConfirmStore.getState().resolve(accept)
// 재질문 억제 체크: isDenied('path', path) / isDenied('cmd', command)
// sticky deny 조회: deniedPaths, deniedCmds Set
```

### protocol.ts

```typescript
// Ctrl+C busy 시 전송:
client.send({type: 'cancel'})
```

### status.ts (신규 개별 setter)

```typescript
status.setWorkingDir(path)
status.setModel(model)
status.setMode(mode)
```

## ~/.harness/history.txt 파일 포맷 및 마운트 가이드

- **포맷**: 한 줄당 한 항목, trailing newline, UTF-8 (Python readline 호환)
- **경로**: `~/.harness/history.txt` (`HISTORY_PATH` export로 테스트 override 가능)
- **읽기**: 가장 위가 오래된 것 → oldest-first 배열로 반환, max 500개
- **쓰기**: `pushHistory()` 호출 시 `appendFileSync`로 즉시 한 줄 추가
- **App.tsx 마운트 패턴**:
  ```typescript
  useEffect(() => {
    useInputStore.getState().hydrate()  // history.txt → store.history 로드
  }, [])
  ```

## 변경된 Store 계약 diff 요약

| 스토어 | 변경 전 | 변경 후 |
|--------|---------|---------|
| messages | `messages: Message[]` (단일 배열) | `completedMessages: Message[]` + `activeMessage: Message\|null` |
| input | `buffer`, `setBuffer`, `clearBuffer` | + `history`, `historyIndex`, `slashOpen`, `pushHistory`, `historyUp`, `historyDown`, `setSlashOpen`, `hydrate` |
| confirm | `mode`, `payload`, `setConfirm`, `clearConfirm` | + `deniedPaths`, `deniedCmds`, `addDenied`, `isDenied`, `clearDenied`, `resolve` |
| status | `setState` batch 업데이트만 | + `setWorkingDir`, `setModel`, `setMode` 개별 setter |
| protocol | `ClientMsg` 4종 유니온 | + `CancelMsg` 추가 (5종) |

## 추가된 테스트 수

- store.messages.test.ts: 7개 신규
- store.input.test.ts: 13개 신규
- store.confirm.test.ts: 8개 신규
- dispatch.test.ts: 6개 신규 (slash_result cmd별)
- **Plan A 신규 합계: 34개**
- **전체: 80개 (Phase 1 잔존 포함)**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] dispatch.test.ts 기존 파일이 이미 completedMessages 계약으로 업데이트되어 있었음**
- **Found during:** A-5
- **Issue:** 기존 dispatch.test.ts가 `messages` 대신 `completedMessages`를 참조하도록 이미 수정된 상태였음 — 충돌 없이 slash_result 테스트 6개만 추가
- **Fix:** 기존 파일 패턴 유지, slash_result describe 블록 append
- **Commit:** b432012

**2. [Rule 2 - Missing] App.tsx legacy messages 접근자 교체**
- **Found during:** A-6
- **Issue:** App.tsx가 `s.messages`를 사용해 tsc 에러 발생
- **Fix:** `completedMessages + activeMessage` 분리 구조로 교체 (Plan B 전면 교체 전 임시)
- **Commit:** 5fac10b

**3. [Rule 1 - Bug] components.statusbar.test.tsx ESLint no-control-regex 오류**
- **Found during:** A-6 lint 실행
- **Issue:** `\x1b` 제어 문자를 정규식에 직접 사용 → ESLint 금지 규칙
- **Fix:** `// eslint-disable-next-line no-control-regex` 주석 추가
- **Commit:** 5fac10b

**4. [Rule 3 - Blocking] confirm.ts 파일이 이미 발전된 버전(bindConfirmClient 포함)으로 존재**
- **Found during:** A-3 구현 시작 시
- **Issue:** Phase 1 이후 다른 에이전트가 중간 버전을 생성해 두었음
- **Fix:** 기존 내용 확인 후 완전한 stickyDeny + DenyKind 버전으로 교체

## Known Stubs

없음 — Plan A 는 store/protocol/dispatch 계층만 대상이며 모든 API가 실제 동작함.

## Threat Flags

없음 — plan의 threat_model에서 이미 식별된 경계(T-02A-01 ~ T-02A-06) 내에서만 변경.

## Self-Check

모든 파일 존재 확인: PASSED
모든 커밋 존재 확인: PASSED (b295697, e6065ff, 1586af1, 1d534a4, b432012, 5fac10b)
bun run test: 80/80 PASSED
bunx tsc --noEmit: PASSED (에러 0)
bun run lint: PASSED (경고/에러 0)

**Self-Check: PASSED**
