---
phase: 01-foundation
verified: 2026-04-23T22:25:00Z
status: gaps_found
score: 4/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "tsc --noEmit green · ESLint green (process.stdout.write/console.log/<div>/child_process.spawn 0건) · vitest 단위 테스트 green"
    status: partial
    reason: "tsc --noEmit green, vitest 30개 전체 pass 이지만 ESLint가 TypeScript 파서(@typescript-eslint/parser) 미설치로 인해 모든 .ts/.tsx 파싱 오류 15건 발생. `bun run lint` exit code 1. FND-10 '금지 패턴 ESLint로 탐지' 기능이 실제로 동작하지 않는 상태."
    artifacts:
      - path: "ui-ink/eslint.config.js"
        issue: "@typescript-eslint/parser 미설치로 ESLint가 TypeScript 파일을 파싱하지 못함. eslint.config.js에 languageOptions.parser 설정 없음."
      - path: "ui-ink/package.json"
        issue: "devDependencies에 @typescript-eslint/eslint-plugin 및 @typescript-eslint/parser 없음."
    missing:
      - "@typescript-eslint/parser 및 @typescript-eslint/eslint-plugin devDependencies 추가"
      - "eslint.config.js에 languageOptions: { parser: tsParser } 설정 추가"
      - "추가 후 bun run lint exit code 0 확인"

  - truth: "kill -9 후 터미널 복구, 5개 시그널 경로에서 setRawMode(false) + 커서 복원 + stdin.pause() 수행"
    status: partial
    reason: "REQUIREMENTS.md FND-13 원문은 SIGINT 포함 5개 경로 모두 cleanup 수행을 요구한다. 코드에 SIGINT 핸들러가 등록되지 않았고 주석으로 '미등록' 결정이 명시되어 있음. 실제로 Ink가 SIGINT를 처리하므로 런타임 안전성은 유지되나, 요건 문자적 충족은 미달."
    artifacts:
      - path: "ui-ink/src/index.tsx"
        issue: "SIGINT 핸들러 미등록 — 라인 40 주석: 'SIGINT: Ink가 기본 처리하므로 추가 핸들러는 등록하지 않음'. REQUIREMENTS.md FND-13은 5개 경로 모두 cleanup 명시."
    missing:
      - "SIGINT 핸들러 추가 (단, Ink 이중 핸들러 충돌 방지 로직 포함) 또는 FND-13을 '4개 경로 + Ink 위임' 형태로 요건 재정의"
      - "이 결정은 설계 트레이드오프이므로 개발자 확인 후 override 또는 수정 중 하나 선택 필요"
human_verification:
  - test: "bun start 후 로컬 harness_server.py에 WS 연결 → 'hello' 입력 → assistant 토큰 스트리밍 렌더 완료 → agent_end 수신 후 프롬프트 복귀 확인"
    expected: "토큰이 스트리밍되며 마지막 assistant 메시지에 in-place 누적되고, agent_end 수신 시 busy 상태 해제 후 입력 프롬프트 복귀"
    why_human: "로컬 harness_server.py 서버가 실행 중이어야 하고 실제 Ollama 모델 응답이 필요한 end-to-end 시나리오. 자동화 불가."
---

# Phase 1: Foundation 검증 보고서

**Phase 목표:** ui-ink 스켈레톤을 Phase 2+ 빌드가 가능한 상태로 끌어올린다. 의존성 세대 격차 · 프로토콜 이름 불일치 · 하드닝 부재를 단일 phase 로 해소해 "`bun start` → 연결 → 토큰 스트리밍 → `agent_end`" end-to-end 스모크가 통과하는 상태를 만든다.

**검증 시각:** 2026-04-23T22:25:00Z
**상태:** gaps_found
**재검증:** 아니오 — 초기 검증

---

## 목표 달성 여부

### 관찰 가능한 진실 (Observable Truths)

| # | 진실 | 상태 | 근거 |
|---|------|------|------|
| 1 | `bun start` 후 WS 연결 → 토큰 스트리밍 → `agent_end` 수신 후 프롬프트 복귀 (FND-16) | ? HUMAN | 로컬 서버 실행 필요 — 자동 검증 불가 |
| 2 | `tsc --noEmit` green · ESLint green · vitest green | ✗ PARTIAL | tsc green (exit 0) · vitest 30/30 pass, 그러나 ESLint TypeScript 파서 미설치로 `bun run lint` exit code 1 (15개 파싱 오류) |
| 3 | `grep '\x1b[?1049\|?1000' ui-ink/src/` 빈 결과 · `echo 'x' | bun run src/index.tsx` crash 없이 종료 | ✓ VERIFIED | ci-no-escape.sh → "OK" · `echo 'x' | bun run src/index.tsx` → exit code 0 |
| 4 | 5개 시그널 경로에서 setRawMode(false) + 커서 복원 + stdin.pause() 수행 | ✗ PARTIAL | uncaughtException · unhandledRejection · SIGHUP · SIGTERM 4개 경로는 cleanup() 함수로 완전 구현됨. SIGINT는 Ink 기본 처리에 위임 (의도적 결정이나 FND-13 원문 미달) |
| 5 | `src/protocol.ts` 에 25+ ServerMsg discriminated union + `src/ws/dispatch.ts` exhaustive switch | ✓ VERIFIED | protocol.ts에 ServerMsg 25종 union 정의 + assertNever 헬퍼, dispatch.ts에 모든 25 case + default assertNever(msg) |

**점수:** 4/5 진실 검증됨 (진실 1은 human 필요, 진실 2·4는 부분 달성)

---

### 필수 아티팩트 검증

| 아티팩트 | 목적 | 존재 | 실질 내용 | 연결 | 상태 |
|---------|------|------|-----------|------|------|
| `ui-ink/package.json` | 의존성 선언 | ✓ | ink@7.0.1, react@19.2.5, zustand@5.0.12, ws@8.20.0 — 모두 정확히 선언. ink-text-input 없음 | ✓ bun install | ✓ VERIFIED |
| `ui-ink/tsconfig.json` | TypeScript 빌드 설정 | ✓ | "jsx":"react-jsx", "moduleResolution":"bundler", "strict":true, lib:["ES2022"] (DOM 없음) | ✓ tsc --noEmit green | ✓ VERIFIED |
| `ui-ink/eslint.config.js` | ESLint 금지 규칙 | ✓ | no-restricted-syntax 7개 규칙 포함, @eslint/js 사용 | ✗ @typescript-eslint/parser 미설치로 실제 동작 안함 | ✗ PARTIAL |
| `ui-ink/scripts/ci-no-escape.sh` | alternate screen CI 가드 | ✓ | 1049h/1000h 등 grep, SCRIPT_DIR 기반 상대 경로 | ✓ bash 실행 시 "OK" 출력 | ✓ VERIFIED |
| `ui-ink/src/protocol.ts` | ServerMsg/ClientMsg union | ✓ | 25종 ServerMsg, 5종 ClientMsg, assertNever 헬퍼 — ErrorMsg.text(.message 아님) 확인 | ✓ dispatch.ts에서 import | ✓ VERIFIED |
| `ui-ink/src/ws/client.ts` | HarnessClient 클래스 | ✓ | connect/send/close/heartbeat(30s) 구현, x-harness-token/room 헤더 포함 | ✓ App.tsx에서 useRef로 참조 | ✓ VERIFIED |
| `ui-ink/src/ws/parse.ts` | JSON → ServerMsg 파서 | ✓ | JSON.parse 실패 시 null 반환, type 필드 없으면 null | ✓ client.ts ws.on('message')에서 호출 | ✓ VERIFIED |
| `ui-ink/src/ws/dispatch.ts` | exhaustive switch 디스패처 | ✓ | 25개 case 전부 처리, default assertNever(msg) | ✓ client.ts에서 dispatch 호출 | ✓ VERIFIED |
| `ui-ink/src/store/messages.ts` | 메시지 슬라이스 | ✓ | appendToken in-place 패턴, crypto.randomUUID() id, streaming 플래그 | ✓ dispatch.ts/App.tsx에서 사용 | ✓ VERIFIED |
| `ui-ink/src/store/input.ts` | 입력 슬라이스 | ✓ | buffer/setBuffer/clearBuffer | ✓ App.tsx에서 사용 | ✓ VERIFIED |
| `ui-ink/src/store/status.ts` | 상태 슬라이스 | ✓ | connected/busy/workingDir/model/mode | ✓ dispatch.ts/App.tsx에서 사용 | ✓ VERIFIED |
| `ui-ink/src/store/room.ts` | 룸 슬라이스 | ✓ | roomName/members/activeInputFrom/activeIsSelf | ✓ dispatch.ts에서 사용 | ✓ VERIFIED |
| `ui-ink/src/store/confirm.ts` | confirm 슬라이스 | ✓ | ConfirmMode/payload/setConfirm/clearConfirm | ✓ dispatch.ts에서 사용 | ✓ VERIFIED |
| `ui-ink/src/store/index.ts` | 통합 re-export | ✓ | 6개 슬라이스 전부 re-export | ✓ | ✓ VERIFIED |
| `ui-ink/src/index.tsx` | TTY 가드 + 시그널 핸들러 + render | ✓ | patchConsole:false, isInteractiveTTY, cleanup, uncaughtException/unhandledRejection/SIGHUP/SIGTERM | ✓ App.tsx render | ⚠️ PARTIAL (SIGINT 미등록) |
| `ui-ink/src/tty-guard.ts` | TTY 가드 유틸 | ✓ | isInteractiveTTY 순수 함수 | ✓ index.tsx에서 import | ✓ VERIFIED |
| `ui-ink/harness.sh` | 쉘 안전망 | ✓ | trap 'stty sane' EXIT, exec bun run | ✓ | ✓ VERIFIED |
| `ui-ink/src/__tests__/protocol.test.ts` | parseServerMsg 테스트 | ✓ | 6개 케이스 — token/agent_end/invalid JSON/error.text/unknown type/no type | ✓ vitest pass | ✓ VERIFIED |
| `ui-ink/src/__tests__/store.test.ts` | store reducer 테스트 | ✓ | agentStart/appendToken in-place/agentEnd/id 중복없음 등 | ✓ vitest pass | ✓ VERIFIED |
| `ui-ink/src/__tests__/dispatch.test.ts` | dispatch exhaustive 테스트 | ✓ | 13개 케이스 포함 | ✓ vitest pass | ✓ VERIFIED |
| `ui-ink/src/__tests__/tty-guard.test.ts` | TTY 가드 테스트 | ✓ | 5개 케이스 — isTTY undefined/false/true+setRawMode/없음/타입오류 | ✓ vitest pass | ✓ VERIFIED |

**삭제 확인:**
- `ui-ink/src/store.ts` — 삭제됨 (Plan B 슬라이스로 대체)
- `ui-ink/src/ws.ts` — 삭제됨 (Plan B ws/*.ts로 대체)

---

### 핵심 연결 검증 (Key Link Verification)

| From | To | Via | 상태 | 근거 |
|------|----|-----|------|------|
| `ws/client.ts` | `ws/dispatch.ts` | ws.on('message') 콜백 | ✓ WIRED | dispatch(msg) 호출 확인됨 |
| `ws/dispatch.ts` | `store/*.ts` | useXxxStore.getState() | ✓ WIRED | messages/status/room/confirm 4개 store 직접 호출 |
| `ws/parse.ts` | `protocol.ts` | ServerMsg 반환 타입 | ✓ WIRED | import type {ServerMsg} from '../protocol.js' |
| `src/index.tsx` | `src/App.tsx` | render(<App/>, {patchConsole:false}) | ✓ WIRED | patchConsole:false 포함 확인 |
| `App.tsx` | `store/messages.ts` | useMessagesStore(useShallow(...)) | ✓ WIRED | useShallow 적용 확인 |
| `App.tsx` | `ws/client.ts` | useRef<HarnessClient> + useEffect | ✓ WIRED | HARNESS_URL/TOKEN 환경변수 기반 조건부 연결 |
| `eslint.config.js` | `src/*.ts/*.tsx` | no-restricted-syntax 규칙 | ✗ NOT_WIRED | @typescript-eslint/parser 미설치로 실제 파싱·탐지 불가 |
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
| ESLint | `bun run lint` | exit code 1, 파싱 오류 15건 (@typescript-eslint/parser 미설치) | ✗ FAIL |

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
| FND-10 | A | ESLint 금지 패턴 탐지 | ✗ BLOCKED | @typescript-eslint/parser 미설치로 ESLint 실제 동작 안함 |
| FND-11 | A | grep alternate screen CI 가드 | ✓ SATISFIED | ci-no-escape.sh green |
| FND-12 | C | TTY 가드 + one-shot 분기 | ✓ SATISFIED | isInteractiveTTY, one-shot exit 0 확인 |
| FND-13 | C | 5개 시그널 경로 cleanup | ✗ BLOCKED | SIGINT 핸들러 미등록 (의도적) — 4개 경로만 구현 |
| FND-14 | C | patchConsole: false | ✓ SATISFIED | index.tsx 라인 56 확인 |
| FND-15 | C | trap 'stty sane' EXIT 쉘 스크립트 | ✓ SATISFIED | harness.sh 확인 |
| FND-16 | C | end-to-end 스모크 | ? NEEDS HUMAN | 로컬 서버 필요 |

---

### 안티패턴 탐지

| 파일 | 라인 | 패턴 | 심각도 | 영향 |
|------|------|------|------|------|
| `src/index.tsx` | 15 | `process.stdout.write('\x1b[?25h')` | ℹ️ Info | cleanup 함수 내 커서 복원 코드 — Ink 렌더 바깥의 정리 로직, 기능적으로 정상. ESLint가 동작했다면 탐지됨 (단 cleanup은 ESLint 예외 처리 필요) |
| `src/index.tsx` | 47 | `process.stdout.write(...)` | ℹ️ Info | one-shot 경로 (Ink 미진입) — 기능적으로 정상, ESLint 예외 처리 필요 |
| `eslint.config.js` | 전체 | TypeScript 파서 미설정 | 🛑 Blocker | `bun run lint` 파싱 오류 15건으로 FND-10 ESLint 탐지 기능 비작동 |

---

### 인간 검증 필요 항목

### 1. end-to-end 스모크 테스트 (FND-16)

**테스트:** `HARNESS_URL=ws://127.0.0.1:7891 HARNESS_TOKEN=<token> bun start` 실행 후 "hello" 입력
**기대:** assistant 토큰이 스트리밍되고 in-place 누적, agent_end 수신 후 프롬프트 복귀
**인간 필요 이유:** 로컬 harness_server.py 실행 중이어야 하고 실제 Ollama 모델 응답 필요

### 2. SIGINT 핸들러 트레이드오프 결정 (FND-13)

**테스트:** `bun start` 실행 중 Ctrl+C 입력 후 터미널 상태 확인
**기대:** 터미널 echo · 라인 편집 · 커서 가시성 정상 유지
**인간 필요 이유:** SIGINT를 Ink에 위임하는 설계가 실제 터미널 상태를 정상 복원하는지 검증 필요. FND-13 원문 충족 vs Ink 이중 핸들러 충돌 방지 중 개발자 결정 필요.

---

## 갭 요약

Phase 1의 핵심 골격 — 의존성 업그레이드, 프로토콜 정합성, 스토어 분할, appendToken 패턴, TTY 가드, vitest 테스트, harness.sh 쉘 안전망 — 은 전부 올바르게 구현되었습니다. `bun run typecheck` (exit 0), `bun run test` (30/30), `bash scripts/ci-no-escape.sh` (OK), `echo 'x' | bun run src/index.tsx` (exit 0) 모두 통과합니다.

두 가지 갭이 존재합니다:

1. **ESLint TypeScript 파서 미설치 (FND-10)** — `eslint.config.js`가 `@typescript-eslint/parser` 없이는 `.ts`/`.tsx` 파일을 파싱할 수 없어 `bun run lint`가 exit code 1입니다. 실제 Ink 금지 패턴(console.log, <div> 등)이 현재 코드에 없다는 것은 grep으로 확인되나, ESLint CI 가드 자체가 동작하지 않습니다.

2. **SIGINT 핸들러 누락 (FND-13 부분 미달)** — REQUIREMENTS.md FND-13은 5개 시그널 경로 모두 cleanup을 명시하나, SIGINT는 Ink 기본 처리에 위임됩니다. Plan C에서 의도적으로 내린 결정이지만 요건 문자적 충족은 미달입니다. 실제 런타임 안전성은 Ink가 보장합니다.

두 갭 모두 Phase 2 진입 전 해소를 권장하나, ESLint 갭이 CI 가드 신뢰성에 직접적 영향을 미치므로 우선 처리가 필요합니다.

---

_검증일: 2026-04-23T22:25:00Z_
_검증자: Claude (gsd-verifier)_
