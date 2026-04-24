---
phase: 3
slug: remote-room-session-control
status: draft
design_system: terminal-ansi
created: 2026-04-24
---

# Phase 3 — UI Design Contract: Remote Room + Session Control

> 터미널 TUI(Ink + ANSI) 전용 시각/상호작용 계약.
> gsd-ui-checker, gsd-planner, gsd-executor, gsd-ui-auditor 가 소비.
> 브라우저/DOM/CSS 없음 — 모든 설계 결정은 Ink Box/Text + ANSI 색상 기준.

---

## Design System

| 항목 | 값 |
|------|----|
| Tool | none (shadcn 해당 없음 — 터미널 TUI) |
| Preset | not applicable |
| 컴포넌트 기반 | Ink 7 (`Box`, `Text`, `Static`) |
| 색상 시스템 | ANSI named colors via Ink `color` prop (Chalk 래핑) |
| 아이콘 체계 | Unicode 단일 문자 + emoji (`🟢`, `↗`, `↘`) |
| 기존 테마 파일 | `ui-ink/src/theme.ts` (Phase 2 확정) |
| npm 패키지 (UI 관련) | ink@7 · chalk (ink 내부) · @inkjs/ui@2 · ink-spinner@5 |

**Phase 2 에서 확정된 설계 원칙 (변경 금지):**
- 완결 메시지 = `<Static>` / 스트리밍 중 active slot = 일반 트리
- 모달 = InputArea 조건부 치환 (Ink z-index 없음)
- `process.stdout.write` / `console.log` 직접 호출 금지 (ESLint 차단)
- Alternate screen(`\x1b[?1049h`) / 마우스 트래킹(`\x1b[?1000h`) 절대 금지

---

## Spacing Scale (터미널 columns/rows 단위)

터미널 TUI 에서 "px" 는 의미 없음. 모든 간격은 characters(열) 또는 lines(행) 기준.

| 토큰 | 값 | 용도 |
|------|----|------|
| gap-inline | 1 col | 인라인 요소 간 공백 (세그먼트 separator ` | `) |
| gap-prefix | 1 col | author prefix `[alice] ` 뒤 공백 |
| presence-sep | ` · ` (3 col) | Presence 멤버 구분자 (center dot) |
| overlay-pad | 0 line | 오버레이는 InputArea 행을 직접 치환 (줄 추가 없음) |
| system-msg | 1 line | Join/Leave 시스템 메시지 = 1줄 (Static append) |
| status-spinner | 2 col | spinner 문자 + 공백 (기존 StatusBar 유지) |

예외: 없음 (Phase 2 레이아웃 그대로 유지, 추가 여백 없음)

---

## Typography (Ink Text 속성)

터미널에는 font-size/font-family 없음. Ink `Text` 의 `bold`, `dim`, `italic`, `color` 조합으로 위계를 표현.

| 역할 | Ink 속성 | 적용 대상 |
|------|----------|-----------|
| 기본 본문 | color 기본 (흰색/터미널 default) | 일반 어시스턴트 메시지 |
| 강조 (Bold) | `bold` | author prefix `[alice]` 텍스트 자체, 경고 레이블 |
| 흐림 (Dim) | `dimColor` | StatusBar 세그먼트, muted 텍스트 (`theme.muted = 'gray'`) |
| 기울임 (Italic) | `italic` | "A 입력 중..." 오버레이 (관전자 상태) |
| Dim+Italic | `dimColor italic` | Join/Leave 시스템 메시지 (`↗ alice 님이 참여했습니다`) |

**weight 는 2종만:** 기본(normal) + bold. Ink 는 bold/dim/italic 만 지원, weight 수치 없음.

---

## Color Contract (ANSI 팔레트)

기존 `theme.ts` 에서 확정된 역할별 색상을 준수하고, Phase 3 신규 요소만 추가.

### 기존 확정 (변경 금지, 출처: `ui-ink/src/theme.ts`)

| 역할 | Ink color 값 | 사용처 |
|------|-------------|--------|
| user 메시지 | `cyan` | 사용자 입력 메시지 role |
| assistant 메시지 | `yellow` | 어시스턴트 응답 role |
| tool 결과 | `green` | ToolCard |
| system 메시지 | `gray` | 기존 시스템 메시지 |
| connected | `green` | StatusBar 연결 지시자 |
| disconnected | `red` | StatusBar 연결 끊김 |
| busy spinner | `cyan` | StatusBar busy 상태 |
| muted | `gray` | StatusBar 세그먼트, 부가 정보 |
| danger.safe | `green` | confirm_bash 안전 레이블 |
| danger.dangerous | `red` | confirm_bash 위험 레이블 |

### Phase 3 신규 추가

| 역할 | Ink color 값 | 사용처 | 근거 |
|------|-------------|--------|------|
| presence online | `green` | Presence 세그먼트 `🟢` emoji 앞 | 연결=green 기존 패턴 일관성 |
| reconnect overlay | `yellow` | `disconnected — reconnecting...` 전체 텍스트 | 경고(황색) — 오류(red)와 구분 |
| system join | `gray` + `dimColor` | `↗ alice 님이 참여했습니다` | 기존 system 색과 동일, dim 추가 |
| system leave | `gray` + `dimColor` | `↘ bob 님이 나갔습니다` | 위와 동일 |
| observer overlay | `gray` + `dimColor` + `italic` | "alice 입력 중..." | 비활성 상태 강조 |

### 사용자 색 해시 (DIFF-04, REM-02)

결정론적 사용자 색 배정 알고리즘:

```
PALETTE = ['cyan', 'green', 'yellow', 'magenta', 'blue', 'red', 'white', 'greenBright']
// white는 readability 확보를 위해 포함 (black 제외)
// 총 8색

hash(token) = token.split('').reduce((acc, ch) => (acc * 31 + ch.charCodeAt(0)) & 0xffff, 0)
userColor(token) = PALETTE[hash(token) % PALETTE.length]
```

- **일관성**: StatusBar presence 세그먼트 `[alice·me]` 의 `alice` 색 == Message author prefix `[alice]` 색
- **자기 자신**: 항상 `cyan` (기존 user 역할 색과 통일) — HARNESS_TOKEN 의 hash 결과와 무관
- **충돌 허용**: 두 사용자가 같은 색을 받을 수 있음 (3인 스케일에서 허용)

---

## Copywriting Contract (정확한 터미널 문자열)

Phase 3 에서 신규 추가되는 모든 레이블·메시지의 정확한 문자열.

### Presence 세그먼트 (REM-02, STAT-01)

| 상황 | 문자열 | Ink 속성 |
|------|--------|----------|
| 1인 (자신만) | `🟢 1명 [me]` | `color='green'` |
| 2인 (자신 + alice) | `🟢 2명 [alice·me]` | alice는 userColor(alice_token), `me` 는 `cyan` |
| 3인 (alice + bob + me) | `🟢 3명 [alice·bob·me]` | 각 이름 고유 색, `·` 는 `gray` |
| room 없음 (solo) | 세그먼트 미표시 | — |

**멤버 순서**: 서버 join 순서 그대로 표시. `me` 는 항상 맨 마지막.
**세그먼트 priority**: 30 (기존 StatusBar 에서 ctx > room 순으로 drop — STAT-02 유지).

### "A 입력 중" 오버레이 (REM-04, DIFF-01)

관전자(`room.activeIsSelf === false`)일 때 InputArea 를 치환하는 텍스트:

```
{activeInputFrom} 입력 중...
```

- Ink 속성: `dimColor italic`
- `activeInputFrom` 의 색: `userColor(activeInputFrom_token)` — 단, 이름 색만 적용, "입력 중..." 은 `gray`
- 렌더 위치: InputArea 가 있던 자리 (Divider 사이, ConfirmDialog 치환 패턴과 동일)
- Confirm 격리(CNF-04): `room.activeIsSelf === false` 이면 ConfirmDialog 도 관전 전용 read-only 뷰(`[alice 가 확인 중...]`) 로 치환

### 재연결 오버레이 (WSR-02)

WS 재연결 시도 중일 때 InputArea 를 치환:

```
disconnected — reconnecting... (attempt N/10)
```

- Ink 속성: `color='yellow'`
- `N`: 현재 시도 횟수 (1 기준 시작), `10`: WSR-01 max 10회 기준
- 재연결 성공 즉시 오버레이 제거, InputArea 복귀
- 10회 실패 후: `disconnected — reconnect failed. Ctrl+C to exit.` (color='red')

### Join/Leave 시스템 메시지 (REM-05)

`<Static>` 에 append — 히스토리 스크롤에 남음.

| 이벤트 | 문자열 | 색 |
|--------|--------|----|
| room_member_joined | `↗ {username} 님이 참여했습니다` | `gray` + `dimColor` |
| room_member_left | `↘ {username} 님이 나갔습니다` | `gray` + `dimColor` |
| room_joined (자신) | `↗ {roomName} 방에 입장했습니다 ({N}명)` | `gray` + `dimColor` |

- `{username}`: 해당 사용자의 `userColor(token)` 색 적용
- `{N}`: 입장 직후 멤버 수
- 시스템 메시지는 별도 `role: 'system'` 으로 Message 컴포넌트에서 구분 렌더

### Author Prefix (DIFF-02)

user 메시지 앞에 붙는 작성자 표시:

```
[alice] 질문 내용...
```

- `[alice]`: `bold` + `userColor(alice_token)` 색
- ` ` (1 col gap) 후 메시지 본문
- 자기 자신 메시지: `[me]` — `bold` + `cyan`
- Solo 모드(roomName 없음): prefix 미표시 (기존 Phase 2 동작 유지)

### Session Control 레이블 (SES-01, SES-02, SES-03)

| 상황 | 출력 | 비고 |
|------|------|------|
| one-shot 완료 후 종료 | ANSI 없이 plain text stdout | non-TTY = ANSI off |
| `--resume` 로드 | `세션 {id} 로드 중...` (gray) → REPL 진입 | Static 1줄 |
| `cancel` 전송 | `취소 요청 중…` (gray) | 기존 App.tsx 패턴 유지 |

---

## Component Inventory (Phase 3 신규/수정)

Phase 2 에서 확정된 컴포넌트를 베이스로, Phase 3 변경사항만 명세.

### 신규 컴포넌트

| 컴포넌트 | 파일 | 역할 |
|----------|------|------|
| `<PresenceSegment>` | `components/PresenceSegment.tsx` | StatusBar 내 Presence 서브컴포넌트 (CtxMeter 격리 패턴 동일) |
| `<ReconnectOverlay>` | `components/ReconnectOverlay.tsx` | 재연결 중 InputArea 치환 텍스트 |
| `<ObserverOverlay>` | `components/ObserverOverlay.tsx` | 관전자 시 "A 입력 중..." InputArea 치환 |
| `<SystemMessage>` | `components/SystemMessage.tsx` | join/leave 1줄 메시지 (Message.tsx 에 통합 가능) |

### 수정 컴포넌트

| 컴포넌트 | 변경 내용 |
|----------|-----------|
| `App.tsx` | InputArea 치환 조건 추가: `wsState === 'reconnecting' → <ReconnectOverlay>` / `!room.activeIsSelf → <ObserverOverlay>` |
| `StatusBar.tsx` | room 세그먼트를 단순 `#roomName` → `<PresenceSegment>` 로 교체 |
| `Message.tsx` | user 메시지에 `[author]` prefix 추가 (roomName 존재 시) |
| `store/room.ts` | `wsState: 'connected' | 'reconnecting' | 'failed'` 필드 추가, `reconnectAttempt: number` 추가 |

### 치환 우선순위 (App.tsx 조건부 렌더)

```
wsState === 'reconnecting'        → <ReconnectOverlay attempt={N} />
wsState === 'failed'              → <ReconnectOverlay failed />
confirmMode !== 'none' AND activeIsSelf  → <ConfirmDialog />
confirmMode !== 'none' AND !activeIsSelf → <ConfirmObserverView />
!activeIsSelf                     → <ObserverOverlay username={activeInputFrom} />
otherwise                         → <InputArea onSubmit={...} disabled={busy} />
```

---

## Interaction Contract

### Turn-taking (BB-2-DESIGN DQ3 결정: 거부)

| 상태 | InputArea | ConfirmDialog |
|------|-----------|---------------|
| `activeIsSelf === true` | 활성 | 활성 (y/n/d 키 동작) |
| `activeIsSelf === false` (관전) | `<ObserverOverlay>` | `<ConfirmObserverView>` (read-only) |
| `busy === true` (에이전트 실행 중) | disabled (커서 있음, 입력 막힘) | 해당 없음 |
| `wsState === 'reconnecting'` | `<ReconnectOverlay>` | `<ReconnectOverlay>` |

### 키보드 인터럽트 (WSR-04 — 기존 App.tsx 패턴 유지)

| 키 | 동작 |
|----|------|
| Ctrl+C (busy 중) | `cancel` 메시지 WS 전송 + "취소 요청 중…" 시스템 메시지 |
| Ctrl+C × 2 (idle, 2초 이내) | exit |
| Ctrl+D (idle, buffer 비어있음) | exit |

### 재연결 로직 (WSR-01 — 시각 계약만)

- 재연결 시도 시작 즉시 `ReconnectOverlay` 표시
- attempt 카운터 1씩 증가하여 `(attempt N/10)` 실시간 업데이트
- 성공 → 오버레이 즉시 제거, 입력 버퍼에 있던 내용 복원
- 10회 실패 → `color='red'` 로 텍스트 변경 + 입력 불가 유지

---

## Registry Safety (npm 패키지)

Phase 3 에서 신규 npm 패키지 추가 없음. 기존 Phase 1~2 에서 설치된 패키지만 사용.

| 패키지 | 용도 | 상태 |
|--------|------|------|
| `ink@7` | Ink 렌더러 | Phase 1 설치 완료 |
| `@inkjs/ui@2` | Spinner 등 | Phase 1 설치 완료 |
| `zustand@5` | 상태 관리 | Phase 1 설치 완료 |
| `ws@8` | WebSocket 클라이언트 | Phase 1 설치 완료 |
| `chalk` (ink 내장) | ANSI 색상 | ink 의존성 |

**Phase 3 에서 추가 npm 패키지가 필요한 경우**: vetting gate 통과 후 이 spec 에 명시 필요.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: 정확한 한국어 문자열 전수 명세 (join/leave/overlay/CTA)
- [ ] Dimension 2 Visuals: 5개 신규 컴포넌트 배치 + 치환 우선순위 명세
- [ ] Dimension 3 Color: 8색 해시 팔레트 + 역할별 ANSI 색 전수 명세
- [ ] Dimension 4 Typography: bold/dim/italic 위계 명세 (2종 weight)
- [ ] Dimension 5 Spacing: columns/lines 단위 간격 전수 명세
- [ ] Dimension 6 Registry Safety: Phase 3 신규 패키지 없음 확인

**Approval:** pending
