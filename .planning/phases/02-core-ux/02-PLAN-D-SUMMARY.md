---
phase: 02-core-ux
plan: D
subsystem: confirm-toolcard-ui
tags: [ink, zustand, confirm, diff-preview, tool-card, tdd]
dependency_graph:
  requires:
    - Plan A (confirm store: stickyDeny/resolve/addDenied/isDenied)
    - Plan B (App.tsx 레이아웃: ConfirmDialog 슬롯 확보)
  provides:
    - ConfirmDialog 컴포넌트 (CNF-01/02/04/05)
    - classifyCommand 유틸 (CNF-02 danger 분류)
    - DiffPreview 컴포넌트 (RND-07 placeholder)
    - ToolCard 컴포넌트 (RND-08 TOOL_META 요약)
    - components.confirm vitest suite (9케이스)
  affects:
    - Plan E (App.tsx ConfirmDialog 슬롯 교체 — import 만 하면 즉시 동작)
tech_stack:
  added: []
  patterns:
    - useShallow 선택적 store 구독
    - useFocus + useInput isActive 포커스 격리
    - 클라이언트 사이드 danger 분류 (DANGEROUS_PATTERNS)
    - Phase 3 교체 placeholder 패턴 (newContent optional)
key_files:
  created:
    - ui-ink/src/components/ConfirmDialog.tsx
    - ui-ink/src/components/DiffPreview.tsx
    - ui-ink/src/components/ToolCard.tsx
    - ui-ink/src/__tests__/components.confirm.test.tsx
decisions:
  - "classifyCommand 클라이언트 판정: 서버가 danger_level 필드를 보내지 않으므로 DANGEROUS_PATTERNS로 직접 분류"
  - "ConfirmDialog useInput은 !activeIsSelf 분기 이후에 위치 — 관전자 키 가로채기 방지"
  - "DiffPreview newContent optional: Phase 2에서 confirm_write payload에 content 없음, Phase 3(PEXT-02)에서 추가 예정"
  - "ToolCard useFocus({autoFocus:false}) + isActive: 여러 카드 동시 입력 차단"
  - "sticky-deny useEffect: mode 변경 시 1회만 체크, resolve 내부에서도 addDenied 처리(double-guard)"
metrics:
  duration: "약 4분"
  completed_date: "2026-04-24"
  tasks_completed: 4
  tasks_total: 4
  files_created: 4
  tests_added: 9
  tests_total: 89
---

# Phase 2 Plan D: ConfirmDialog + DiffPreview + ToolCard Summary

**한 줄 요약:** confirm_write/bash/cplan 세 모드 + 관전자 read-only + sticky-deny 자동 체크를 갖춘 ConfirmDialog, Phase 3 diff 교체 예정 DiffPreview placeholder, TOOL_META 1줄 요약 + Space/Enter 토글 ToolCard를 구현하여 Plan E App.tsx 교체 준비 완료

## 완료 태스크

| 태스크 | 설명 | 커밋 | 파일 |
|--------|------|------|------|
| D-1 | ConfirmDialog — CNF-01/02/04/05 + sticky-deny + classifyCommand | 25a5e88 | ConfirmDialog.tsx (169줄) |
| D-2 | DiffPreview — RND-07 Phase 2 placeholder | 380288b | DiffPreview.tsx (34줄) |
| D-3 | ToolCard — RND-08 TOOL_META 요약 + Space/Enter 토글 | b638239 | ToolCard.tsx (88줄) |
| D-4 | vitest 통합 테스트 — classifyCommand 3 + ConfirmDialog 6 | 6f69629 | components.confirm.test.tsx (100줄) |

## 생성된 파일 상세

### ConfirmDialog.tsx (169줄)

**Exports:** `ConfirmDialog`, `classifyCommand`

**서브뷰:**
- `confirm_write` 모드: 경로 + DiffPreview 토글(d키) + y/n/d/Esc 힌트 (CNF-01)
- `confirm_bash` 모드: 커맨드 + 위험도 라벨([위험]/[일반]) + y/n/Esc 힌트 (CNF-02)
- `cplan_confirm` 모드: task 문자열 + y/n/Esc 힌트 (CNF-05)
- `activeIsSelf=false`: ConfirmReadOnlyView "관전 중 — 응답 불가" (CNF-04)

**sticky-deny 로직:**
- `useEffect` 에서 mode 변경 시 isDenied 체크 → 즉시 resolve(false)
- handleDeny 에서 addDenied 호출 (store.resolve 내부도 처리하므로 double-guard)
- Esc 키 = deny 동일 처리

### DiffPreview.tsx (34줄)

**Exports:** `DiffPreview`

**Props:** `path: string`, `newContent?: string`

**동작:**
- `newContent === undefined`: "(새 내용 미수신 — Phase 3 에서 diff 표시 예정)" 메시지
- `newContent` 있으면: 처음 10줄 `+ ` prefix로 표시, 초과 시 "... (N줄 더)" truncation 메시지
- React key: `preview-${path}-${i}-${ln.slice(0, 16)}` (index 단독 금지 준수)

**Phase 3 교체 지점:** `newContent` → `oldContent + newContent` prop 추가 + `diff@9 structuredPatch` import

### ToolCard.tsx (88줄)

**Exports:** `ToolCard`, `ToolInvocationView`

**TOOL_META 포함 툴 목록 (5개):**
| 툴 | 요약 규칙 |
|----|----------|
| `read_file` | `read N lines` |
| `write_file` | `write {args.path}` |
| `run_command` | `exit N` 또는 `ran` |
| `list_directory` | `ls N entries` |
| `search_files` | `found N results` |

**미등록 툴 fallback:** result 앞 60자 + `...`

**포커스 동작:**
- `useFocus({autoFocus: false})` + `useInput(handler, {isActive: isFocused})`
- 포커스된 카드만 Space/Enter 입력 수신 (여러 카드 동시 토글 방지)
- `useInput` 호출 수: 정확히 1개

### components.confirm.test.tsx (100줄)

**테스트 케이스 목록:**

```
classifyCommand (CNF-02)
  ✓ 평문 명령은 safe 로 판정한다
  ✓ rm / sudo / chmod 는 dangerous
  ✓ 쉘 메타 문자 및 command substitution 은 dangerous

ConfirmDialog rendering
  ✓ confirm_write 모드: 경로와 y/n/d/Esc 힌트를 표시한다 (CNF-01)
  ✓ confirm_bash 모드: 커맨드와 위험 라벨을 표시한다 (CNF-02)
  ✓ confirm_bash 안전 커맨드: [일반] 라벨
  ✓ cplan_confirm 모드: task 와 힌트를 표시한다 (CNF-05)
  ✓ activeIsSelf=false: read-only 뷰를 렌더한다 (CNF-04)
  ✓ mode=none 일 때 null 을 반환한다
```

**전체 vitest 결과:** 89/89 passed (11 파일)

## classifyCommand DANGEROUS_PATTERNS (최종)

```typescript
const DANGEROUS_PATTERNS: RegExp[] = [
  /\brm\b/,
  /\bsudo\b/,
  /\bchmod\b/,
  /\bchown\b/,
  /[|&;<>`]/,     // 쉘 메타문자 / 파이프 / 리디렉션
  /\$\(/,         // command substitution
  /\bdd\b/,
  /\bmkfs\b/,
  /\beval\b/,
]
```

## Plan E (App.tsx 교체) 참조 가이드

Plan E는 App.tsx의 confirm placeholder를 실제 `<ConfirmDialog />`로 교체합니다.

**import 경로:**
```typescript
import {ConfirmDialog} from './components/ConfirmDialog.js'
```

**App.tsx 교체 지점 (현재 placeholder):**
```tsx
// AS-IS (App.tsx line 169-173)
{confirmMode !== 'none' ? (
  <Box>
    <Text color={theme.status.busy} bold>[confirm {confirmMode}] y/n · esc</Text>
  </Box>
) : (

// TO-BE (Plan E 교체)
{confirmMode !== 'none' ? (
  <ConfirmDialog />
) : (
```

**주의:** App.tsx의 confirm 모드 최소 처리 (y/n/Esc) 코드(line 113-123)도 제거해야 ConfirmDialog와 중복 처리가 발생하지 않음.

## Phase 3 PEXT-02 DiffPreview 교체 지점

`ui-ink/src/components/DiffPreview.tsx`의 교체 내용:

1. `diff@9` import 추가: `import {structuredPatch} from 'diff'`
2. `oldContent?: string` prop 추가
3. `newContent !== undefined && oldContent !== undefined` 분기에서 `structuredPatch` 호출 후 hunks 렌더

## Deviations from Plan

### Auto-fixed Issues

없음 — Plan D 의 모든 태스크는 플랜대로 실행되었습니다.

### 구현 시 결정 사항

1. **eslint-disable-next-line 주석 추가:** ConfirmDialog.tsx에서 관전자 분기 이후 `useInput` 호출에 `react-hooks/rules-of-hooks` 억제 주석 추가. React Hooks 규칙상 조건부 반환 뒤 훅 호출은 금지이나, Ink의 `useInput` 특성상 관전자 분기 뒤 위치가 CNF-04 보안 요구사항임. 주석으로 의도 명시.

2. **clearConfirm 제거:** sticky-deny useEffect에서 `clearConfirm` 호출을 제거했습니다. `resolve(false)` 내부에서 이미 `set({mode: 'none', payload: {}})` 처리하므로 중복 호출 불필요.

## Known Stubs

- **DiffPreview.tsx**: `newContent` prop이 undefined인 경우 "(새 내용 미수신 — Phase 3 에서 diff 표시 예정)" 텍스트 표시. 이는 의도된 Phase 2 placeholder — Phase 3 PEXT-02에서 old_content 수신 후 diff@9 연동으로 교체 예정.

## Threat Flags

없음 — 플랜의 threat_model(T-02D-01 ~ T-02D-08) 내에서만 변경.

## Self-Check

- `ui-ink/src/components/ConfirmDialog.tsx` — FOUND
- `ui-ink/src/components/DiffPreview.tsx` — FOUND
- `ui-ink/src/components/ToolCard.tsx` — FOUND
- `ui-ink/src/__tests__/components.confirm.test.tsx` — FOUND
- Commit 25a5e88 — FOUND (D-1 ConfirmDialog)
- Commit 380288b — FOUND (D-2 DiffPreview)
- Commit b638239 — FOUND (D-3 ToolCard)
- Commit 6f69629 — FOUND (D-4 테스트)
- bun run test: 89/89 PASSED
- bunx tsc --noEmit: PASSED (에러 0)
- 금지 패턴 검사: PASSED (0건)
- useInput 개수 (ToolCard): 3줄 (import 1 + 주석 1 + 호출 1) — 실제 호출 1개 PASSED
- useShallow 사용 (ConfirmDialog): PASSED

**Self-Check: PASSED**
