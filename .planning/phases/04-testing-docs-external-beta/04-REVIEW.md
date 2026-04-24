---
phase: 04-testing-docs-external-beta
reviewed: 2026-04-24T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - .github/workflows/ci.yml
  - ui-ink/scripts/guard-forbidden.sh
  - ui-ink/src/__tests__/integration.agent-turn.test.ts
  - ui-ink/src/__tests__/integration.confirm-write.test.ts
  - ui-ink/src/__tests__/integration.room.test.ts
  - ui-ink/src/__tests__/integration.reconnect.test.ts
  - ui-ink/src/__tests__/components.multiline.test.tsx
  - ui-ink/src/__tests__/tty-guard.test.ts
  - ui-ink/src/__tests__/store.messages.snapshot.test.tsx
  - CLIENT_SETUP.md
  - PROTOCOL.md
  - RELEASE_NOTES.md
findings:
  critical: 0
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-04-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 4의 테스트·문서·CI 파일 12개를 검토했습니다. Critical 보안 취약점은 없습니다. 주요 발견사항은 다음과 같습니다.

- **타이밍 의존성(Warning):** 통합 테스트 4개 파일 전체가 `setTimeout(r, 20)` 방식의 고정 지연으로 비동기 흐름을 기다립니다. CI 환경(부하 상황·macOS 러너 지연)에서 간헐적 실패(flaky) 위험이 있습니다.
- **리소스 누수(Warning):** `integration.room.test.ts`의 3인 동시 접속 테스트가 `openSockets` 추적 없이 서버 소켓을 열어 두고 `afterAll`에서 명시적으로 닫지 않아, 테스트 타임아웃을 유발할 수 있습니다.
- **guard 스크립트 정규식(Warning):** alternate screen/mouse tracking 이스케이프 패턴이 실제 소스의 리터럴 형식과 일치하지 않아 검사가 항상 통과(false negative)합니다.
- **CI Python 설치 실패 무시(Warning):** `pip install` 실패 시 `|| true`로 계속 진행하여 pytest가 의존성 없이 실행될 수 있습니다.
- **문서 정확도(Info):** CR-01 버그가 PROTOCOL.md와 RELEASE_NOTES.md 양쪽에 "수정 예정"으로 기재되어 있으나 실제 수정 커밋(`ccd0e06`)이 이미 완료된 상태이므로 Known Bugs 항목을 제거해야 합니다.

---

## Warnings

### WR-01: 통합 테스트 — 고정 지연(20ms) 기반 비동기 기다림으로 flaky 위험

**Files:**
- `ui-ink/src/__tests__/integration.agent-turn.test.ts:54,60,83,90`
- `ui-ink/src/__tests__/integration.confirm-write.test.ts:56`
- `ui-ink/src/__tests__/integration.room.test.ts:54,90`
- `ui-ink/src/__tests__/integration.reconnect.test.ts:95,102,108`

**Issue:** 모든 통합 테스트에서 WS 메시지 전달 및 Zustand store dispatch 완료를 `await new Promise<void>((r) => setTimeout(r, 20))` 단일 고정 타이머로 기다립니다. 로컬 개발환경에서는 충분하나, macOS GitHub Actions 러너가 바쁜 시간대에 20ms 안에 이벤트 루프가 돌지 않으면 assertion이 이른 시점에 실행되어 간헐적으로 실패합니다.

**Fix:** WS 이벤트 완료를 명시적으로 기다리는 방식으로 교체합니다. 가장 단순한 접근은 Zustand store를 polling하거나, `vi.waitFor` (vitest 내장)를 사용하는 것입니다.

```typescript
// 변경 전
serverWs.send(JSON.stringify({type: 'agent_start', from_self: true}))
await new Promise<void>((r) => setTimeout(r, 20))
expect(useStatusStore.getState().busy).toBe(true)

// 변경 후 (vitest vi.waitFor 사용)
import {vi} from 'vitest'
serverWs.send(JSON.stringify({type: 'agent_start', from_self: true}))
await vi.waitFor(() => {
  expect(useStatusStore.getState().busy).toBe(true)
}, {timeout: 1000})
```

---

### WR-02: integration.room.test.ts — 3인 동시 접속 테스트에서 서버 소켓 누수

**File:** `ui-ink/src/__tests__/integration.room.test.ts:71-73`

**Issue:** `fakeServer.on('connection', ...)` 핸들러를 `once` 대신 `on`으로 등록합니다. 이 핸들러는 `afterAll`에서 제거되지 않아 이후 다른 테스트의 연결에도 계속 발동됩니다. 또한 이 테스트 파일에는 `integration.reconnect.test.ts`에 있는 `openSockets` 추적 패턴이 없어, 3개의 클라이언트 소켓이 `clients.forEach(c => c.close())` 이후에도 서버 측에서 정리되기 전에 다음 테스트가 시작될 수 있습니다.

```typescript
// 변경 전 (라인 72-76) — 누적 핸들러
const allConnected = new Promise<void>((resolve) => {
  let count = 0
  fakeServer.on('connection', (ws) => {   // ← 'on' 은 영속적으로 남음
    serverWsList.push(ws)
    count++
    if (count === 3) resolve()
  })
})

// 변경 후 — 완료 후 핸들러 제거
const allConnected = new Promise<void>((resolve) => {
  let count = 0
  const handler = (ws: WebSocket) => {
    serverWsList.push(ws)
    count++
    if (count === 3) {
      fakeServer.off('connection', handler)
      resolve()
    }
  }
  fakeServer.on('connection', handler)
})
```

---

### WR-03: guard-forbidden.sh — alternate screen / mouse tracking 정규식이 실제 소스와 불일치 (false negative)

**File:** `ui-ink/scripts/guard-forbidden.sh:40-41`

**Issue:** 스크립트가 검사하는 정규식은 다음과 같습니다.

```bash
check 'no alternate screen escape (1049h)' '\\\\x1b\[\\\\?1049h'
check 'no mouse tracking escape (1000h)'   '\\\\x1b\[\\\\?100[0-3]h'
```

`grep -E`에 전달될 때 이중 역슬래시 이스케이프가 겹쳐서, 실제 소스 코드에 `\x1b[?1049h` 리터럴이 있어도 탐지하지 못합니다. `grep -E`에서 리터럴 이스케이프 바이트를 탐지하려면 패턴이 달라야 합니다. 현재는 가드가 항상 "OK"를 출력하므로, 악의적이거나 실수로 삽입된 이스케이프 시퀀스를 잡지 못합니다.

**Fix:**

```bash
# 리터럴 \x1b 문자열(소스에 하드코딩된 경우) 탐지
check 'no alternate screen escape (1049h)' '\\\\x1b\[\\?1049h|\\x1b\[\\?1049h'

# 또는 Perl 모드(-P) 사용
if grep -rnP '\x1b\[\?1049h' src/ --include='*.ts' --include='*.tsx'; then ...
```

실용적 대안으로, 소스 파일에 유니코드 이스케이프 형태(``)나 문자열 형태(`\x1b`) 둘 다 포함한 패턴을 커버하도록 수정하는 것이 권장됩니다.

---

### WR-04: CI yml — Python 의존성 설치 실패 무시로 pytest가 빈 환경에서 실행될 수 있음

**File:** `.github/workflows/ci.yml:74-75`

**Issue:**

```yaml
pip install -e ".[dev]" 2>/dev/null || pip install -r requirements.txt 2>/dev/null || true
```

마지막 `|| true`로 인해 두 pip 명령이 모두 실패해도 워크플로우가 계속 진행됩니다. 결과적으로 `python -m pytest -x --tb=short`가 의존성 없이 실행되어, 임포트 오류가 pytest 수집 실패로 나타나 실제 버그를 숨길 수 있습니다.

**Fix:**

```yaml
- name: Install Python deps
  run: |
    python -m pip install --upgrade pip
    pip install -e ".[dev]" || pip install -r requirements.txt
```

`2>/dev/null`도 제거하면 실패 원인을 CI 로그에서 즉시 확인할 수 있습니다.

---

### WR-05: store.messages.snapshot.test.tsx — snapshotKey 필드가 일부 beforeEach에서 초기화 누락

**File:** `ui-ink/src/__tests__/store.messages.snapshot.test.tsx:47-53`

**Issue:** `describe('dispatch 확장')` 블록의 `beforeEach`(라인 47-53)에서 `useMessagesStore.setState`에 `snapshotKey` 필드가 포함되어 있지 않습니다. `describe('loadSnapshot')` 블록(라인 16-18)에는 `snapshotKey: 0`이 있으나, 두 번째 describe 블록에는 누락되어 있습니다. `loadSnapshot` describe 이후 `dispatch` describe가 실행될 때 `snapshotKey`가 이전 테스트에서 증가된 값(예: 1)으로 남아 있으면, `dispatch` 테스트 내에서 snapshot 관련 로직이 예상치 못하게 동작할 수 있습니다.

```typescript
// 변경 전 (라인 48-53)
beforeEach(() => {
  useMessagesStore.setState({completedMessages: [], activeMessage: null, snapshotKey: 0})
  // ...
})

// 이미 snapshotKey: 0 포함 — 실제로는 맞습니다. 단, 아래 '회귀 스냅샷' describe도 확인 필요
```

재검토 결과: `dispatch 확장` describe의 `beforeEach` 라인 48에는 `snapshotKey: 0`이 포함되어 있습니다. 다만 `회귀 스냅샷(TST-03)` describe의 `beforeEach`(라인 100-113)에서 `snapshotKey` 필드가 없습니다. 이전 describe에서 `snapshotKey`가 증가한 채로 스냅샷 테스트가 시작될 수 있습니다.

**Fix:**

```typescript
// 라인 102 근처 — 회귀 스냅샷 beforeEach
useMessagesStore.setState({
  completedMessages: [],
  activeMessage: null,
  snapshotKey: 0,  // ← 추가
})
```

---

## Info

### IN-01: CLIENT_SETUP.md — Bun 최소 버전이 package.json engines 필드와 일치함 (확인 완료)

**File:** `CLIENT_SETUP.md:11`

**Issue:** `CLIENT_SETUP.md`의 "Bun >= 1.2.19"는 `package.json`의 `"engines": {"bun": ">=1.2.19"}`와 일치합니다. 현재는 정확합니다. 단, Bun 버전을 bump할 때 두 파일을 동시에 업데이트해야 한다는 점을 주의하십시오 (단일 소스가 아님).

---

### IN-02: PROTOCOL.md — CR-01 Known Bugs 항목이 이미 수정된 버그를 현재형으로 기술

**File:** `PROTOCOL.md:151-153, 219-235`

**Issue:** `PROTOCOL.md`의 주의 블록(라인 151-153)과 Known Bugs 섹션(라인 218-235)이 CR-01을 "현재 confirm 승인이 항상 거부로 처리됩니다"라는 현재 시제로 기술합니다. git log 상 커밋 `ccd0e06`(`fix(03): CR-01 confirm_write_response accept 필드 수정`)이 이미 완료되어 있으므로 서버 측 수정도 적용된 상태입니다. 문서가 현실을 반영하지 못하면 외부 클라이언트 구현자에게 혼란을 줍니다.

**Fix:** Known Bugs 섹션을 삭제하거나, "v0.3.1에서 수정됨"으로 변경하십시오. ClientMsg 섹션의 주의 블록도 제거하십시오.

---

### IN-03: RELEASE_NOTES.md — CR-01 알려진 버그 항목이 이미 수정된 상태를 미래형으로 기술

**File:** `RELEASE_NOTES.md:49-51`

**Issue:** `RELEASE_NOTES.md:49`의 "임시 대응: ... 수정 예정" 문구는 커밋 `ccd0e06`으로 이미 수정이 완료된 상태를 반영하지 못합니다. 외부 베타 사용자가 이 릴리즈 노트를 읽으면 수정된 버그를 우회하려다 불필요한 혼란을 겪을 수 있습니다.

**Fix:** "알려진 버그" 섹션에서 CR-01 항목을 제거하거나 "수정됨 (v0.3.1, ccd0e06)"으로 변경하십시오.

---

### IN-04: integration.confirm-write.test.ts — 테스트 주석이 "서버 수정 예정"을 언급하나 이미 완료

**File:** `ui-ink/src/__tests__/integration.confirm-write.test.ts:83-84`

**Issue:** 라인 83-84의 주석이 "서버 수정(04-05)에서 harness_server.py의 result → accept 교정 예정"으로 기술되어 있습니다. 이미 수정 완료된 내용이므로 미래형 주석이 혼동을 줄 수 있습니다.

**Fix:**

```typescript
// CR-01: 서버 수정 완료 (ccd0e06) — harness_server.py가 accept 필드를 우선 읽음
// 이 테스트는 클라이언트가 accept 필드를 올바르게 전송함을 영속적으로 검증
```

---

_Reviewed: 2026-04-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
