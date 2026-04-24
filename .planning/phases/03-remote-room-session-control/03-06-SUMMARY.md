---
phase: 03-remote-room-session-control
plan: "06"
subsystem: ui-ink/app
tags:
  - app-wiring
  - reconnect-overlay
  - presence
  - observer-mode
  - diff-preview
  - author-prefix
dependency_graph:
  requires:
    - "03-03"  # store/room.ts wsState/reconnectAttempt/activeIsSelf, store/messages.ts snapshotKey
    - "03-04"  # ReconnectOverlay.tsx, ObserverOverlay.tsx, PresenceSegment.tsx
    - "03-05"  # HarnessClient jitter backoff, resumeSession 옵션
  provides:
    - App.tsx 치환 우선순위: reconnecting > failed > confirm > observer > input
    - StatusBar.tsx PresenceSegment 연결 (REM-02)
    - Message.tsx room 모드 [author] prefix (DIFF-02)
    - DiffPreview.tsx old_content 기반 structuredPatch 실제 diff (PEXT-02)
    - MessageList.tsx snapshotKey Static key 연결 (REM-03)
    - Ctrl+C cancel stub 교정 → {type:'cancel'} (WSR-04)
  affects:
    - ui-ink/src/App.tsx
    - ui-ink/src/components/StatusBar.tsx
    - ui-ink/src/components/Message.tsx
    - ui-ink/src/components/MessageList.tsx
    - ui-ink/src/components/DiffPreview.tsx
    - ui-ink/src/components/ConfirmDialog.tsx
tech_stack:
  added: []
  patterns:
    - 치환 우선순위 패턴 (inputArea letvar 조건 분기)
    - structuredPatch (diff@9 라이브러리)
    - meta.author room 모드 prefix 표시
key_files:
  created: []
  modified:
    - ui-ink/src/App.tsx
    - ui-ink/src/components/StatusBar.tsx
    - ui-ink/src/components/Message.tsx
    - ui-ink/src/components/MessageList.tsx
    - ui-ink/src/components/DiffPreview.tsx
    - ui-ink/src/components/ConfirmDialog.tsx
    - ui-ink/src/__tests__/components.statusbar.test.tsx
    - ui-ink/src/components/StatusBar.test.tsx
decisions:
  - "치환 우선순위를 let inputArea 패턴으로 구현 — JSX 내 중첩 삼항 대신 가독성 개선"
  - "DiffPreview oldContent 없으면 '(신규 파일)' 메시지 표시, 있으면 structuredPatch diff"
  - "Message.tsx author label은 meta.author || 'me' fallback으로 항상 표시"
  - "StatusBar room 세그먼트 textLen은 max(roomName.length+10, 20) 고정 추정값 사용 (동적 크기 대응)"
metrics:
  duration: "약 20분"
  completed: "2026-04-24T07:10:23Z"
  tasks_completed: 2
  files_changed: 8
---

# Phase 03 Plan 06: Wave 4 최종 배선 Summary

**One-liner:** App.tsx 치환 우선순위(reconnecting>observer>confirm>input) + PresenceSegment·author prefix·structuredPatch diff 배선으로 Phase 3 클라이언트 기능 완성

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | App.tsx 치환 우선순위 확장 + MessageList/DiffPreview 배선 | 569e084 | `App.tsx`, `ConfirmDialog.tsx`, `DiffPreview.tsx`, `MessageList.tsx` |
| 2 | StatusBar PresenceSegment 연결 + Message author prefix | 27da2ad | `StatusBar.tsx`, `Message.tsx`, 테스트 2건 |

## What Was Built

### Task 1: App.tsx 배선 + 하위 컴포넌트 활성화

**App.tsx** (`ui-ink/src/App.tsx`):
- `useRoomStore`에서 `wsState`, `reconnectAttempt`, `activeIsSelf`, `activeInputFrom` 구독 추가
- `let inputArea` 패턴으로 치환 우선순위 구현:
  1. `wsState === 'reconnecting'` → `<ReconnectOverlay attempt={reconnectAttempt} />`
  2. `wsState === 'failed'` → `<ReconnectOverlay failed />`
  3. `confirmMode !== 'none'` → `<ConfirmDialog />`
  4. `!activeIsSelf` → `<ObserverOverlay username={activeInputFrom} />`
  5. 기본 → `<InputArea onSubmit={handleSubmit} disabled={busy} />`
- Ctrl+C cancel stub 교정: `{type:'input', text:'/cancel'}` → `{type:'cancel'}` (WSR-04)
- `resumeSession: process.env['HARNESS_RESUME_SESSION']` HarnessClient 연결 (SES-02)
- `handleSubmit` 내 `meta.author` 추가 (room 모드 author prefix용)

**MessageList.tsx** (`ui-ink/src/components/MessageList.tsx`):
- `snapshotKey` 구독 추가 (`useShallow`)
- `<Static key={snapshotKey}>` — Phase 3 snapshot 로드 시 Static 강제 재렌더 (REM-03)

**DiffPreview.tsx** (`ui-ink/src/components/DiffPreview.tsx`):
- `oldContent?: string` prop 추가
- `oldContent` 없으면 `(신규 파일) {path}` 초록 텍스트 표시
- `oldContent` 있으면 `structuredPatch(path, path, oldContent, newContent)` 호출 → hunk 렌더 (PEXT-02, W1)
- diff 라인 색상: `+` → green, `-` → red, `@@` hunk 헤더 → cyan

**ConfirmDialog.tsx** (`ui-ink/src/components/ConfirmDialog.tsx`):
- `DiffPreview`에 `oldContent={payload?.['oldContent']}` prop 전달 (W1)

### Task 2: StatusBar PresenceSegment + Message author prefix

**StatusBar.tsx** (`ui-ink/src/components/StatusBar.tsx`):
- `import {PresenceSegment}` 추가
- room 세그먼트 `render: () => <Text>{roomText}</Text>` → `render: () => <PresenceSegment />` 교체 (REM-02)
- `textLen: Math.max(roomName.length + 10, 20)` 고정 추정값으로 우선순위 드롭 보호

**Message.tsx** (`ui-ink/src/components/Message.tsx`):
- `useRoomStore(s => s.roomName)` 구독
- `authorLabel` 조건부 계산: room 모드 + user role일 때만 `meta.author || 'me'`
- `[authorLabel]` prefix를 `userColor(authorLabel)` 색상 + bold로 렌더 (DIFF-02)
- solo 모드(`roomName=''`)에서는 prefix 미표시 — Phase 2 동작 유지

## Verification

```
tsc --noEmit       : 에러 0
vitest run         : 21 Test Files, 146 Tests — 모두 통과
```

## Manual Verification Results (체크포인트 결과)

| SC | 항목 | 결과 | 비고 |
|----|------|------|------|
| SC-1 | 재연결 오버레이 (WSR-02) | APPROVED | 서버 강제 종료 후 오버레이 표시 + 재시작 후 복귀 확인 |
| SC-7 | 자동 테스트 vitest | APPROVED | 146/146 통과 (자동 확인) |
| SC-2 | Presence 세그먼트 (REM-02) | DEFERRED | 멀티 터미널 환경 미구성 |
| SC-3 | 관전 모드 (REM-04) | DEFERRED | 멀티 터미널 환경 미구성 |
| SC-4 | one-shot CLI (SES-01) | DEFERRED | 환경 미구성 |
| SC-5 | Ctrl+C cancel (WSR-04) | DEFERRED | 환경 미구성 |
| SC-6 | DiffPreview 실제 diff (PEXT-02) | DEFERRED | 환경 미구성 |

SC-2~SC-6은 멀티 터미널 환경 구성 후 `/gsd-verify-work`로 별도 검증 필요합니다.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] StatusBar 테스트 roomName 직접 텍스트 검사 교정**
- **Found during:** Task 2
- **Issue:** PresenceSegment로 교체 후 StatusBar 테스트가 `#testroom` 텍스트를 직접 검사하여 실패
- **Fix:** 테스트를 `🟢` 아이콘 기반으로 교정 (PresenceSegment가 아이콘을 렌더함)
- **Files modified:** `ui-ink/src/__tests__/components.statusbar.test.tsx`, `ui-ink/src/components/StatusBar.test.tsx`
- **Commit:** 27da2ad

## Requirements Coverage

| REQ-ID | 항목 | 상태 |
|--------|------|------|
| REM-01 | room 모드 진입 | DONE (App.tsx wsState 구독) |
| REM-02 | PresenceSegment StatusBar 표시 | DONE (StatusBar.tsx) |
| REM-03 | snapshot 로드 Static 재렌더 | DONE (MessageList snapshotKey) |
| REM-04 | 관전자 InputArea 비활성화 | DONE (ObserverOverlay 치환) |
| REM-05 | 관전자 ConfirmDialog read-only | DONE (ConfirmDialog 내부 activeIsSelf 분기) |
| REM-06 | 로컬-원격 동등성 | Phase 4 TST-02 자동 검증 이관 (W2) |
| SES-04 | resumeSession App.tsx 연결 | DONE |
| WSR-02 | ReconnectOverlay 표시 | DONE (App.tsx 치환 우선순위) |
| WSR-04 | Ctrl+C → {type:'cancel'} | DONE (stub 교정) |
| PEXT-02 | old_content DiffPreview | DONE (structuredPatch) |
| DIFF-02 | author prefix room 모드 | DONE (Message.tsx) |
| DIFF-03 | DiffPreview ConfirmDialog 배선 | DONE (oldContent prop 전달) |

## Known Stubs

없음. 이 플랜에서 처리한 모든 stub이 교정되었습니다.

(REM-06 로컬-원격 동등성은 계획상 Phase 4 TST-02 자동 검증으로 이관된 항목으로, stub이 아닌 설계 결정입니다.)

## Threat Surface Scan

이 플랜의 `<threat_model>`에 명시된 4건 외 추가 threat surface 없음:
- T-03-06-01: ObserverOverlay InputArea 완전 치환으로 키보드 이벤트 차단 — mitigate 완료
- T-03-06-02: 서버 PEXT-05 active_input_from 가드 — 이전 플랜에서 구현
- T-03-06-03: old_content 노출 — accept (인증된 클라이언트에게만 전송)
- T-03-06-04: meta.author 위조 — accept (소규모 협업 허용)

## Self-Check: PASSED

| Item | Result |
|------|--------|
| `ui-ink/src/App.tsx` 존재 | FOUND |
| `ui-ink/src/components/StatusBar.tsx` 존재 | FOUND |
| `ui-ink/src/components/Message.tsx` 존재 | FOUND |
| `ui-ink/src/components/MessageList.tsx` 존재 | FOUND |
| `ui-ink/src/components/DiffPreview.tsx` 존재 | FOUND |
| `ui-ink/src/components/ConfirmDialog.tsx` 존재 | FOUND |
| commit 569e084 (Task 1) | FOUND |
| commit 27da2ad (Task 2) | FOUND |
| tsc --noEmit 에러 | 0 |
| vitest 테스트 | 146/146 통과 |
| SC-1 approved | CONFIRMED |
| SC-7 approved | CONFIRMED |
