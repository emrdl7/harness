---
phase: 02-core-ux
plan: C
subsystem: ui-ink/components
tags: [multiline-input, slash-popup, input-area, ink, zustand, vitest]
dependency_graph:
  requires:
    - 02-A  # useInputStore (buffer/history/slashOpen 계약)
    - 02-B  # slash-catalog.ts (SLASH_CATALOG/filterSlash), App.tsx 레이아웃
  provides:
    - MultilineInput  # INPT-01/02/03/04/05 구현체
    - SlashPopup      # INPT-06 구현체
    - InputArea       # D-11 컨테이너 (Wave 3 App.tsx 배선 대상)
  affects:
    - App.tsx  # InputArea drop-in 교체 예정 (Wave 3)
tech_stack:
  added:
    - usePaste (ink@7 — bracketed paste primary handler)
    - ink-select-input@6.2 onHighlight (SlashPopup highlighted state 추적)
  patterns:
    - useShallow selector (전체 store 객체 참조 금지 준수)
    - insertAt 유틸 (cursor 위치 기반 멀티라인 텍스트 삽입)
    - store-driven buffer + local cursor state 분리
key_files:
  created:
    - ui-ink/src/components/MultilineInput.tsx
    - ui-ink/src/components/SlashPopup.tsx
    - ui-ink/src/components/InputArea.tsx
    - ui-ink/src/__tests__/components.multiline.test.tsx
  modified: []
decisions:
  - "usePaste primary + useInput fallback 분리 — Ink 7 usePaste 가 bracketed paste 채널을 별도 관리하므로 useInput 의 paste 휴리스틱 불필요"
  - "SlashPopup Enter → onSelect 방어 연결 (T-02C-05) — SelectInput 이 Enter 를 consume 해도 buffer 교체 일관성 유지"
  - "SlashPopup Tab = 확정, Esc = 닫기 — Enter 는 MultilineInput submit 경로 보존"
  - "빈 buffer Enter 제출 차단 (T-02C-04) — text.trim() === '' guard"
  - "usePaste 는 bracketed paste mode (\\x1b[?2004h) 자동 활성화 — alternate screen 과 달리 scrollback 파괴 없음, CLAUDE.md 금지 대상 아님"
metrics:
  duration_minutes: ~20
  completed_date: "2026-04-24"
  tasks_completed: 4
  files_created: 4
  tests_added: 13
---

# Phase 2 Plan C: MultilineInput / SlashPopup / InputArea Summary

**한 줄 요약:** useInput + Ink 7 usePaste 기반 자체 멀티라인 입력 컴포넌트(INPT-01~05), ink-select-input onHighlight 활용 슬래시 팝업(INPT-06), D-11 레이아웃 컨테이너 구현 완료

---

## 생성 파일 목록

### ui-ink/src/components/MultilineInput.tsx (INPT-01/02/03/04/05)

```typescript
export const MultilineInput: React.FC<{
  onSubmit: (text: string) => void
  disabled?: boolean
}>
```

핵심 구현:
- `usePaste(handler)` — primary paste 처리 (Ink 7 bracketed paste 채널)
- `useInput(handler)` — 키입력 처리 (Enter/Shift+Enter/Ctrl+J/↑↓/POSIX)
- `insertAt(lines, cursor, text)` — cursor 위치 기반 텍스트 삽입 유틸
- `deleteWordBefore`, `killToEnd` — Ctrl+W, Ctrl+K POSIX 유틸

### ui-ink/src/components/SlashPopup.tsx (INPT-06)

```typescript
export const SlashPopup: React.FC<{
  query: string              // buffer 의 '/' 이후 텍스트 (leading '/' 포함)
  onSelect: (commandName: string) => void  // leading slash 포함 ('/help')
  onClose: () => void
}>
```

핵심 구현:
- `filterSlash(query)` → `toItems()` → `SelectInput` 렌더
- `onHighlight` prop 으로 highlighted value 추적
- Tab = 확정(`onSelect`), Esc = 닫기(`onClose`), Enter = 방어적 `onSelect`

### ui-ink/src/components/InputArea.tsx (D-11 레이아웃)

```typescript
export const InputArea: React.FC<{
  onSubmit: (text: string) => void
  disabled?: boolean
}>
```

핵심 구현:
- `buffer.startsWith('/')` 감지 → `setSlashOpen` 자동 토글 (useEffect)
- `slashQuery` = 첫 공백까지만 slice (인자 구간 제외)
- `handleSlashSelect` → `setBuffer(commandName + ' ')` (INPT-08 확장 훅)
- D-11: SlashPopup 먼저 렌더 → MultilineInput 순서 (flexDirection='column')

### ui-ink/src/__tests__/components.multiline.test.tsx

테스트 13개 (기존 80개 → 93개로 증가):
- MultilineInput 5개: Enter 제출, Ctrl+U 삭제, 멀티라인 paste, ↑ history, 빈 Enter 차단
- SlashPopup 5개: 전체 카탈로그 렌더, Esc 닫기, Tab 선택, 필터 쿼리, 0개 후보
- InputArea 3개: buffer='/' → slashOpen, buffer='hello' → 닫힘, buffer='' → 닫힘

---

## 커버된 요건

| REQ-ID | 상태 | 구현 위치 |
|--------|------|-----------|
| INPT-01 | Implemented | MultilineInput.tsx — 자체 구현, ink-text-input 불사용 |
| INPT-02 | Implemented | MultilineInput — Enter 제출 / Shift+Enter·Ctrl+J 개행 |
| INPT-03 | Implemented | MultilineInput — ↑↓ historyUp/historyDown store 위임 |
| INPT-04 | Implemented | MultilineInput — Ctrl+A/E/K/W/U POSIX 단축키 |
| INPT-05 | Implemented | MultilineInput — usePaste primary + useInput fallback |
| INPT-06 | Implemented | SlashPopup — filterSlash, Tab 확정, Esc 닫기 |
| INPT-08 | Partial (hook only) | InputArea.handleSlashSelect — `commandName + ' '` trailing space. 실제 Tab 인자 자동완성은 후속 Plan |

---

## Wave 3 (Plan D/E) 를 위한 후속 작업

1. **App.tsx 에 InputArea 실제 배선** — Plan B 의 placeholder `<Box><Text>❯ {buffer}</Text></Box>` 를 `<InputArea onSubmit={handleSubmit} />` 으로 교체. WS 송신 + messages store push 로직을 handleSubmit 에서 처리.

2. **Ctrl+C 첫 번째 cancel 전송 (INPT-09)** — App.tsx 의 상위 useInput 에서 이미 처리 중 (Plan B B-5). MultilineInput 은 Ctrl+C 를 intercept 하지 않아 T-02C-07 완화 조건 충족. Plan E 수동 확인 필수.

3. **Ctrl+D 종료 가드 (INPT-10)** — App.tsx 의 상위 useInput 에서 이미 처리 중 (Plan B). Plan E 수동 확인.

4. **500줄 paste 수동 스모크** — T-02C-03 (DoS 완화). Phase 2 exit criteria 로 이월.

5. **macOS IME 시나리오** — T-02C-02 (IME 조합 중 Enter). Plan E 수동 검증 체크리스트.

---

## 알려진 제약

- **Shift+Enter 터미널 구분 불가** — 터미널은 Shift+Enter 와 Enter 를 동일한 raw sequence 로 전송. `key.shift` + `key.return` 조합은 kitty keyboard protocol 에서만 구분 가능. 현재 vitest 는 store 상태로 간접 검증. Plan E 수동 검증에서 실제 키 동작 필수 확인.

- **usePaste 는 stdin.write 로 직접 트리거 불가** — ink-testing-library 의 stdin.write 는 bracketed paste 채널을 우회함. paste 테스트는 store 직접 조작으로 간접 검증.

- **INPT-08 인자 자동완성 미구현** — `handleSlashSelect` 에 trailing space 훅만 마련. 실제 Tab 기반 인자 자동완성은 후속 Plan 에서 구현.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ink-select-input Item 타입 import 오류 수정**
- **Found during:** C-2 typecheck
- **Issue:** `import {type Item} from 'ink-select-input'` 가 컴포넌트를 타입으로 사용하는 TS2749 오류
- **Fix:** 로컬 `interface SelectItem` 정의로 대체
- **Files modified:** ui-ink/src/components/SlashPopup.tsx
- **Commit:** f1811ee

**2. [Rule 1 - Bug] ESLint react-hooks/exhaustive-deps 미등록 규칙 주석 제거**
- **Found during:** C-2 lint
- **Issue:** `// eslint-disable-next-line react-hooks/exhaustive-deps` 주석이 프로젝트에 등록되지 않은 규칙을 참조하여 ESLint 오류 발생
- **Fix:** 주석 제거, 한국어 설명으로 교체
- **Files modified:** ui-ink/src/components/SlashPopup.tsx
- **Commit:** f1811ee

**3. [Rule 2 - Missing Critical] 빈 입력 Enter 제출 차단 (T-02C-04)**
- **Found during:** C-1 구현 (threat model 검토)
- **Issue:** plan 본문에 `text.trim() === ''` 가드가 명시되어 있었으나 history 오염 방지를 위한 correctness requirement
- **Fix:** `if (text.trim() === '') return` guard 추가 + 테스트 케이스 1개 추가
- **Files modified:** ui-ink/src/components/MultilineInput.tsx, components.multiline.test.tsx

---

## Threat Surface Scan

해당 Plan 에서 새로 도입한 네트워크 엔드포인트, 파일 접근 경로, 인증 경로 없음.
`usePaste` 가 bracketed paste mode (`\x1b[?2004h`) 를 자동 활성화하나, 이는 scrollback 파괴가 없는 표준 터미널 기능으로 CLAUDE.md 금지 대상(alternate screen, mouse tracking)과 상이함.

---

## Self-Check

파일 존재 확인:
- ui-ink/src/components/MultilineInput.tsx: FOUND
- ui-ink/src/components/SlashPopup.tsx: FOUND
- ui-ink/src/components/InputArea.tsx: FOUND
- ui-ink/src/__tests__/components.multiline.test.tsx: FOUND

커밋 확인:
- 76e1f49 (C-1): FOUND
- f1811ee (C-2): FOUND
- de28369 (C-3): FOUND
- 32d5b07 (C-4): FOUND

검증 결과:
- `bun run typecheck`: 0 exit
- `bun run lint`: 0 exit (max-warnings=0)
- `bun run test`: 93/93 PASS (신규 13개 포함)
- `bun run ci:no-escape`: OK

## Self-Check: PASSED
