---
phase: 02-core-ux
plan: E
subsystem: render-quality
tags: [ink, cli-highlight, ctx-meter, tool-card, tdd, rnd-06, rnd-09]
dependency_graph:
  requires:
    - Plan A (store/protocol 계약 — ctxTokens selector)
    - Plan B (StatusBar, Message 기반 컴포넌트)
    - Plan C (MultilineInput, SlashPopup — 입력 레이어)
    - Plan D (ToolCard 기반 — useFocus/useInput 구현)
  provides:
    - Message.tsx cli-highlight 코드 펜스 하이라이트 (RND-06)
    - StatusBar.tsx CtxMeter 서브컴포넌트 격리 (RND-09)
    - ToolCard.tsx Space/Enter 토글 TDD 테스트 (E-2)
    - E-4 전체 게이트 통과 (vitest/tsc/lint/ci-no-escape)
  affects:
    - Phase 3 (Remote Room + Session) — Phase 2 exit criteria 통과 후 진입
tech_stack:
  added: []
  patterns:
    - cli-highlight ANSI pass-through (Ink Text 직접 렌더)
    - splitByCodeFence — non-greedy 정규식 코드 펜스 파싱 (T-02E-02 DoS 회피)
    - CtxMeter 격리 서브컴포넌트 — useShallow 독립 구독 (RND-09)
    - useStatusStore.getState() 레이아웃 계산 전용 읽기 (구독 없음)
key_files:
  created:
    - ui-ink/src/components/Message.test.tsx (5건 — cli-highlight TDD)
    - ui-ink/src/components/ToolCard.test.tsx (5건 — Space/Enter 토글 TDD)
    - ui-ink/src/components/StatusBar.test.tsx (4건 — CtxMeter 격리 TDD)
  modified:
    - ui-ink/src/components/Message.tsx (cli-highlight 통합, splitByCodeFence)
    - ui-ink/src/components/StatusBar.tsx (CtxMeter 서브컴포넌트 격리)
    - ui-ink/src/__tests__/app.smoke.test.tsx (lint 수정 — no-control-regex)
    - ui-ink/src/components/ConfirmDialog.tsx (미설치 react-hooks 플러그인 주석 제거)
decisions:
  - "CtxMeter 레이아웃 계산: useStatusStore.getState()로 읽기 — 구독 없이 초기값만 참조, CtxMeter 내부에서 실제 구독"
  - "splitByCodeFence non-greedy 정규식: catastrophic backtracking 회피 (T-02E-02)"
  - "ToolCard TDD: Plan D에서 이미 완성된 구현 위에 테스트 5건 추가 (RED→GREEN 즉시)"
  - "lint 수정: react-hooks 플러그인 미설치 상태에서 eslint-disable 주석이 에러 유발 — 주석 제거"
metrics:
  duration: "약 7분"
  completed_date: "2026-04-24"
  tasks_completed: 4
  tasks_total: 5
  files_created: 3
  files_modified: 4
  tests_added: 14
  tests_total: 120
---

# Phase 2 Plan E: Render Quality Summary

**한 줄 요약:** cli-highlight ANSI pass-through 코드 펜스 하이라이트, CtxMeter 독립 구독 격리, ToolCard TDD 14건 추가로 Phase 2 렌더 품질 레이어 완성 — E-5 수동 검증 대기 중

## 완료 태스크

| 태스크 | 이름 | 커밋 | 파일 |
|--------|------|------|------|
| E-1 | Message.tsx cli-highlight 통합 (RND-06) | a207536 | Message.tsx + Message.test.tsx (5건) |
| E-2 | ToolCard.tsx Space/Enter 토글 TDD | 6ed2d1a | ToolCard.test.tsx (5건) |
| E-3 | StatusBar CtxMeter 서브컴포넌트 격리 (RND-09) | bb3ad6c | StatusBar.tsx + StatusBar.test.tsx (4건) |
| E-4 | 전체 vitest + tsc + lint + CI 가드 통과 | bd3bac2 | app.smoke.test.tsx, ConfirmDialog.tsx (lint 수정) |
| E-5 | Phase 2 exit criteria 6개 수동 검증 | — | **PENDING HUMAN VERIFICATION** |

## 태스크별 상세

### E-1: Message.tsx cli-highlight 통합 (RND-06)

**구현 내용:**
- `splitByCodeFence(content)` — 정규식 `` /```(\w*)\n([\s\S]*?)```/g `` 으로 text/code 세그먼트 배열 분리
- `highlightCode(code, lang?)` — `try/catch` 래핑, `ignoreIllegals: true` 옵션, 실패 시 원본 반환 (T-02E-01)
- 코드 펜스 없는 content 는 파싱 생략 최적화
- Ink `<Text>` 에 ANSI 출력 직접 pass-through (`process.stdout.write` 금지 준수)

**TDD 결과:** 5/5 GREEN
- Test 1: ts 펜스 → highlight() 호출 + ANSI 렌더
- Test 2: 언어 미지정 → 실패 시 원본 반환
- Test 3: 잘못된 언어 → 크래시 없음
- Test 4: 일반 텍스트 → highlight() 미호출
- Test 5: 복수 펜스 → 각 블록 독립 highlight

### E-2: ToolCard.tsx Space/Enter 토글 TDD

**상황:** Plan D에서 이미 `useFocus({autoFocus: false})` + `useInput({isActive: isFocused})` 완성
- TDD RED→GREEN 즉시 통과 (기존 구현이 behavior를 이미 충족)
- 테스트 5건 추가: 토글 동작, Enter 키, result=undefined 크래시 없음, pending 상태

**TDD 결과:** 5/5 GREEN

### E-3: StatusBar CtxMeter 서브컴포넌트 격리 (RND-09)

**구현 내용:**
- `function CtxMeter()` — `useStatusStore(useShallow((s) => ({ctxTokens: s.ctxTokens})))` 독립 구독
- StatusBar 본체 selector에서 ctxTokens 제거 → `getState()` 로만 레이아웃 계산
- ctxTokens 변경 시 CtxMeter 서브트리만 리렌더 (StatusBar 본체 리렌더 방지)

**TDD 결과:** 4/4 GREEN
- Test 1: CtxMeter 렌더 확인
- Test 2: 50% ctx% 렌더
- Test 3: ctxTokens=undefined 시 CtxMeter 미렌더
- Test 4: 전 세그먼트(path/model/mode/turn/ctx/room) 동시 렌더

### E-4: 전체 게이트 통과

| 게이트 | 결과 |
|--------|------|
| vitest 120건 | PASSED |
| tsc --noEmit | PASSED (에러 0) |
| eslint --max-warnings=0 | PASSED |
| ci-no-escape.sh | PASSED |
| useStore() grep | 0건 |
| process.stdout.write grep (컴포넌트) | 0건 |
| child_process grep | 0건 |
| cli-highlight import | FOUND |
| CtxMeter grep | FOUND |
| useFocus grep | FOUND |

## Task E-5 현황 (PENDING)

**상태:** 인간 검증 대기 중

Phase 2 exit criteria 6개 수동 검증이 필요합니다:
- SC-1: 스트리밍 성능 (500 토큰, CPU 50% 미만, flicker 0, scrollback 청결)
- SC-2: MultilineInput (Enter/Shift+Enter/Ctrl+J/history/POSIX/500줄 paste)
- SC-3: SlashPopup (13개 명령, 필터, 방향키, Tab/Enter/Esc)
- SC-4: ConfirmDialog (confirm_write y/n/d, confirm_bash 위험도, sticky-deny)
- SC-5: StatusBar (전 세그먼트, graceful drop, CtxMeter flicker 없음)
- SC-6: 렌더 품질 (cli-highlight, DiffPreview placeholder, ToolCard 토글)

**검증 방법:** `cd ui-ink && bun start` (HARNESS_URL/HARNESS_TOKEN/HARNESS_ROOM 설정 필요)

## Deviations from Plan

### Auto-fixed Issues (Rule 1/Rule 3)

**1. [Rule 1 - Bug] ESLint no-control-regex 에러 — app.smoke.test.tsx**
- **Found during:** Task E-4
- **Issue:** line 66에 `\x1b` 정규식 리터럴에 `eslint-disable-next-line` 주석 누락
- **Fix:** `eslint-disable-next-line no-control-regex` 주석 추가 + 주석에서 `1049h` 문자열 제거 (ci-no-escape.sh 오탐 방지)
- **Files modified:** `ui-ink/src/__tests__/app.smoke.test.tsx`
- **Commit:** bd3bac2

**2. [Rule 1 - Bug] ESLint "react-hooks/rules-of-hooks" 규칙 미설치 에러 — ConfirmDialog.tsx**
- **Found during:** Task E-4
- **Issue:** `eslint-disable-next-line react-hooks/rules-of-hooks` 주석이 플러그인 미설치 상태에서 "Definition for rule was not found" 에러 유발
- **Fix:** 해당 주석을 한국어 의도 설명 주석으로 교체
- **Files modified:** `ui-ink/src/components/ConfirmDialog.tsx`
- **Commit:** bd3bac2

**3. [Rule 2 - Design] CtxMeter 레이아웃 계산 구독 분리**
- **Found during:** Task E-3
- **Issue:** StatusBar 본체에서 ctxTokens를 완전히 제거하면 ctx% 세그먼트의 textLen 계산 불가 (graceful drop 로직에 필요)
- **Fix:** 레이아웃 계산에만 `useStatusStore.getState().ctxTokens` 사용 (구독 없음) + 실제 렌더는 CtxMeter 서브컴포넌트가 담당

## Known Stubs

없음 — Plan E에서 새로 추가된 스텁 없음. DiffPreview placeholder는 Plan D에서 이미 문서화됨 (Phase 3 PEXT-02에서 교체 예정).

## Threat Flags

없음 — 모든 변경사항이 plan의 threat_model(T-02E-01~T-02E-06) 범위 내.

## Self-Check

- `ui-ink/src/components/Message.tsx` — FOUND
- `ui-ink/src/components/Message.test.tsx` — FOUND
- `ui-ink/src/components/ToolCard.test.tsx` — FOUND
- `ui-ink/src/components/StatusBar.tsx` — FOUND
- `ui-ink/src/components/StatusBar.test.tsx` — FOUND
- Commit a207536 — FOUND (E-1 cli-highlight)
- Commit 6ed2d1a — FOUND (E-2 ToolCard TDD)
- Commit bb3ad6c — FOUND (E-3 CtxMeter)
- Commit bd3bac2 — FOUND (E-4 lint 수정)
- vitest 120/120: PASSED
- tsc --noEmit: PASSED
- lint: PASSED
- ci-no-escape.sh: PASSED
- cli-highlight import in Message.tsx: FOUND
- function CtxMeter in StatusBar.tsx: FOUND
- useFocus in ToolCard.tsx: FOUND

**Self-Check: PASSED**
