---
phase: 04-testing-docs-external-beta
plan: "03"
subsystem: ui-ink/testing
tags: [unit-test, snapshot, multiline-input, tty-guard, tst-01, tst-03, inpt-02, inpt-03, inpt-04, fnd-12]
dependency_graph:
  requires:
    - 04-01-SUMMARY.md  # 통합 테스트 패턴 (153건 기준선)
  provides:
    - components.multiline.test.tsx  # POSIX 단축키 + 개행 + 빈 히스토리 케이스 보완
    - tty-guard.test.ts              # non-TTY one-shot 경로 명시 케이스 추가
    - store.messages.snapshot.test.tsx  # 회귀 스냅샷 4종 (TST-03)
    - __snapshots__/store.messages.snapshot.test.tsx.snap  # 스냅샷 파일
  affects:
    - vitest suite (153건 → 163건 증가)
tech_stack:
  added: []
  patterns:
    - ink-testing-library render() + toMatchSnapshot() 기반 회귀 스냅샷
    - beforeEach store 전체 초기화 (app.smoke.test.tsx 패턴 재사용)
    - stdin.write() POSIX 키코드 시퀀스 직접 시뮬레이션
key_files:
  created:
    - ui-ink/src/__tests__/store.messages.snapshot.test.tsx
    - ui-ink/src/__tests__/__snapshots__/store.messages.snapshot.test.tsx.snap
  modified:
    - ui-ink/src/__tests__/components.multiline.test.tsx
    - ui-ink/src/__tests__/tty-guard.test.ts
decisions:
  - "store.messages.snapshot.test.ts → .tsx 전환: JSX(render(<App />)) 사용 필요, TypeScript .ts 파일에서 파싱 오류 발생"
  - "ink-testing-library render()는 columns 옵션 미지원: 두 번째 인수 제거, 한국어+emoji 테스트는 기본 폭으로 스냅샷 고정"
metrics:
  duration: "약 5분"
  completed_date: "2026-04-24"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 2
---

# Phase 4 Plan 03: 단위 테스트 보완 + 회귀 스냅샷 4종 (TST-01, TST-03) Summary

MultilineInput POSIX 키 시퀀스 5종 + TTY 가드 non-TTY 경로 케이스 보완, ink-testing-library render() 기반 회귀 스냅샷 4종(500토큰 스트리밍·한국어+emoji·/undo 순서·Static 오염 0) green.

## Objectives

Phase 1~3에서 확립된 기존 단위 테스트 누락 케이스를 보완하고(TST-01), Phase 2~3 렌더링 동작을 스냅샷으로 고정(TST-03). 향후 컴포넌트 변경 시 회귀를 자동 감지.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | MultilineInput 키 시퀀스 보완 + TTY 가드 non-TTY 케이스 추가 | 6613f6b | components.multiline.test.tsx, tty-guard.test.ts |
| 2 | 회귀 스냅샷 4종 추가 + store.messages.snapshot .tsx 전환 | 160c72a | store.messages.snapshot.test.tsx, __snapshots__/ |

## Test Results

- **기존:** 25개 파일, 153건 통과
- **최종:** 25개 파일, 163건 통과 (신규 10건 추가)
- **TypeScript:** tsc --noEmit 에러 0건

### 추가된 케이스 상세

**Task 1 — components.multiline.test.tsx (5건 추가, 5건 → 10건)**

| 케이스 | 키코드 | REQ-ID | 결과 |
|--------|--------|--------|------|
| Ctrl+J 개행 — onSubmit 미호출, buffer에 '\n' 누적 | `\x0a` | INPT-02 | PASS |
| Ctrl+K 뒤 삭제 — Ctrl+A 후 Ctrl+K → buffer='' | `\x01` + `\x0b` | INPT-04 | PASS |
| Ctrl+W 단어 삭제 — 'hello world' → 'hello' | `\x17` | INPT-04 | PASS |
| Ctrl+A 줄 처음 이동 후 문자 삽입 — 'Xhello' | `\x01` | INPT-04 | PASS |
| 빈 히스토리 ↑ 크래시 없음 | `\x1b[A` | INPT-03 | PASS |

**Task 1 — tty-guard.test.ts (1건 추가, 5건 → 6건)**

| 케이스 | REQ-ID | 결과 |
|--------|--------|------|
| stdin.isTTY=false one-shot 경로 명시 (FND-12) | FND-12 | PASS |

**Task 2 — store.messages.snapshot.test.tsx (4종 스냅샷)**

| 케이스 | 내용 | 결과 |
|--------|------|------|
| 500 토큰 스트리밍 스냅샷 | activeMessage.content 500자, streaming:true | PASS (생성) |
| 한국어+emoji 메시지 렌더 스냅샷 | '안녕하세요' 포함 확인 + 스냅샷 고정 | PASS (생성) |
| /undo + 새 메시지 순서 스냅샷 | pos1 < pos2 순서 보장 | PASS (생성) |
| Static 오염 0 — spinner 잔재 없음 | Braille 문자 미포함 확인 | PASS (생성) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] store.messages.snapshot.test.ts → .tsx 파일 전환**
- **Found during:** Task 2 첫 실행
- **Issue:** 파일 확장자가 `.ts`인데 JSX(`<App />`)를 사용하여 oxc Transform 파싱 오류 발생 (`Expected '>' but found '/'`)
- **Fix:** 파일을 `.tsx`로 전환 (git rm --cached 후 새 파일 생성)
- **Files modified:** `store.messages.snapshot.test.ts` → `store.messages.snapshot.test.tsx`
- **Commit:** 160c72a

**2. [Rule 1 - Bug] ink-testing-library render() columns 옵션 미지원**
- **Found during:** Task 2 tsc typecheck
- **Issue:** `render(<App />, {columns: 40})` — render() 는 인수 1개만 허용 (TS2554)
- **Fix:** columns 옵션 제거, 기본 폭에서 한국어+emoji 콘텐츠 포함 여부(`.toContain('안녕하세요')`)로 보완 확인 후 스냅샷 고정
- **Files modified:** `store.messages.snapshot.test.tsx`
- **Commit:** 160c72a (동일 커밋)

**3. [Rule 1 - Bug] obsolete 스냅샷 정리**
- **Found during:** Task 2 최종 vitest run
- **Issue:** 테스트 이름 변경('한국어+emoji wrap 폭 40' → '한국어+emoji 메시지 렌더')으로 구 스냅샷 1개 obsolete
- **Fix:** `vitest run -u` 로 obsolete 스냅샷 제거
- **Commit:** 160c72a (동일 커밋)

## Known Stubs

없음 — 테스트 파일만 생성/수정, UI 컴포넌트 변경 없음.

## Threat Flags

없음 — T-04-07(스냅샷 파일 git commit 대상), T-04-08(columns:40 — 미지원으로 기본폭 사용) 모두 accept 처리됨. 신규 보안 표면 없음.

## Self-Check: PASSED

- components.multiline.test.tsx: FOUND (수정됨)
- tty-guard.test.ts: FOUND (수정됨)
- store.messages.snapshot.test.tsx: FOUND (신규 생성)
- __snapshots__/store.messages.snapshot.test.tsx.snap: FOUND (신규 생성)
- 6613f6b: FOUND (git log)
- 160c72a: FOUND (git log)
- vitest 163/163: PASSED
- tsc --noEmit: 에러 0건
- Ctrl+J 케이스: FOUND (components.multiline.test.tsx line 101)
- isTTY=false non-TTY 케이스: FOUND (tty-guard.test.ts line 35)
- toMatchSnapshot 4개: FOUND
- 스냅샷 파일: FOUND
