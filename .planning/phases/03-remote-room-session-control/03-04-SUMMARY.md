---
phase: 03-remote-room-session-control
plan: "04"
subsystem: ui-ink (컴포넌트 4종)
tags: [rem-02, rem-04, wsr-02, diff-01, diff-04, usercolor, presence, reconnect, observer, tdd]
one_liner: "userColor djb2 해시 유틸 + PresenceSegment/ReconnectOverlay/ObserverOverlay 컴포넌트 4종 TDD 구현 (DIFF-04, REM-02, WSR-02, REM-04)"

dependency_graph:
  requires:
    - ui-ink/src/store/room.ts (roomName/members 필드)
  provides:
    - "DIFF-04: userColor.ts — 결정론적 token 색 해시 순수함수"
    - "REM-02: PresenceSegment.tsx — StatusBar 서브컴포넌트 Presence 세그먼트"
    - "WSR-02: ReconnectOverlay.tsx — WS 재연결 중 InputArea 치환"
    - "REM-04/DIFF-01: ObserverOverlay.tsx — 관전자 InputArea 치환 '입력 중...'"
  affects:
    - ui-ink/src/utils/userColor.ts
    - ui-ink/src/components/PresenceSegment.tsx
    - ui-ink/src/components/ReconnectOverlay.tsx
    - ui-ink/src/components/ObserverOverlay.tsx

tech_stack:
  added: []
  patterns:
    - "TDD RED/GREEN 사이클 2회"
    - "CtxMeter 서브컴포넌트 격리 패턴 — solo 모드 null 반환"
    - "useShallow 멀티 필드 구독 (useRoomStore)"
    - "djb2 변형 hash (% 0xffff) + PALETTE 모듈로 — PALETTE 범위 보장"
    - "React key 로 index 대신 member 토큰 문자열 사용"

key_files:
  created:
    - path: ui-ink/src/utils/userColor.ts
      summary: "PALETTE 8색 + djb2 _hash() + userColor() 순수함수. 자기 자신(HARNESS_TOKEN)=cyan"
    - path: ui-ink/src/components/PresenceSegment.tsx
      summary: "solo(roomName='') → null, room → '🟢 N명 [alice·me]' 렌더. useShallow 구독"
    - path: ui-ink/src/components/ReconnectOverlay.tsx
      summary: "attempt prop → yellow 'reconnecting...(attempt N/10)', failed prop → red 'reconnect failed'"
    - path: ui-ink/src/components/ObserverOverlay.tsx
      summary: "username prop → userColor 색 displayName + dimColor italic '입력 중...'. null 안전"
    - path: ui-ink/src/__tests__/userColor.test.ts
      summary: "TDD RED: U1 빈토큰/U2 HARNESS_TOKEN=cyan/U3 결정론/U4 PALETTE 범위 4건"
    - path: ui-ink/src/__tests__/components.presence.test.tsx
      summary: "TDD RED: P1 solo null/P2 2명 렌더/P3 · 구분자 3건"
    - path: ui-ink/src/__tests__/components.observer.test.tsx
      summary: "TDD RED: R1~R3 ReconnectOverlay 3건 + O1~O3 ObserverOverlay 3건"

decisions:
  - "userColor PALETTE 빈 문자열(token='')도 안전: djb2(0) = 0 → PALETTE[0]='cyan'. 자기 자신 체크 전에 빈 토큰이면 myToken='' 동일 → cyan 반환 가능하나 정상 동작"
  - "ObserverOverlay username=null → '상대방' fallback. userColor('')로 호출되어 cyan 반환 — 구분 색이 없으므로 무방"
  - "React key는 member 토큰 문자열 사용 (index 사용 금지 — CLAUDE.md 절대 금지)"

metrics:
  duration: "약 3분 (2026-04-24 15:49~15:52)"
  completed_date: "2026-04-24"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 7
---

# Phase 03 Plan 04: Wave 2 신규 컴포넌트 4종 구현 Summary

userColor djb2 해시 유틸 + PresenceSegment/ReconnectOverlay/ObserverOverlay 컴포넌트 4종을 TDD RED/GREEN 사이클로 구현했습니다. tsc 에러 0, vitest 133건 green (기존 120건 + 신규 13건).

## 완료된 태스크

| Task | 이름 | 커밋 | 주요 파일 |
|------|------|------|-----------|
| 1 RED | userColor/PresenceSegment 실패 테스트 | c24fc32 | src/__tests__/userColor.test.ts, components.presence.test.tsx |
| 1 GREEN | userColor.ts + PresenceSegment.tsx 구현 | 874a4e2 | src/utils/userColor.ts, src/components/PresenceSegment.tsx |
| 2 RED | ReconnectOverlay/ObserverOverlay 실패 테스트 | 74e797a | src/__tests__/components.observer.test.tsx |
| 2 GREEN | ReconnectOverlay.tsx + ObserverOverlay.tsx 구현 | 42f88aa | src/components/ReconnectOverlay.tsx, ObserverOverlay.tsx |

## 검증 결과

```
tsc --noEmit: 에러 0
vitest: 19 Test Files passed, 133 Tests passed (기존 120건 + 신규 13건)
userColor 테스트 4건: U1~U4 green
PresenceSegment 테스트 3건: P1~P3 green
ReconnectOverlay 테스트 3건: R1~R3 green
ObserverOverlay 테스트 3건: O1~O3 green
4개 파일 모두 존재 확인
```

## Deviations from Plan

없음 — 플랜 그대로 실행됐습니다.

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (Task 1) | c24fc32 | test(03-04): userColor/PresenceSegment 실패 테스트 |
| GREEN (Task 1) | 874a4e2 | feat(03-04): userColor 해시 유틸 + PresenceSegment 구현 |
| RED (Task 2) | 74e797a | test(03-04): ReconnectOverlay/ObserverOverlay 실패 테스트 |
| GREEN (Task 2) | 42f88aa | feat(03-04): ReconnectOverlay + ObserverOverlay 구현 |

모든 RED/GREEN 게이트 커밋이 순서대로 존재합니다.

## Known Stubs

없음 — 4개 컴포넌트 모두 실제 prop/store 데이터 기반으로 렌더합니다.

## Threat Flags

플랜의 threat_model 항목(T-03-04-01~03) 처리:
- T-03-04-01 (Tampering): `% PALETTE.length` 모듈로 연산으로 인덱스 범위 보장. 빈 문자열 포함 모든 입력 안전
- T-03-04-02 (Information Disclosure): accept — userColor는 token 원문이 아닌 'me'/'cyan' 여부만 판단
- T-03-04-03 (Tampering): accept — Ink Text 컴포넌트가 문자열을 안전하게 출력

새 네트워크 엔드포인트 추가 없음. 순수 UI 컴포넌트만 작성됐습니다.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| ui-ink/src/utils/userColor.ts 존재 | FOUND |
| ui-ink/src/components/PresenceSegment.tsx 존재 | FOUND |
| ui-ink/src/components/ReconnectOverlay.tsx 존재 | FOUND |
| ui-ink/src/components/ObserverOverlay.tsx 존재 | FOUND |
| commit c24fc32 (RED Task 1) | FOUND |
| commit 874a4e2 (GREEN Task 1) | FOUND |
| commit 74e797a (RED Task 2) | FOUND |
| commit 42f88aa (GREEN Task 2) | FOUND |
| vitest 133건 green | PASSED |
| tsc --noEmit 에러 0 | PASSED |
