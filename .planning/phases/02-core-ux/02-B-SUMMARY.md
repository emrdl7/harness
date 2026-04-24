---
phase: 02-core-ux
plan: B
status: complete
wave: 1
subsystem: ui-components
tags: [ink, zustand, layout, static, statusbar, divider]
key-files:
  created:
    - ui-ink/src/components/Divider.tsx
    - ui-ink/src/components/StatusBar.tsx
    - ui-ink/src/components/MessageList.tsx
    - ui-ink/src/components/Message.tsx
    - ui-ink/src/slash-catalog.ts
    - ui-ink/src/theme.ts
  modified:
    - ui-ink/src/App.tsx
    - ui-ink/package.json
metrics:
  tasks_completed: 6
  tests_added: 16
  tests_total: 84
---

# Plan B — 기반 UI 컴포넌트 실행 완료

## 완료된 Task 요약

| Task | 설명 | 상태 |
|------|------|------|
| B-1 | Divider.tsx — 가로폭 자동 채움 구분선 | ✓ |
| B-2 | slash-catalog.ts + theme.ts — 정적 상수 파일 | ✓ |
| B-3 | StatusBar.tsx — 6 세그먼트 + 우선순위 드롭 | ✓ |
| B-4 | MessageList.tsx + Message.tsx — Static/active 분리 렌더 | ✓ |
| B-5 | App.tsx — D-01..D-04 레이아웃 + Ctrl+C/D 전면 재작성 | ✓ |
| B-6 | App smoke 테스트 + guard-forbidden.sh CI 가드 | ✓ |

## 주요 변경 사항

### Divider.tsx (신규)
- `columns` prop 기반 가로폭 채움 (`'─'.repeat(width)`)
- `useStdout().stdout.columns` 기본값, Math.max(1, ...) 방어
- `dimColor` 적용 — D-02 규격 (active↔input, input↔statusbar 두 자리)

### slash-catalog.ts (신규)
- 13개 slash 명령 정적 하드코딩 (D-06 결정 반영)
- `SLASH_CATALOG: readonly SlashCommand[]` + `filterSlash(query)` 헬퍼
- 서버 round-trip 없음 — UI 팝업 표시 전용

### theme.ts (신규)
- `role` / `status` / `mode` / `danger` / `muted` 색상 팔레트
- `as const` + `Object.freeze` 불변성 확보
- Ink `color` prop에 직접 전달 가능한 문자열 값

### StatusBar.tsx (신규)
- 6 세그먼트: path · model · mode · turn · ctx% · room
- Priority 기반 graceful drop (좁은 폭 시 낮은 priority 먼저 제거)
- `ink-spinner` 사용 (Phase 1 수동 스피너 완전 제거)
- `useShallow` 적용으로 불필요한 리렌더 억제
- `shortenPath()` — 홈 → `~`, 깊은 경로 → `…/parent/leaf`

### MessageList.tsx + Message.tsx (신규)
- `<Static items={completedMessages}>` — append-only, 재렌더 없음 (RND-01, RND-02)
- `activeMessage`는 일반 Box — 매 토큰마다 in-place 업데이트
- `key={m.id}` — index key 절대 금지 준수
- role 별 prefix: `❯ ` (user) / `● ` (assistant) / `└ ` (tool) / `  ` (system)

### App.tsx (전면 재작성)
- D-01 레이아웃: `MessageList → Divider → InputArea|ConfirmDialog → Divider → StatusBar`
- `bindConfirmClient(client)` / `bindConfirmClient(null)` — connect/cleanup 주입
- Ctrl+C busy → `{type:'cancel'}` 전송 + 안내 메시지 (D-07)
- Ctrl+C idle → 2초 내 2회 반복 시 exit (D-08)
- `stdout.on('resize', ...)` → ED2+ED3+Home escape 수동 발행 (RND-04 stale line 방지)
- Wave 2 교체 예정 placeholder: InputArea, ConfirmDialog 자리 확보

### package.json + guard-forbidden.sh (신규)
- `"guard"` 스크립트: `bash scripts/guard-forbidden.sh`
- `"ci"` 스크립트: `typecheck && test && guard` 통합
- guard 검사 항목: process.stdout.write / console.log / child_process / div/span / alternate screen / mouse tracking

## App.tsx 레이아웃 트리 (D-01)

```
<Box flexDirection='column'>
  <MessageList/>           ← <Static>(completedMessages) + active Box
  <Divider/>               ← active ↔ input 구분
  {confirm ? <ConfirmPlaceholder/> : <InputPlaceholder/>}
  <Divider/>               ← input ↔ statusbar 구분
  <StatusBar/>             ← 6 세그먼트 + spinner
</Box>
```

## Wave 2 교체 예정 슬롯

| 슬롯 | 현재 | Wave 2 교체 대상 |
|------|------|-----------------|
| InputArea | buffer + Text placeholder | `<MultilineInput>` (Plan C) |
| ConfirmDialog | `[confirm {mode}] y/n` 텍스트 | `<ConfirmDialog>` (Plan D) |
| Message.tsx | 기본 텍스트 렌더 | cli-highlight 코드 펜스 (Plan E) |

## 테스트 현황

- 신규 테스트: 16개 (divider 4, messagelist 6, statusbar 6)
- app.smoke.test.tsx: 레이아웃 렌더 + 금지 패턴 런타임 검증 4개
- 전체: 84/84 green

## Self-Check: PASSED

- `bun run test` → 84/84 ✓
- `bunx tsc --noEmit` → 에러 0 ✓
- `bash scripts/guard-forbidden.sh` → 전체 통과 ✓
- `bun run ci` → typecheck + test + guard 모두 green ✓
- `grep -rn '<div\|<span' src/` → 0 매칭 ✓
- `grep -n '<Static' src/components/MessageList.tsx` → 매칭 ✓
- `grep -n 'priority' src/components/StatusBar.tsx` → 매칭 ✓
- `grep -n 'bindConfirmClient' src/App.tsx` → 매칭 ✓
- `grep -n "stdout.on" src/App.tsx` → 매칭 ✓
- `grep -c 'name:' src/slash-catalog.ts` → 13 ✓
