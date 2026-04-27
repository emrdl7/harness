---
phase: 01-foundation
verified: 2026-04-24T07:31:30Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "tsc --noEmit green · ESLint green (process.stdout.write/console.log/<div>/child_process.spawn 0건) · vitest 단위 테스트 green — @typescript-eslint/parser 설치 및 eslint.config.js 파서 설정 완료, bun run lint exit 0 확인"
    - "kill -9 후 터미널 복구, 5개 시그널 경로에서 setRawMode(false) + 커서 복원 + stdin.pause() 수행 — SIGINT 핸들러 process.on('SIGINT', () => cleanup(0)) 추가됨"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "HARNESS_URL=ws://127.0.0.1:7891 HARNESS_TOKEN=<token> HARNESS_ROOM=<room> bun start 실행 후 'hello' 입력"
    expected: "assistant 토큰이 스트리밍되며 in-place 누적, agent_end 수신 후 busy 상태 해제 및 입력 프롬프트 복귀"
    why_human: "로컬 harness_server.py 서버 실행 중이어야 하고 실제 Ollama 모델 응답이 필요한 end-to-end 시나리오. 자동화 불가."
---

# Phase 1: Foundation 검증 보고서 (재검증)

**Phase 목표:** ui-ink 스켈레톤을 Phase 2+ 빌드가 가능한 상태로 끌어올린다. 의존성 세대 격차 · 프로토콜 이름 불일치 · 하드닝 부재를 단일 phase 로 해소해 "`bun start` → 연결 → 토큰 스트리밍 → `agent_end`" end-to-end 스모크가 통과하는 상태를 만든다.

**검증 시각:** 2026-04-24T07:31:30Z
**상태:** human_needed
**재검증:** 예 — 2건 갭 수정 후 재검증 (이전: 2026-04-23T22:25:00Z, gaps_found)

---

## 재검증 요약

| 갭 | 이전 상태 | 수정 내용 | 현재 상태 |
|---|---------|---------|---------|
| FND-10 ESLint TypeScript 파서 미설치 | ✗ PARTIAL | `@typescript-eslint/parser` 설치 + `eslint.config.js`에 `languageOptions.parser: tsParser` 추가 | ✓ CLOSED |
| FND-13 SIGINT 핸들러 미등록 | ✗ PARTIAL | `index.tsx` 라인 42에 `process.on('SIGINT', () => cleanup(0))` 추가 | ✓ CLOSED |

---

## 목표 달성 여부

### 관찰 가능한 진실 (Observable Truths)

| # | 진실 | 상태 | 근거 |
|---|------|------|------|
| 1 | `bun start` 후 WS 연결 → 토큰 스트리밍 → `agent_end` 수신 후 프롬프트 복귀 (FND-16) | ? HUMAN | 로컬 harness_server.py 실행 필요 — 자동 검증 불가 |
| 2 | `tsc --noEmit` green · ESLint green · vitest green | ✓ VERIFIED | tsc exit 0 · `bun run lint` exit 0 (--max-warnings=0) · vitest 4 files / 30 tests pass |
| 3 | `grep '\x1b[?1049\|?1000' ui-ink/src/` 빈 결과 · non-TTY one-shot crash 없음 | ✓ VERIFIED | ci-no-escape.sh "OK" · `echo 'x' | bun run src/index.tsx` exit 0 |
| 4 | 5개 시그널 경로에서 setRawMode(false) + 커서 복원 + stdin.pause() 수행 | ✓ VERIFIED | uncaughtException · unhandledRejection · SIGHUP · SIGTERM · SIGINT — 5개 모두 cleanup() 호출 확인 (index.tsx 라인 29-42) |
| 5 | `src/protocol.ts` 에 25+ ServerMsg discriminated union + `src/ws/dispatch.ts` exhaustive switch | ✓ VERIFIED | protocol.ts 25종 ServerMsg union + assertNever 헬퍼, dispatch.ts 25 case + default assertNever(msg) |

**점수:** 5/5 진실 검증됨 (진실 1은 로컬 서버 필요 — human 검증 항목)

---

### 필수 아티팩트 검증

| 아티팩트 | 목적 | 존재 | 실질 내용 | 연결 | 상태 |
|---------|------|------|-----------|------|------|
| `ui-ink/package.json` | 의존성 선언 | ✓ | ink@7.0.1, react@19.2.5, zustand@5.0.12, ws@8.20.0, @typescript-eslint/parser devDep | ✓ bun install | ✓ VERIFIED |
| `ui-ink/tsconfig.json` | TypeScript 빌드 설정 | ✓ | "jsx":"react-jsx", "moduleResolution":"bundler", "strict":true, lib:["ES2022"] | ✓ tsc --noEmit exit 0 | ✓ VERIFIED |
| `ui-ink/eslint.config.js` | ESLint 금지 규칙 | ✓ | @typescript-eslint/parser import + languageOptions.parser: tsParser 설정, no-restricted-syntax 7개 규칙 | ✓ bun run lint exit 0 | ✓ VERIFIED |
| `ui-ink/scripts/ci-no-escape.sh` | alternate screen CI 가드 | ✓ | 1049h/1000h grep, SCRIPT_DIR 상대 경로 | ✓ "OK" 출력 | ✓ VERIFIED |
| `ui-ink/src/protocol.ts` | ServerMsg/ClientMsg union | ✓ | 25종 ServerMsg, 5종 ClientMsg, assertNever 헬퍼 | ✓ dispatch.ts에서 import | ✓ VERIFIED |
| `ui-ink/src/ws/client.ts` | HarnessClient 클래스 | ✓ | connect/send/close/heartbeat(30s), x-harness-token/room 헤더 | ✓ App.tsx useRef | ✓ VERIFIED |
| `ui-ink/src/ws/parse.ts` | JSON → ServerMsg 파서 | ✓ | JSON.parse 실패 시 null, type 없으면 null | ✓ client.ts ws.on('message') | ✓ VERIFIED |
| `ui-ink/src/ws/dispatch.ts` | exhaustive switch 디스패처 | ✓ | 25개 case, default assertNever(msg) | ✓ client.ts dispatch 호출 | ✓ VERIFIED |
| `ui-ink/src/store/messages.ts` | 메시지 슬라이스 | ✓ | appendToken in-place 패턴, crypto.randomUUID() id | ✓ dispatch.ts/App.tsx | ✓ VERIFIED |
| `ui-ink/src/store/input.ts` | 입력 슬라이스 | ✓ | buffer/setBuffer/clearBuffer | ✓ App.tsx | ✓ VERIFIED |
| `ui-ink/src/store/status.ts` | 상태 슬라이스 | ✓ | connected/busy/workingDir/model/mode | ✓ dispatch.ts/App.tsx | ✓ VERIFIED |
| `ui-ink/src/store/room.ts` | 룸 슬라이스 | ✓ | roomName/members/activeInputFrom/activeIsSelf | ✓ dispatch.ts | ✓ VERIFIED |
| `ui-ink/src/store/confirm.ts` | confirm 슬라이스 | ✓ | ConfirmMode/payload/setConfirm/clearConfirm | ✓ dispatch.ts | ✓ VERIFIED |
| `ui-ink/src/store/index.ts` | 통합 re-export | ✓ | 6개 슬라이스 전부 re-export | ✓ | ✓ VERIFIED |
| `ui-ink/src/index.tsx` | TTY 가드 + 시그널 핸들러 + render | ✓ | patchConsole:false, isInteractiveTTY, cleanup, 5개 시그널 모두 등록 (SIGINT 포함) | ✓ App.tsx render | ✓ VERIFIED |
| `ui-ink/src/tty-guard.ts` | TTY 가드 유틸 | ✓ | isInteractiveTTY 순수 함수 | ✓ index.tsx | ✓ VERIFIED |
| `ui-ink/harness.sh` | 쉘 안전망 | ✓ | trap 'stty sane' EXIT, exec bun run | ✓ | ✓ VERIFIED |
| `ui-ink/src/__tests__/protocol.test.ts` | parseServerMsg 테스트 | ✓ | 6개 케이스 | ✓ vitest pass | ✓ VERIFIED |
| `ui-ink/src/__tests__/store.test.ts` | store reducer 테스트 | ✓ | agentStart/appendToken/agentEnd/id 중복없음 | ✓ vitest pass | ✓ VERIFIED |
| `ui-ink/src/__tests__/dispatch.test.ts` | dispatch exhaustive 테스트 | ✓ | 13개 케이스 | ✓ vitest pass | ✓ VERIFIED |
| `ui-ink/src/__tests__/tty-guard.test.ts` | TTY 가드 테스트 | ✓ | 5개 케이스 | ✓ vitest pass | ✓ VERIFIED |

---

### 핵심 연결 검증 (Key Link Verification)

| From | To | Via | 상태 | 근거 |
|------|----|-----|------|------|
| `ws/client.ts` | `ws/dispatch.ts` | ws.on('message') 콜백 | ✓ WIRED | dispatch(msg) 호출 확인됨 |
| `ws/dispatch.ts` | `store/*.ts` | useXxxStore.getState() | ✓ WIRED | messages/status/room/confirm 4개 store 직접 호출 |
| `ws/parse.ts` | `protocol.ts` | ServerMsg 반환 타입 | ✓ WIRED | import type {ServerMsg} from '../protocol.js' |
| `src/index.tsx` | `src/App.tsx` | render(<App/>, {patchConsole:false}) | ✓ WIRED | patchConsole:false 확인 |
| `App.tsx` | `store/messages.ts` | useMessagesStore(useShallow(...)) | ✓ WIRED | useShallow 적용 확인 |
| `App.tsx` | `ws/client.ts` | useRef<HarnessClient> + useEffect | ✓ WIRED | HARNESS_URL/TOKEN 환경변수 기반 조건부 연결 |
| `eslint.config.js` | `src/*.ts/*.tsx` | @typescript-eslint/parser + no-restricted-syntax | ✓ WIRED | bun run lint exit 0, --max-warnings=0 통과 |
| `harness.sh` | `src/index.tsx` | exec bun run + trap 'stty sane' EXIT | ✓ WIRED | stty sane EXIT trap 확인 |

---

### 데이터 흐름 추적 (Level 4)

| 아티팩트 | 데이터 변수 | 소스 | 실제 데이터 흐름 | 상태 |
|---------|-----------|------|----------------|------|
| `App.tsx` | messages | useMessagesStore | dispatch.ts → appendToken/agentStart/agentEnd, 서버 WS 이벤트에서 실데이터 | ✓ FLOWING |
| `App.tsx` | connected | useStatusStore | dispatch.ts → setConnected(true) on 'ready' event | ✓ FLOWING |
| `App.tsx` | busy | useStatusStore | dispatch.ts → setBusy(true/false) on agent_start/agent_end | ✓ FLOWING |
| `App.tsx` | buffer | useInputStore | useInput 훅 → setBuffer on keypress | ✓ FLOWING |

---

### 동작 점검 (Behavioral Spot-checks)

| 동작 | 명령 | 결과 | 상태 |
|------|------|------|------|
| tsc --noEmit | `bun run typecheck` | exit code 0, 출력 없음 | ✓ PASS |
| vitest 단위 테스트 | `bun run test` | 4 files · 30 tests · 0 failed | ✓ PASS |
| CI escape 가드 | `bash scripts/ci-no-escape.sh` | "OK: alternate screen / mouse tracking escape 코드 없음" | ✓ PASS |
| non-TTY one-shot | `echo 'x' \| bun run src/index.tsx` | exit code 0, 안내 메시지 출력 | ✓ PASS |
| ESLint (재검증) | `bun run lint` | exit code 0, --max-warnings=0 통과, 경고 0건 | ✓ PASS |

---

### 요구사항 커버리지

| REQ-ID | 플랜 | 설명 | 상태 | 근거 |
|--------|------|------|------|------|
| FND-01 | A | ink-text-input 제거, ink@7/react@19/zustand@5 bump | ✓ SATISFIED | package.json 확인됨, ink-text-input 0건 |
| FND-02 | A | @inkjs/ui, ink-spinner 등 추가 + 스모크 | ✓ SATISFIED | package.json에 전부 선언됨 |
| FND-03 | B | on_token/on_tool/error.message 교정 | ✓ SATISFIED | src/ 전체에서 0건 |
| FND-04 | B | protocol.ts 25+ ServerMsg discriminated union | ✓ SATISFIED | 25종 정의, ErrorMsg.text 확인 |
| FND-05 | B | ws/{client,dispatch,parse}.ts 분리 | ✓ SATISFIED | 3개 파일 존재, 기능 구현 |
| FND-06 | B | store 5슬라이스 분할 | ✓ SATISFIED | 5 슬라이스 + index.ts |
| FND-07 | B | appendToken in-place 업데이트 | ✓ SATISFIED | slice(0,-1) + content + text 패턴 확인 |
| FND-08 | B | crypto.randomUUID() id + React key | ✓ SATISFIED | randomUUID() 4곳, key={m.id} 확인 |
| FND-09 | A | tsconfig react-jsx/bundler/strict/ES2022 | ✓ SATISFIED | tsconfig.json 확인됨 |
| FND-10 | A | ESLint 금지 패턴 탐지 | ✓ SATISFIED | @typescript-eslint/parser 설치 + eslint.config.js 파서 설정, bun run lint exit 0 |
| FND-11 | A | grep alternate screen CI 가드 | ✓ SATISFIED | ci-no-escape.sh green |
| FND-12 | C | TTY 가드 + one-shot 분기 | ✓ SATISFIED | isInteractiveTTY, one-shot exit 0 확인 |
| FND-13 | C | 5개 시그널 경로 cleanup | ✓ SATISFIED | index.tsx 라인 29-42: uncaughtException/unhandledRejection/SIGHUP/SIGTERM/SIGINT 5개 모두 cleanup() 호출 |
| FND-14 | C | patchConsole: false | ✓ SATISFIED | index.tsx 라인 58 확인 |
| FND-15 | C | trap 'stty sane' EXIT 쉘 스크립트 | ✓ SATISFIED | harness.sh 확인 |
| FND-16 | C | end-to-end 스모크 | ? NEEDS HUMAN | 로컬 서버 필요 |

---

### 안티패턴 탐지

| 파일 | 라인 | 패턴 | 심각도 | 영향 |
|------|------|------|------|------|
| `src/index.tsx` | 16 | `process.stdout.write('\x1b[?25h')` | ℹ️ Info | cleanup 함수 내 커서 복원 — Ink 렌더 바깥 정리 로직. eslint-disable-next-line 주석으로 의도적 예외 처리됨. 정상. |
| `src/index.tsx` | 49 | `process.stdout.write(...)` | ℹ️ Info | one-shot 경로 (Ink 미진입) — eslint-disable-next-line 주석 포함. 기능적으로 정상. |

이전 Blocker였던 `eslint.config.js` 파서 미설정은 해소되었습니다.

---

### 인간 검증 필요 항목

### 1. end-to-end 스모크 테스트 (FND-16)

**테스트:** `HARNESS_URL=ws://127.0.0.1:7891 HARNESS_TOKEN=<token> HARNESS_ROOM=<room> bun start` 실행 후 "hello" 입력
**기대:** assistant 토큰이 스트리밍되고 in-place 누적, agent_end 수신 후 프롬프트 복귀
**인간 필요 이유:** 로컬 harness_server.py 실행 중이어야 하고 실제 Ollama 모델 응답 필요. 자동화 불가.

---

## 갭 요약

이전 검증(2026-04-23T22:25:00Z)에서 발견된 2건의 갭이 모두 해소되었습니다.

**FND-10 해소:** `@typescript-eslint/parser`가 devDependencies에 추가되었고, `eslint.config.js`에 `languageOptions: { parser: tsParser }` 설정이 적용되었습니다. `bun run lint` (--max-warnings=0)가 exit code 0으로 통과합니다. ESLint 금지 패턴(process.stdout.write/console.log/<div>/child_process.spawn) 탐지 기능이 실제로 동작하는 상태입니다.

**FND-13 해소:** `index.tsx` 라인 42에 `process.on('SIGINT', () => cleanup(0))`가 추가되었습니다. 5개 시그널 경로(uncaughtException · unhandledRejection · SIGHUP · SIGTERM · SIGINT) 전부 cleanup() 함수를 통해 setRawMode(false) + 커서 복원 + stdin.pause()를 수행합니다.

자동화 가능한 모든 검사가 통과합니다. FND-16 end-to-end 스모크 테스트만 로컬 서버(harness_server.py + Ollama)가 필요하여 인간 검증 항목으로 유지됩니다.

---

_검증일: 2026-04-24T07:31:30Z_
_검증자: Claude (gsd-verifier)_
_재검증: 이전 gaps_found (2026-04-23T22:25:00Z) → human_needed_
