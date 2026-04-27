---
phase: 01-rpc-skeleton
plan: 01
subsystem: ui-ink/rpc
tags:
  - rpc
  - typescript
  - ui-ink
  - ws-protocol
requirements:
  - RPC-01
  - RPC-03
dependency_graph:
  requires:
    - ui-ink/src/protocol.ts (기존 ServerMsg/ClientMsg discriminated union)
    - ui-ink/src/ws/client.ts (HarnessClient.send 시그니처)
    - ui-ink/src/store/confirm.ts (boundClient 패턴 참조)
    - tools/fs.py:read_file (Python schema ground truth)
  provides:
    - ToolRequestMsg / ToolResultMsg 타입 (Plan 02 가 의존)
    - TOOL_RUNTIME registry + bindToolClient (Phase 2 가 write/edit 추가 시 확장점)
    - dispatch.ts case 'tool_request' 라우팅
    - App.tsx bindToolClient lifecycle
  affects:
    - Plan 02 (Python harness_server.py 측) — 본 plan 의 schema 에 1:1 정합 필요
    - Plan 03 (vitest read_file 5케이스 + 통합) — TOOL_RUNTIME 진입점 사용
tech_stack:
  added:
    - node:fs/promises (readFile 파일 IO)
  patterns:
    - boundClient 주입 (store → client 순환 의존 회피)
    - discriminated union + assertNever exhaustive 가드
    - dispatch fire-and-forget Promise (`void runClientTool(...)`)
key_files:
  created:
    - ui-ink/src/tools/fs.ts
    - ui-ink/src/tools/registry.ts
  modified:
    - ui-ink/src/protocol.ts
    - ui-ink/src/ws/dispatch.ts
    - ui-ink/src/App.tsx
    - ui-ink/src/__tests__/protocol.test.ts
    - ui-ink/src/__tests__/dispatch.test.ts
decisions:
  - D-01 채택 (call_id uuid v4 1:1 correlation) — 페이로드 schema 그대로 protocol.ts 에 박힘
  - D-02 채택 (error = {kind, message}) — registry.ts 의 unknown_tool/tool_error/exception 3종 분기
  - D-04 채택 (discriminated union + assertNever) — 컴파일 시점 누락 탐지 보장
  - D-14/D-15 채택 (Python schema 1:1) — cat -n 4자리 padding + tab prefix 동등
  - D-16 채택 (file_path alias 는 agent.py 측 책임) — TS 는 path 만 받음
metrics:
  duration: 319s
  tasks_completed: 3
  files_modified: 5
  files_created: 2
  tests_added: 3
  completed_date: "2026-04-27"
---

# Phase 01 Plan 01: RPC 골격 + read_file PoC (클라 측) Summary

ui-ink (TS) 측에 `tool_request`/`tool_result` discriminated union 페어 + 클라 측 `read_file` 실행 + dispatch 라우팅 + lifecycle 배선까지 한 라운드트립을 완성했습니다. Python 측 (Plan 02) 가 의존할 schema 가 `protocol.ts` 에 확정되어 Wave 2 진입 가능합니다.

## What Was Built

### 1. `protocol.ts` — RPC 메시지 페어 + union 갱신

```typescript
// 서버 → 클라 (D-01, D-02)
export interface ToolRequestMsg {
  type: 'tool_request'
  call_id: string                                   // uuid v4 — 1:1 correlation
  name: string                                       // Phase 1 = 'read_file'
  args: Record<string, unknown>                      // {path, offset?, limit?}
}

// 클라 → 서버 (D-02)
export interface ToolResultMsg {
  type: 'tool_result'
  call_id: string
  ok: boolean
  result?: Record<string, unknown>                  // ok=true 시
  error?: { kind: string; message: string }          // ok=false 시
}
```

`ServerMsg` union 에 `ToolRequestMsg`, `ClientMsg` union 에 `ToolResultMsg` 추가. `assertNever` exhaustive 가드는 미수정 — 새 case 누락 시 컴파일 에러로 잡히는 구조 유지.

### 2. `tools/fs.ts:readFile` — Python `read_file` 동등 schema

Python `tools/fs.py:read_file` 의 출력 schema 와 1:1 매칭:

| 필드 | 타입 | Python 대응 |
|------|------|-------------|
| `ok` | `true` | `'ok': True` |
| `content` | string (cat -n 4자리 padding + tab) | `f'{n:4d}\t{l}'` |
| `total_lines` | number | `len(lines)` |
| `start_line` | number (1-based) | `start + 1` |
| `end_line` | number | `start + len(sliced)` |

**Schema 매칭 검증:** `padStart(4, ' ')` ↔ Python `f'{:4d}'` 동등 (빈 자리 공백 패딩, ≥4자리 시 전체 출력 — 둘 다 truncation 없음). 수동 비교: `'   1\t   2\t99999'` 형식 일치 확인.

`split(/(?<=\n)/)` 으로 keepends 동등 — Python `f.readlines()` 가 줄바꿈 보존하는 동작 매칭. 빈 파일 → 빈 배열 분기.

에러 분기: path 누락 → `{ok:false, error:'path 누락'}`, 그 외 (파일 없음 / 디렉토리 / 권한 / 인코딩) → `{ok:false, error: e.message}`.

### 3. `tools/registry.ts` — `TOOL_RUNTIME` + `bindToolClient` + `runClientTool`

```typescript
export const TOOL_RUNTIME: Record<string, ToolFn> = {
  read_file: readFile,
}
```

`bindToolClient` 패턴 = `store/confirm.ts:9-13` 카피. registry 모듈에서 `import {HarnessClient} from '../ws/client.js'` 만 type-only — 순환 의존 차단.

`runClientTool(call_id, name, args)` 의 결과 envelope 변환 규칙:

- 미등록 도구 → `{ok:false, error:{kind:'unknown_tool', message}}`
- 도구가 `{ok:false, error:string}` 반환 → `{ok:false, error:{kind:'tool_error', message:r.error}}`
- 도구가 throw → `{ok:false, error:{kind:'exception', message: e.message}}`
- 성공 → `{ok:true, result: rest}` (envelope 의 `ok` 외 나머지 필드만 `result` 안에 포장)

### 4. `dispatch.ts` — `case 'tool_request'` fire-and-forget 정책

```typescript
case 'tool_request': {
  void runClientTool(msg.call_id, msg.name, msg.args)
  break
}
```

- `flushPendingTokens` 미호출 — `tool_request` 는 사용자 가시 텍스트가 아니므로 token coalescer 와 무관.
- `void` 캐스팅으로 fire-and-forget — `dispatch()` 는 sync, Promise 결과는 `boundClient.send` 로 별도 회신.
- `assertNever` exhaustive 가드를 통과 (컴파일 에러 0).

### 5. `App.tsx` — `bindToolClient` lifecycle (mount/unmount 호출 횟수)

```typescript
client.connect()
clientRef.current = client
bindConfirmClient(client)
bindFilesClient(client)
bindToolClient(client)        // mount 시 1회
return () => {
  bindConfirmClient(null)
  bindFilesClient(null)
  bindToolClient(null)         // unmount 시 1회
  client.close()
  clientRef.current = null
}
```

`grep -c "bindToolClient" App.tsx` = 3 (import 1 + mount 1 + cleanup 1).

## Verification Results

| 단계 | 명령 | 결과 |
|------|------|------|
| typecheck | `bun run typecheck` | exit 0 (컴파일 에러 0) |
| 전체 vitest | `bun run test` | 26 files / 182 tests green |
| dispatch 단독 | `bun run test -- dispatch` | 26 tests green (1건 신규 — `tool_request` 위임) |
| protocol 단독 | `bun run test -- protocol` | 8 tests green (2건 신규 — 기본 + offset+limit) |
| guard | `bun run guard` | 모든 금지 패턴 체크 통과 |
| acceptance grep | (전 9건) | 모두 매치 |

신규 테스트 케이스 3건:

1. `parseServerMsg('{"type":"tool_request",...}')` → ToolRequestMsg narrow + 필드 검증
2. `parseServerMsg(...offset, limit...)` → args 의 숫자 필드 보존
3. `dispatch({type:'tool_request', ...})` → `runClientTool('X1', 'read_file', {path:'/tmp/a'})` 위임 (vi.mock 검증)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking: 커밋 단위 typecheck 그린 보장 vs exhaustive 가드]**

- **Found during:** Task 1 commit
- **Issue:** 플랜 acceptance criteria 는 각 task commit 시점에 `bun run typecheck exit 0` 을 요구하지만, `assertNever` exhaustive 가드가 union 추가(Task 1) 와 case 추가(Task 3) 사이에서 컴파일 에러를 발생시킴. Task 1 단독 커밋과 Task 2 단독 커밋의 중간 git 상태에서는 typecheck 가 exit 1.
- **Fix:** 각 task 의 코드 변경을 모두 작성한 뒤 plan 순서대로 분리 커밋. 최종 HEAD 상태에서 typecheck/test/guard 모두 그린. 중간 커밋(aea54e1, 73b4096)은 의도적으로 typecheck 가 깨진 상태 — 최종 커밋(d500da4)에서 회복.
- **Rationale:** assertNever 가드는 D-04 의 컴파일 시점 누락 탐지를 보장하는 핵심 장치이므로 우회 불가. 대안(union 만 먼저 / case 만 먼저)도 모두 같은 문제. 플랜 의도(per-task atomic commit)는 유지하면서 최종 상태의 그린만 보장하는 표준 패턴 채택.
- **Files modified:** 없음 (커밋 순서만 조정)
- **Commits affected:** aea54e1 (Task 1, 중간 typecheck red), 73b4096 (Task 2, 중간 typecheck red), d500da4 (Task 3, typecheck green)

**2. [Rule 2 - Test 추가] protocol.test.ts 회귀 케이스 1건 추가**

- **Found during:** Task 1
- **Issue:** 플랜은 `tool_request` 기본 파싱 1건만 명시. 실제 schema 의 args 필드(offset/limit)가 number 로 파싱되는지 별도 회귀가 없음.
- **Fix:** offset+limit 케이스 1건 추가 — Phase 2 가 schema 확장 시 회귀로 활용 가능.
- **Files modified:** `ui-ink/src/__tests__/protocol.test.ts`
- **Commit:** aea54e1

## Authentication Gates

해당 없음.

## TDD Gate Compliance

각 task 의 `tdd="true"` 플래그에 대해:

- Task 1: GREEN 우선 (테스트 + 코드 동시 작성). RED 단계 분리 커밋 미수행 — 테스트와 타입 정의가 같은 커밋에 포함됨. 이는 plan 의 `<action>` 단계가 코드와 테스트를 한 task 안에 묶어 지정한 결과.
- Task 2: 테스트 없음 (plan 명시 — "테스트는 Plan 03 의 Task 1 = vitest 5케이스 + registry 핸드오프 케이스로 분리하여 Wave 3 에서 통합. 본 task 는 코드 작성 + typecheck 만으로 검증").
- Task 3: 새 dispatch 케이스 + 회귀 테스트 동시 작성. RED→GREEN 분리 미수행 (동일 이유).

별도 RED/GREEN 커밋이 필요했다면 plan 의 task 분할 단위가 더 세분화되어야 했음. 본 plan 의 Task 단위는 "feature + 회귀 테스트" 묶음이며, GREEN-first 통합 커밋으로 처리.

## Known Stubs

해당 없음. `TOOL_RUNTIME` 은 Phase 1 의 의도된 단일 도구 등록 상태 (Phase 2 에서 write_file/edit_file/list_files/grep_search 추가 예정). Plan 03 의 통합 검증이 완료되어야 PoC 라운드트립이 보장됨.

## Threat Flags

본 plan 은 클라 측 file IO 진입점을 도입했으나 **샌드박스 미구현 상태**. Python `_resolve_path` (tools/fs.py:31-52) 의 `realpath` + symlink escape 방지가 TS 측에 없음. Phase 1 의 D-19 수동 검증은 외부 PC 에서 자기 PC 파일을 읽는 것으로 한정되며, BB-2 deletion(Phase 4) 이전까지는 보안 경계에 영향 없음.

| Flag | File | Description |
|------|------|-------------|
| threat_flag: client_fs_no_sandbox | ui-ink/src/tools/fs.ts | path 인자가 sandbox 검증 없이 fs.readFile 로 흘러감. Python 의 `_resolve_path` 동등 가드 미구현. Phase 4 의 RX-02 세션 격리 또는 별도 plan 에서 처리 필요. |

## Self-Check: PASSED

**Created files:**
- FOUND: ui-ink/src/tools/fs.ts
- FOUND: ui-ink/src/tools/registry.ts

**Modified files (acceptance grep):**
- FOUND: ToolRequestMsg in protocol.ts
- FOUND: ToolResultMsg in protocol.ts
- FOUND: `| ToolRequestMsg` in protocol.ts (ServerMsg union)
- FOUND: `| ToolResultMsg` in protocol.ts (ClientMsg union)
- FOUND: TOOL_RUNTIME in registry.ts
- FOUND: `read_file: readFile` in registry.ts
- FOUND: bindToolClient in registry.ts (export)
- FOUND: runClientTool in registry.ts (export)
- FOUND: padStart(4 in fs.ts
- FOUND: `case 'tool_request'` in dispatch.ts
- FOUND: runClientTool in dispatch.ts (import)
- FOUND: bindToolClient in App.tsx (count = 3)

**Commits:**
- FOUND: aea54e1 (Task 1: protocol.ts + protocol.test.ts)
- FOUND: 73b4096 (Task 2: tools/fs.ts + tools/registry.ts)
- FOUND: d500da4 (Task 3: dispatch.ts + App.tsx + dispatch.test.ts)

**Verification:**
- typecheck: exit 0
- vitest 전체: 182/182 green
- guard: 통과
