# Phase 2: Core UX — Research

**Researched:** 2026-04-24
**Domain:** Node + Ink 7 + Zustand 5 + bun 기반 터미널 에이전트 UI — MultilineInput · SlashPopup · ConfirmDialog · ToolCard · StatusBar · 스트리밍 렌더
**Confidence:** HIGH (Phase 1 실제 구현 코드 + 기존 4개 리서치 문서 교차검증 + harness_server.py 실제 코드 분석)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01**: 수직 배치 순서 — `[Static 완결 메시지] → [active streaming 슬롯] → [구분선] → [InputArea / ConfirmDialog] → [구분선] → [StatusBar]`
- **D-02**: 구분선 — active slot ↔ input 사이: 있음 (`─`×터미널 폭). input ↔ status bar 사이: 있음. Static history 내부 구분선: 없음 (빈 줄로 그룹 구분)
- **D-03**: Confirm 교체 방식 — confirm 모드일 때 `<InputArea>` 대신 `<ConfirmDialog>`를 조건부 렌더링. 동일 위치에 자연스럽게 대체되며 레이아웃 선 유지
- **D-04**: Static/active 경계 — 완결 메시지(agent_end 수신 후)는 `<Static>`에 push. 스트리밍 중인 active 메시지는 일반 트리(active slot). 완결 전까지 `<Static>`에 포함하지 않음
- **D-05**: spinner — Phase 1 스텁(`spinRef` 카운터)을 `ink-spinner` 컴포넌트로 교체. active slot 앞에 표시. `<Static>`에는 절대 push하지 않음
- **D-06**: 슬래시 카탈로그 — `src/slash-catalog.ts`에 13개 명령 메타를 정적 하드코딩
- **D-07**: Ctrl+C cancel — Phase 2에서 `ClientMsg`에 `cancel` 타입 추가 + 전송만 구현. 서버가 아직 처리 불가하므로 클라이언트는 "취소 요청 중..." 시스템 메시지 표시
- **D-08**: 두 번 입력 exit — busy 상태가 아닐 때 Ctrl+C 두 번을 2초 이내 입력 시 exit
- **D-09**: 슬래시 트리거 — `/` 입력 즉시 전체 명령 목록 표시, 이후 타이핑으로 실시간 필터링
- **D-10**: Tab 동작 — 선택된 명령을 입력창에 채우고 팝업 닫힘. Enter로 다시 확인 후 제출
- **D-11**: 팝업 위치 — 입력창 바로 위에 인라인 렌더 (`flexDirection='column'`)

### Claude's Discretion

- **RND-04**: resize clear — `useStdout().stdout.on('resize')` 감지 후 `\x1b[2J\x1b[3J\x1b[H` 강제 clear 타이밍과 구현 방식
- **RND-09**: ctx 미터 격리 — ctx/토큰 업데이트가 전체 리렌더를 유발하지 않도록 분리하는 구체적 방법
- **RND-10**: 테마 감지 — `COLORFGBG` / `TERM_PROGRAM` 파싱 방식과 fallback 색 팔레트
- **INPT-08**: Tab 자동완성 인자 — 경로/세션/room 이름 자동완성 구현 범위
- **ToolCard 상세 펼침** — 1줄 요약 + 상세 펼침 트리거 키 및 UX

### Deferred Ideas (OUT OF SCOPE)

- WS 이벤트 기반 slash catalog broadcast — Phase 2에서 정적 JSON으로 결정. Phase 3 PEXT 논의 시 재검토
- SlashPopup 인자 자동완성(INPT-08) — Phase 2 exit criteria에 포함되지 않음
- PEXT-05 서버 cancel 처리 — Phase 3. Phase 2에서는 ClientMsg cancel 타입 추가 + 전송 stub만
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INPT-01 | `<MultilineInput>` 자체 구현 (`ink-text-input` 사용하지 않음) | Ink 7 `useInput` + `usePaste` 조합으로 구현. `string[]` 라인 버퍼 + `{row, col}` 커서 상태 |
| INPT-02 | Enter=제출, Shift+Enter·Ctrl+J=개행. 연속 줄 continuation 표시 | `useInput`의 `key.shift + key.return` 구분. Ctrl+J는 `ch === '\x0a'` 패턴 |
| INPT-03 | ↑/↓로 `~/.harness/history.txt` 기반 히스토리 탐색 | `fs.readFileSync`/`appendFileSync`로 파일 I/O. Python REPL 포맷(줄 단위)과 호환 |
| INPT-04 | POSIX 편집 단축키 — Ctrl+A/E/K/W/U | `useInput`에서 `key.ctrl + ch` 패턴 매칭. 라인 버퍼 조작 |
| INPT-05 | `usePaste` + bracketed paste로 붙여넣기 submit 차단. 500줄 paste 스모크 통과 | Ink 7 `usePaste` hook이 bracketed paste를 별도 이벤트로 처리 |
| INPT-06 | `<SlashPopup>` — `ink-select-input` 기반, 실시간 필터, 방향키 네비, Tab/Enter 보완, Esc 닫기 | Phase 1에서 `ink-select-input@6.2` ink@7 호환 확인됨 |
| INPT-07 | 슬래시 카탈로그(`src/slash-catalog.ts`)를 `harness_core`의 13개 명령 메타에서 파생 | 정적 하드코딩. D-06 결정. |
| INPT-08 | Tab 자동완성 — 슬래시 인자(경로, 세션 이름 등) | Claude 판단 범위. Phase 2 exit criteria 미포함 |
| INPT-09 | Ctrl+C = 현재 턴만 취소, 프로세스 유지. 2초 내 두 번째 입력 시 exit | D-07, D-08 결정. `cancel` ClientMsg 추가, 2초 타이머 ref |
| INPT-10 | Ctrl+D 종료 (입력 버퍼 비어있을 때만) | `useInput`에서 `key.ctrl + ch === 'd'` + `buffer.length === 0` 체크 |
| RND-01 | 완결 메시지=`<Static>`, 스트리밍 중 active slot=일반 트리 — 컴포넌트 구조로 고정 | D-04 결정. `agentEnd` 시 `completedMessages` 배열로 이동 |
| RND-02 | spinner · 진행 메시지를 `<Static>`에 push하지 않음 | D-05 결정. Python `c45e29f`/`c27111a` 동형 버그 방지 |
| RND-03 | Zustand selector는 단일 값만 구독. `useShallow` 적용 | Pitfall 8 대응. 컴포넌트별 분리 selector |
| RND-04 | 터미널 resize 시 `\x1b[2J\x1b[3J\x1b[H` 강제 clear | Claude 판단. `useStdout().stdout.on('resize')` + Ink 재렌더 유도 |
| RND-05 | 토큰 스트리밍 시 전체 messages 트리 리렌더 0회. 500 토큰 CPU 50% 미만 | `<Static>` 분리 + active slot 독립 컴포넌트 + `useMessagesStore` 구독 격리 |
| RND-06 | 코드 펜스 블록은 `cli-highlight`로 언어 감지 + syntax highlight | `cli-highlight@2.1.11` 이미 설치됨. `highlight(code, {language})` API |
| RND-07 | unified diff는 `diff@9 structuredPatch`로 hunk 분해 + ± 색 + 라인 번호 | `diff@9` 이미 설치됨. `structuredPatch()` API |
| RND-08 | tool 결과는 `<ToolCard>`로 1줄 요약 + 선택적 상세 펼침 | TOOL_META 테이블로 도구별 요약 포맷 정의 |
| RND-09 | ctx/토큰 meter를 status bar가 아닌 별도 경로로 업데이트 | Claude 판단. `useRef` 기반 또는 별도 슬라이스 격리 |
| RND-10 | 테마 — `COLORFGBG`/`TERM_PROGRAM` 감지 + `/theme` 수동 override | Claude 판단. `process.env.COLORFGBG` 파싱 |
| RND-11 | alternate screen · mouse tracking escape 절대 출력 금지 | Phase 1 CI 가드 이미 적용됨 (FND-11). Phase 2에서 유지 |
| CNF-01 | `confirm_write` 다이얼로그 — 경로 + `<DiffPreview>` + y/n/d 키 | Phase 2는 placeholder (경로 + 새 내용 미리보기). `old_content`는 PEXT-02 이후 |
| CNF-02 | `confirm_bash` 다이얼로그 — 커맨드 프리뷰 + 위험도 라벨 + y/n | 서버가 `danger_level` 미전송(verified). 클라이언트가 `classify_command` 로직 재구현 |
| CNF-03 | Sticky-deny — 동일 턴 내 동일 `confirm_*` 반복 시 클라에서 즉시 거부 | confirm 슬라이스에 `deniedPaths: Set<string>` + `deniedCmds: Set<string>` 상태 추가 |
| CNF-04 | Confirm 격리 — `room.activeIsSelf === true`일 때만 confirm 다이얼로그 활성 | Phase 1 `room.ts`에 `activeIsSelf` 필드 이미 존재. 조건부 렌더링 |
| CNF-05 | `cplan_confirm`도 동일 다이얼로그 프레임 재사용 | `ConfirmMode` 타입에 이미 `cplan_confirm` 있음 |
| STAT-01 | 기본 세그먼트 — `path · model · mode · turn · ctx% · room[members]` | `useStatusStore` + `useRoomStore`를 각각 단일 selector로 구독 |
| STAT-02 | 좁은 터미널 폭에서 우선순위 기반 drop | `useWindowSize`로 폭 감지. 세그먼트 우선순위: ctx% → room → mode → turn → path 순 축약 |
</phase_requirements>

---

## Summary

Phase 2는 Phase 1의 end-to-end 스모크 스켈레톤 위에 "로컬 단독 사용 시 Python REPL 완전 대체" 수준의 UX를 완성하는 단계다. 핵심 기술 도전은 세 가지다: (1) `<Static>` + active slot 분리로 500 토큰 스트리밍 시 CPU 50% 이하 달성, (2) `ink-text-input` 없이 Ink 7 hooks만으로 완전한 멀티라인 입력(Shift+Enter · history · POSIX 단축키 · bracketed paste · IME) 구현, (3) Confirm 다이얼로그를 InputArea 조건부 치환 패턴으로 구현(Ink에 z-index 없음).

현재 App.tsx는 Phase 1 최소 구현으로 전면 교체 대상이다. messages 슬라이스의 in-place token append 패턴, confirm 슬라이스 기본 구조, room 슬라이스의 `activeIsSelf`는 이미 Phase 1에서 구축됐다. Phase 2는 이 위에 컴포넌트 트리를 전면 재조립한다.

**Primary recommendation:** App.tsx를 Wave 1 초반에 컴포넌트 트리로 분해한 뒤, 나머지 Wave에서 각 컴포넌트를 완성하는 방식으로 진행. Static/active 경계 결정이 모든 컴포넌트 구조의 전제이므로 Wave 1에서 먼저 확정해야 한다.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| MultilineInput (버퍼·커서·submit) | Ink 컴포넌트 | Zustand input 슬라이스 | UI 이벤트는 컴포넌트에서 처리, 버퍼 상태는 store에 저장 |
| 히스토리 파일 read/write | input 슬라이스 action | Node.js fs 모듈 | store action에서 동기 파일 I/O (마운트 시 1회 로드) |
| Slash popup 필터링 | SlashPopup 컴포넌트 | slash-catalog.ts (정적) | 순수 클라이언트 필터링. 서버 RPC 없음 |
| 스트리밍 렌더 (Static/active) | MessageList 컴포넌트 | messages 슬라이스 | `<Static>` + active slot 분리 패턴 |
| ToolCard 요약 | ToolCard 컴포넌트 | TOOL_META 테이블 | 도구별 포맷은 정적 테이블, 상태는 messages 슬라이스 |
| Confirm 다이얼로그 | ConfirmDialog 컴포넌트 | confirm 슬라이스 + HarnessClient | 렌더는 컴포넌트, WS 응답은 슬라이스 action에서 client.send |
| Syntax highlight | Message/ToolCard 컴포넌트 | cli-highlight 라이브러리 | 순수 렌더 변환. store에 저장하지 않음 |
| Diff 렌더 (DiffPreview) | DiffPreview 컴포넌트 | diff@9 라이브러리 | `structuredPatch()`로 hunk 분해, Ink `<Box>`로 렌더 |
| StatusBar 세그먼트 | StatusBar 컴포넌트 | status/room 슬라이스 | 각 슬라이스를 단일 selector로 구독 (리렌더 격리) |
| 터미널 resize 감지 | App.tsx (useEffect) | useStdout().stdout | resize 이벤트에서 직접 escape 전송 후 setState 유발 |
| Ctrl+C cancel stub | App.tsx useInput | HarnessClient.send | Phase 2는 전송만. 서버 처리는 Phase 3 |
| danger_level 판정 (CNF-02) | ConfirmDialog 컴포넌트 | (클라이언트 내 로직) | 서버 미전송 확인됨. 클라이언트에서 간단한 패턴 매칭 |

---

## Standard Stack

### 이미 설치된 핵심 라이브러리

| Library | Version | Purpose | 확인 |
|---------|---------|---------|------|
| `ink` | ^7.0.1 | TUI 렌더러. `usePaste` · `useWindowSize` · `useInput` · `useStdout` · `<Static>` | Phase 1에서 설치됨 [VERIFIED] |
| `zustand` | ^5.0.12 | 5슬라이스 스토어 | Phase 1에서 설치됨 [VERIFIED] |
| `ink-spinner` | ^5.0.0 | spinner 컴포넌트 (Phase 1 스텁 교체) | Phase 1에서 설치됨 [VERIFIED] |
| `ink-select-input` | ^6.2.0 | SlashPopup 선택 UI | Phase 1에서 설치됨. ink@7 호환 [VERIFIED] |
| `@inkjs/ui` | ^2.0.0 | ConfirmInput · StatusMessage 등 | Phase 1에서 설치됨. ink@7 peer 실전 확인 필요 [ASSUMED] |
| `cli-highlight` | ^2.1.11 | 코드 syntax highlight | Phase 1에서 설치됨 [VERIFIED] |
| `diff` | ^9.0.0 | structuredPatch unified diff | Phase 1에서 설치됨 [VERIFIED] |
| `ink-link` | ^5.0.0 | OSC 8 하이퍼링크 | Phase 1에서 설치됨 [VERIFIED] |

### Phase 2에서 필요한 추가 Node.js 내장 API

| API | Purpose | Notes |
|-----|---------|-------|
| `node:fs` | history.txt read/write | `fs.readFileSync` / `fs.appendFileSync`. 동기 I/O OK (마운트 시 1회) |
| `node:os` | `~/.harness/history.txt` 경로 | `os.homedir()` |
| `node:path` | 경로 조합 | `path.join(os.homedir(), '.harness', 'history.txt')` |

---

## Architecture Patterns

### System Architecture Diagram

```
┌─── Phase 2 컴포넌트 트리 ────────────────────────────────────────────────┐
│                                                                         │
│  <App> (WS lifecycle, 전역 key: Ctrl+C/Ctrl+D)                          │
│  │                                                                      │
│  ├── <MessageList>                                                      │
│  │     ├── <Static items={completedMessages}>   ← agent_end 이후만     │
│  │     │     └── <Message> 완결 렌더 (각 id key)                       │
│  │     └── [active slot — 일반 트리]                                    │
│  │           ├── <Spinner> (busy === true)                              │
│  │           └── <Message> 스트리밍 중 (streaming === true)             │
│  │                                                                      │
│  ├── <Divider> (터미널 폭만큼 ─)                                        │
│  │                                                                      │
│  ├── {confirm.mode === 'none'                                           │
│  │     ? <InputArea>                                                    │
│  │         ├── <SlashPopup> (조건부: buffer[0] === '/')                 │
│  │         └── <MultilineInput>                                         │
│  │     : <ConfirmDialog mode={confirm.mode} payload={...}>}             │
│  │                                                                      │
│  ├── <Divider>                                                          │
│  │                                                                      │
│  └── <StatusBar>                                                        │
│        ├── connected indicator                                           │
│        ├── path · model · mode · turn                                   │
│        ├── ctx% meter                                                   │
│        └── room[members] (Phase 3에서 완성)                              │
│                                                                         │
│  데이터 흐름:                                                            │
│  WS → dispatch() → store slices → Zustand selector → 컴포넌트 구독      │
│  useInput(ch, key) → input slice → MultilineInput 렌더                  │
│  agentEnd → completedMessages push → <Static> 새 항목 렌더              │
└─────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
ui-ink/src/
├── App.tsx                    # Phase 2에서 전면 재작성 (레이아웃 컨테이너)
├── protocol.ts                # Phase 1 완성. cancel 타입 추가 필요
├── index.tsx                  # Phase 1 완성. 변경 없음
├── tty-guard.ts               # Phase 1 완성. 변경 없음
├── slash-catalog.ts           # Phase 2 신규 — 13개 명령 정적 목록
├── theme.ts                   # Phase 2 신규 — COLORFGBG/TERM_PROGRAM 감지
├── store/
│   ├── messages.ts            # Phase 1 완성. completedMessages 분리 추가
│   ├── input.ts               # Phase 2 확장 — history, slashOpen 추가
│   ├── status.ts              # Phase 1 완성. 변경 거의 없음
│   ├── room.ts                # Phase 1 완성. 변경 없음 (Phase 3에서 확장)
│   ├── confirm.ts             # Phase 2 확장 — stickyDeny 세트 추가
│   └── index.ts               # Phase 1 완성. 변경 없음
├── ws/
│   ├── client.ts              # Phase 1 완성. 변경 없음
│   ├── dispatch.ts            # Phase 2 확장 — slash_result cmd별 처리
│   └── parse.ts               # Phase 1 완성. 변경 없음
└── components/
    ├── MessageList.tsx         # Phase 2 신규 — Static + active slot 분리
    ├── Message.tsx             # Phase 2 신규 — role별 렌더 + syntax highlight
    ├── ToolCard.tsx            # Phase 2 신규 — tool_start/end 요약 1줄
    ├── DiffPreview.tsx         # Phase 2 신규 — diff@9 + Ink Box 렌더
    ├── InputArea.tsx           # Phase 2 신규 — MultilineInput + SlashPopup 컨테이너
    ├── MultilineInput.tsx      # Phase 2 신규 — 핵심 구현 (INPT-01..05, 09, 10)
    ├── SlashPopup.tsx          # Phase 2 신규 — ink-select-input 기반
    ├── ConfirmDialog.tsx       # Phase 2 신규 — 세 가지 모드 (write/bash/cplan)
    ├── StatusBar.tsx           # Phase 2 신규 — 세그먼트 + 폭 기반 drop
    └── Divider.tsx             # Phase 2 신규 — ─ × 터미널 폭
```

---

## Pattern 1: Static/Active Slot 분리 (RND-01, RND-02, RND-05)

**핵심 결정:** `completedMessages`와 `activeMessage`를 별도 상태로 분리.

```typescript
// store/messages.ts 확장 패턴
interface MessagesState {
  completedMessages: Message[]  // <Static>에 들어가는 배열 (append-only)
  activeMessage: Message | null // 스트리밍 중 — 일반 트리에만 렌더
  // ...
  agentEnd: () => void  // activeMessage → completedMessages로 이동
}

agentEnd: () => set((s) => {
  if (!s.activeMessage) return {busy: false}
  return {
    completedMessages: [...s.completedMessages, {...s.activeMessage, streaming: false}],
    activeMessage: null,
    busy: false,
  }
}),
```

```tsx
// components/MessageList.tsx
// Source: ARCHITECTURE.md §1.4 + Ink Static 공식 패턴
const completedMessages = useMessagesStore(useShallow(s => s.completedMessages))
const activeMessage = useMessagesStore(s => s.activeMessage)
const busy = useStatusStore(s => s.busy)

return (
  <Box flexDirection='column'>
    {/* 완결 메시지 — 한 번 렌더 후 절대 변경하지 않음 */}
    <Static items={completedMessages}>
      {(msg) => <Message key={msg.id} message={msg} />}
    </Static>
    {/* active slot — 스트리밍 중 메시지만 */}
    {busy && <Spinner type='dots' />}
    {activeMessage && <Message message={activeMessage} />}
  </Box>
)
```

**규칙:** spinner, activeMessage, InputArea는 절대 `<Static>`에 들어가지 않는다.

---

## Pattern 2: MultilineInput 자체 구현 (INPT-01..05)

**왜 자체 구현인가:** `ink-text-input@6`은 싱글라인 전용이고, 2026년 현재 npm에 프로덕션급 멀티라인 Ink 입력 패키지 부재 [CITED: STACK.md #2, FEATURES.md TS-I1].

```typescript
// components/MultilineInput.tsx 핵심 구조
// Source: Ink 7 공식 문서 (useInput, usePaste)
import {useInput, usePaste, Text, Box} from 'ink'

interface State {
  lines: string[]         // 라인 배열
  cursor: {row: number; col: number}
  historyIndex: number    // -1 = 현재 버퍼
  historyDraft: string    // history 탐색 중 편집 임시 저장
}

// usePaste — Ink 7에서 bracketed paste를 별도 이벤트로 제공
usePaste((text) => {
  // paste된 텍스트는 '\n'으로 분할, 그대로 삽입
  // submit 트리거 없음
  const pastedLines = text.split('\n')
  // cursor 위치에 삽입...
})

useInput((ch, key) => {
  // Enter (제출)
  if (key.return && !key.shift && ch !== '\x0a') {
    onSubmit(lines.join('\n'))
    return
  }
  // Shift+Enter 또는 Ctrl+J (개행)
  if ((key.return && key.shift) || ch === '\x0a') {
    insertNewline()
    return
  }
  // POSIX 단축키
  if (key.ctrl) {
    switch (ch) {
      case 'a': moveCursorToLineStart(); break
      case 'e': moveCursorToLineEnd(); break
      case 'k': deleteToLineEnd(); break
      case 'w': deleteWordBackward(); break
      case 'u': clearCurrentLine(); break
    }
    return
  }
  // 방향키 — history 또는 커서 이동
  if (key.upArrow) { recallHistory(-1); return }
  if (key.downArrow) { recallHistory(1); return }
  if (key.leftArrow) { moveCursorLeft(); return }
  if (key.rightArrow) { moveCursorRight(); return }
  // 일반 문자 입력
  if (ch && !key.ctrl && !key.meta) {
    insertChar(ch)
  }
})

// 렌더 — 커서 위치는 현재 줄에 역상(inverse) 문자로 표시
return (
  <Box flexDirection='column'>
    {lines.map((line, i) => (
      <Box key={i}>
        <Text color='cyan' bold>{i === 0 ? '❯ ' : '… '}</Text>
        {i === cursor.row
          ? renderLineWithCursor(line, cursor.col)
          : <Text>{line}</Text>
        }
      </Box>
    ))}
  </Box>
)
```

---

## Pattern 3: IME 한국어 조합 처리 (INPT-02 — 핵심 위험)

[ASSUMED] macOS IME 동작에 대한 실증 데이터 부재. 알려진 이슈:

- macOS IME 조합 중 Enter: 일부 터미널(macOS Terminal.app, iTerm2 default mode)에서 조합 완성 Enter가 submit으로 오인될 수 있음
- Ink 7 `useInput`은 `key.return`을 raw Enter로 처리. IME 조합 완성 Enter와 실제 submit Enter를 구분하는 공식 API 없음
- **Mitigation (Claude 판단):** `isComposing` 상태를 `useRef`로 추적하는 것은 DOM 환경에서만 가능. 터미널에서는 CSI u 프로토콜을 지원하는 터미널(Ghostty, Kitty, WezTerm)에서만 수식키와 Enter를 정확히 구분. 실용적 대책: 커서 위치가 빈 줄(Enter가 빈 줄 확정인 경우) + 1자 이상 내용이 있어야 submit 허용하는 가드.
- **검증 필수:** Phase 2 구현 직후 macOS에서 한국어 IME로 "안녕하세요" 조합 중 Enter 동작 수동 테스트 필수.

---

## Pattern 4: SlashPopup (INPT-06, INPT-07)

```typescript
// src/slash-catalog.ts — 정적 하드코딩 (D-06)
export interface SlashCommand {
  name: string      // '/help'
  description: string
  argHint?: string  // '/resume <session-id>'
}

export const SLASH_CATALOG: SlashCommand[] = [
  {name: '/help', description: '명령 목록'},
  {name: '/clear', description: '대화 초기화'},
  {name: '/undo', description: '마지막 턴 취소'},
  {name: '/save', description: '세션 저장'},
  {name: '/resume', description: '세션 재개', argHint: '<id>'},
  {name: '/index', description: '코드베이스 인덱싱'},
  {name: '/files', description: '파일 트리 보기'},
  {name: '/sessions', description: '저장된 세션 목록'},
  {name: '/who', description: '방 멤버 목록'},
  {name: '/plan', description: '계획 후 실행'},
  {name: '/cplan', description: 'Claude 계획'},
  {name: '/cd', description: '디렉토리 변경', argHint: '<path>'},
  {name: '/theme', description: '테마 변경', argHint: 'light|dark'},
]
```

```tsx
// components/SlashPopup.tsx
// Source: ink-select-input 공식 패턴
import SelectInput from 'ink-select-input'

// buffer가 '/'로 시작하면 카탈로그 필터링
const query = buffer.slice(1).toLowerCase()
const filtered = SLASH_CATALOG.filter(cmd =>
  cmd.name.slice(1).startsWith(query) ||
  cmd.description.includes(query)
)

// ink-select-input에서 Tab = 선택(D-10), Enter = 제출
// Esc = 팝업 닫기
```

**D-11 팝업 위치:** `<Box flexDirection='column'>` 안에서 팝업이 InputArea 바로 위에 오도록 배치.

---

## Pattern 5: ConfirmDialog (CNF-01..05)

```tsx
// components/ConfirmDialog.tsx
// D-03: InputArea 위치에 조건부 치환
const {mode, payload, clearConfirm} = useConfirmStore(useShallow(s => ({
  mode: s.mode,
  payload: s.payload,
  clearConfirm: s.clearConfirm,
})))
const activeIsSelf = useRoomStore(s => s.activeIsSelf)

// CNF-04: 관전자는 read-only
if (!activeIsSelf) {
  return <ConfirmReadOnlyView mode={mode} payload={payload} />
}

useInput((ch, key) => {
  if (ch === 'y') { resolve(true); return }
  if (ch === 'n') { resolve(false); return }
  if (ch === 'd' && mode === 'confirm_write') { toggleDiff(); return }
  if (key.escape) { resolve(false); return }
})
```

**CNF-02 danger_level 판정:**
서버가 `confirm_bash` 이벤트에 `danger_level` 필드를 전송하지 않음 [VERIFIED: harness_server.py line 210 — `send(ws, type='confirm_bash', command=command)`]. 클라이언트에서 간단한 패턴 매칭으로 판정:

```typescript
// 클라이언트 측 위험도 판정 (shell.py의 classify_command와 동일 로직)
function classifyCommand(cmd: string): 'safe' | 'dangerous' {
  const DANGEROUS_PATTERNS = [
    /\brm\b/, /\bsudo\b/, /\bchmod\b/, /\bchown\b/,
    /[|&;<>`]/, /\$\(/, // 셸 메타문자
    /\bdd\b/, /\bmkfs\b/, /\beval\b/,
  ]
  return DANGEROUS_PATTERNS.some(p => p.test(cmd)) ? 'dangerous' : 'safe'
}
```

**CNF-01 DiffPreview — Phase 2 범위:**
`confirm_write` 이벤트에 `old_content` 필드가 없음 (PEXT-02는 Phase 3). Phase 2는 경로 + 새 내용 처음 10줄 미리보기만 표시. 실제 diff는 Phase 3 이후.

**CNF-03 Sticky-deny 구현:**
```typescript
// store/confirm.ts 확장
interface ConfirmState {
  // ...
  deniedPaths: Set<string>
  deniedCmds: Set<string>
  addDenied: (type: 'path' | 'cmd', key: string) => void
  isDenied: (type: 'path' | 'cmd', key: string) => boolean
  clearDenied: () => void  // agentEnd 시 호출
}
```

---

## Pattern 6: StatusBar (STAT-01, STAT-02)

```tsx
// components/StatusBar.tsx — 각 슬라이스를 독립 selector로 구독
// RND-09 ctx 격리: ctx 업데이트가 다른 세그먼트 리렌더를 유발하지 않도록
const {columns} = useWindowSize()

// 각 세그먼트는 독립 컴포넌트로 분리하여 구독 범위 최소화
const workingDir = useStatusStore(s => s.workingDir)
const model = useStatusStore(s => s.model)
const mode = useStatusStore(s => s.mode)
const turns = useStatusStore(s => s.turns)
const ctxTokens = useStatusStore(s => s.ctxTokens)
const connected = useStatusStore(s => s.connected)

// STAT-02: 폭 기반 우선순위 drop
// 우선순위: connected indicator → model → turn → ctx% → mode → room → path
const segments = buildSegments(columns, {...})
```

**RND-09 ctx meter 격리 (Claude 판단):**
`useRef`를 사용한 격리:
```typescript
// ctx 업데이트는 별도 렌더 주기 없이 ref를 통해 직접 DOM에 반영
const ctxRef = useRef<number>(0)
// StatusBar 내 CtxMeter 서브컴포넌트만 ctxTokens를 구독
```
또는 ctxTokens를 status 슬라이스에서 분리된 별도 atom처럼 취급하여 `useStore(s => s.ctxTokens)`만 구독하는 `<CtxMeter>` 컴포넌트로 격리.

---

## Pattern 7: Resize 처리 (RND-04)

```typescript
// App.tsx useEffect 안
// Source: Python 5ba9e6f commit 경험 (ED3 필수)
const {stdout} = useStdout()

useEffect(() => {
  const handleResize = () => {
    // ED2 + ED3 + Home — Python 경험에서 ED3이 xterm.js 잔상 제거에 필수
    stdout.write('\x1b[2J\x1b[3J\x1b[H')
    // Ink가 다음 프레임에서 전체 재렌더하도록 강제 state 변경
    setResizeCount(c => c + 1)
  }
  stdout.on('resize', handleResize)
  return () => { stdout.off('resize', handleResize) }
}, [stdout])
```

**주의:** `resizeCount`는 렌더 trigger용 더미 state여야 하며, 이를 구독하는 컴포넌트 최소화. App.tsx 루트에서 상태 변경 시 전체 트리가 리렌더되므로 OK (resize는 드문 이벤트).

---

## Pattern 8: Syntax Highlight + Diff (RND-06, RND-07)

```typescript
// cli-highlight 사용 패턴
// Source: cli-highlight@2.1.11 공식 README
import {highlight} from 'cli-highlight'

function highlightCode(code: string, lang?: string): string {
  try {
    return highlight(code, {language: lang, ignoreIllegals: true})
  } catch {
    return code  // 언어 감지 실패 시 원본 반환
  }
}
```

```typescript
// diff@9 structuredPatch 사용 패턴
// Source: jsdiff 공식 문서
import {structuredPatch} from 'diff'

interface Hunk {
  oldStart: number
  newStart: number
  lines: string[]  // '+line' | '-line' | ' context'
}

function renderDiff(oldStr: string, newStr: string, filePath: string): Hunk[] {
  const patch = structuredPatch(filePath, filePath, oldStr, newStr)
  return patch.hunks
}
```

```tsx
// DiffPreview 컴포넌트
{hunk.lines.map((line, i) => (
  <Text
    key={i}
    color={line.startsWith('+') ? 'green' : line.startsWith('-') ? 'red' : undefined}
    dimColor={!line.startsWith('+') && !line.startsWith('-')}
  >
    {line}
  </Text>
))}
```

---

## Pattern 9: ToolCard (RND-08)

```typescript
// TOOL_META 테이블 — 도구별 요약 포맷
const TOOL_META: Record<string, (args: Record<string, unknown>, result: string) => string> = {
  read_file: (args, result) => {
    // result 파싱하여 "read 120 lines (of 340)" 포맷
    const lines = result.split('\n').length
    return `read ${lines} lines`
  },
  write_file: (args) => {
    const path = args['path'] as string
    return `write ${path}`
  },
  run_command: (args, result) => {
    // exitCode, duration 파싱
    return `exit 0, 1.2s`
  },
  // ...
}
```

**ToolCard 상세 펼침 (Claude 판단):**
1줄 요약 기본. 상세 펼침은 toggle state를 `Message` 안에서 `useState`로 관리 (store에 불필요). 단축키는 해당 ToolCard에 focus되어 있을 때 `Enter` 또는 `Space`로 토글.

---

## Pattern 10: Ctrl+C Cancel Stub (D-07, D-08)

```typescript
// protocol.ts에 cancel 타입 추가
export interface CancelMsg { type: 'cancel' }
export type ClientMsg =
  | InputMsg | ConfirmWriteResponse | ConfirmBashResponse | SlashMsg | PingMsg
  | CancelMsg  // Phase 2 추가

// App.tsx 또는 InputArea.tsx
const ctrlCCount = useRef(0)
const ctrlCTimer = useRef<NodeJS.Timeout | null>(null)

useInput((ch, key) => {
  if (key.ctrl && ch === 'c') {
    const {busy} = useStatusStore.getState()
    if (busy) {
      // 첫 번째 Ctrl+C: cancel 전송 (D-07)
      clientRef.current?.send({type: 'cancel'})
      useMessagesStore.getState().appendSystemMessage('취소 요청 중...')
    } else {
      // busy 아닐 때: 2초 내 두 번째 Ctrl+C = exit (D-08)
      ctrlCCount.current++
      if (ctrlCCount.current >= 2) {
        exit()
        return
      }
      ctrlCTimer.current = setTimeout(() => {
        ctrlCCount.current = 0
      }, 2000)
    }
  }
})
```

---

## Pattern 11: History 파일 (INPT-03)

```typescript
// store/input.ts 확장
import {homedir} from 'node:os'
import {join} from 'node:path'
import {readFileSync, appendFileSync, existsSync} from 'node:fs'
import {mkdirSync} from 'node:fs'

const HISTORY_PATH = join(homedir(), '.harness', 'history.txt')

function loadHistory(): string[] {
  if (!existsSync(HISTORY_PATH)) return []
  return readFileSync(HISTORY_PATH, 'utf-8')
    .split('\n')
    .filter(Boolean)
    .reverse()  // 최신이 앞
}

function appendHistory(text: string): void {
  mkdirSync(join(homedir(), '.harness'), {recursive: true})
  appendFileSync(HISTORY_PATH, text + '\n', 'utf-8')
}
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Spinner 애니메이션 | 직접 setInterval + SPIN 배열 | `<Spinner type='dots'>` from `ink-spinner` | Phase 1 스텁이 이미 있음. 교체만 하면 됨 |
| Select 목록 렌더 | 직접 키보드 탐색 구현 | `ink-select-input@6.2` | SlashPopup의 ↑↓ 선택 이미 지원됨 |
| JSON parse + type guard | `typeof msg.type === 'string' && ...` | 기존 `parseServerMsg` in `ws/parse.ts` | Phase 1에서 완성됨 |
| 터미널 폭 감지 | `process.stdout.columns` 직접 구독 | Ink `useWindowSize()` | resize 이벤트까지 자동 처리됨 |
| Diff 알고리즘 | Myers diff 직접 구현 | `structuredPatch()` from `diff@9` | 수십 년 검증된 알고리즘 |
| Syntax highlight | ANSI 색상 직접 매핑 | `highlight()` from `cli-highlight` | 185개 언어 지원, 언어 감지 포함 |
| WS 메시지 dispatch | `if/else` 체인 | 기존 `dispatch.ts` exhaustive switch | Phase 1에서 완성됨. 케이스 추가만 |

---

## Common Pitfalls

### Pitfall A: Spinner를 `<Static>`에 push (Pitfall 20 — 최고 위험)
**What goes wrong:** busy 상태 변화가 completedMessages 배열에 들어가면 scrollback에 spinner 프레임이 수백 줄 쌓임. Python `c45e29f`/`c27111a` 동형 버그.
**How to avoid:** active slot과 spinner는 반드시 일반 트리에만. `<Static>`에는 `completedMessages`만.
**Warning signs:** scrollback에 `⠋⠙⠹` 패턴이 줄줄이.

### Pitfall B: streaming=true인 메시지를 completedMessages로 이동 (Pitfall 6)
**What goes wrong:** `<Static>`에 들어간 후 토큰이 더 와도 반영 안 됨. "답변이 한 글자만 나옴".
**How to avoid:** `agentEnd` 이벤트에서만 `streaming: false` + completedMessages 이동.

### Pitfall C: Ctrl+J를 개행으로 처리할 때 IME Enter와 충돌
**What goes wrong:** Ctrl+J(`\x0a`)가 일부 터미널에서 일반 Enter와 동일하게 들어올 수 있음.
**How to avoid:** `key.return && !key.shift`를 명확히 체크. Ctrl+J는 `ch === '\x0a' && !key.return` 조건으로.

### Pitfall D: resize 이벤트 핸들러에서 stdout.write + setState 동시에
**What goes wrong:** Ink가 렌더 중에 escape를 쓰면 커서 위치 꼬임.
**How to avoid:** `stdout.write(CLEAR_ESCAPE)` 후 `setTimeout(() => setResizeCount(c+1), 0)`으로 micro-task 분리.

### Pitfall E: useStore에서 전체 messages 구독
**What goes wrong:** 입력 타이핑마다 전체 메시지 리스트 리렌더.
**How to avoid:** `MessageList`는 `completedMessages`와 `activeMessage`만 구독. InputArea는 `buffer`만 구독.

### Pitfall F: ink-select-input에서 Tab key 충돌
**What goes wrong:** `ink-select-input`이 Tab을 기본적으로 처리하지 않을 수 있음. `<MultilineInput>`의 Tab 처리와 충돌 가능.
**How to avoid [ASSUMED]:** SlashPopup이 active일 때는 MultilineInput의 Tab 핸들러를 비활성화. `slashOpen` state로 분기.

---

## 10 Research Questions 답변

### Q1: Ink 7 `usePaste`가 bun에서 bracketed paste를 정확히 전달하는가
[ASSUMED] bun + Ink 7 `usePaste` 공식 호환 매트릭스 부재. 알려진 사실:
- Ink 7이 `usePaste` hook을 신설했으며, bracketed paste 마커(`\x1b[200~...\x1b[201~`)를 stdin 레벨에서 처리
- bun의 stdin raw mode 처리는 Node와 동일 libuv 기반
- xterm.js(VS Code), iTerm2, Ghostty, macOS Terminal.app은 bracketed paste 모드 지원
- **검증 필수:** 500줄 paste 스모크 테스트가 Phase 2 exit criteria에 포함됨

### Q2: macOS IME 한국어 조합 완성 시점에서 Enter 전달
[ASSUMED] Pitfall 16 참조. 실증 데이터 없음. Phase 2 구현 후 즉시 수동 검증 필요.

### Q3: `@inkjs/ui@2` + `ink-select-input@6.2`의 ink@7 peer 실전 호환
[VERIFIED: Phase 1 스모크] Phase 1에서 설치 완료 및 기본 동작 확인됨. Phase 2에서 SlashPopup(`ink-select-input`) + ConfirmDialog(`@inkjs/ui ConfirmInput`) 실제 사용 시 추가 검증 필요.

### Q4: `<MultilineInput>` 자체 구현 방법
상기 Pattern 2 참조. `useInput` + `usePaste` + `string[]` 라인 버퍼.

### Q5: `<Static>` + active slot 분리 패턴
상기 Pattern 1 참조. `completedMessages` + `activeMessage` 스토어 분리.

### Q6: `cli-highlight@2`와 `diff@9 structuredPatch` API
상기 Pattern 8 참조.

### Q7: StatusBar 좁은 폭 graceful drop
상기 Pattern 6 참조. `useWindowSize()` + 우선순위 배열로 순차 drop.

### Q8: `confirm_write`의 `danger_level` 필드 — 서버가 전송하는가
[VERIFIED: harness_server.py line 210] 서버는 `danger_level` 미전송. `confirm_bash` 이벤트에는 `command` 필드만 있음. 클라이언트에서 패턴 매칭으로 판정해야 함.

### Q9: resize 이벤트 처리
상기 Pattern 7 참조. ED2 + ED3 + Home escape sequence 필수 (Python 5ba9e6f 경험).

### Q10: Zustand selector 최적화 — RND-05
상기 Pattern 1 참조. `completedMessages`/`activeMessage` 분리 + 컴포넌트별 단일 selector.

---

## Component Breakdown (파일별 구현 책임)

| 파일 | Phase 1 상태 | Phase 2 작업 |
|------|------------|------------|
| `App.tsx` | 최소 구현 (전면 교체 대상) | 레이아웃 재조립, WS lifecycle 유지, 전역 키(Ctrl+C/D), resize useEffect |
| `store/messages.ts` | in-place token append 완성 | `completedMessages` + `activeMessage` 분리, `agentEnd` 로직 변경 |
| `store/input.ts` | buffer/setBuffer/clearBuffer만 | `history: string[]`, `historyIndex`, `slashOpen`, `historyLoad/Save` 추가 |
| `store/confirm.ts` | mode/payload/setConfirm/clearConfirm | `deniedPaths`, `deniedCmds`, `addDenied`, `resolve(accept)` + WS 응답 전송 |
| `store/status.ts` | connected/busy/model 등 | 변경 거의 없음 |
| `store/room.ts` | activeIsSelf 포함 | 변경 없음 (Phase 3에서 확장) |
| `protocol.ts` | 23종 ServerMsg 완성 | `CancelMsg` 추가, `ClientMsg`에 편입 |
| `ws/dispatch.ts` | exhaustive switch 완성 | `slash_result` cmd별 처리 확장 (`/clear` → `clearMessages`, `/cd` → `setWorkingDir` 등) |
| `ws/client.ts` | HarnessClient 완성 | 변경 없음 |
| `slash-catalog.ts` | 없음 | 신규 생성. 13개 명령 정적 목록 |
| `theme.ts` | 없음 | 신규 생성. `COLORFGBG`/`TERM_PROGRAM` 파싱 |
| `components/MessageList.tsx` | 없음 | Static + active slot. `<Spinner>` |
| `components/Message.tsx` | 없음 | role별 렌더. syntax highlight. Markdown 코드펜스 파싱 |
| `components/ToolCard.tsx` | 없음 | TOOL_META + pending/ok/err 시각화 |
| `components/DiffPreview.tsx` | 없음 | diff@9 + Ink Box 렌더. Phase 2는 새 내용 미리보기만 |
| `components/InputArea.tsx` | 없음 | MultilineInput + SlashPopup 컨테이너 |
| `components/MultilineInput.tsx` | 없음 | 핵심 구현. useInput + usePaste + history |
| `components/SlashPopup.tsx` | 없음 | ink-select-input 기반. slash-catalog 필터링 |
| `components/ConfirmDialog.tsx` | 없음 | 3 모드 (write/bash/cplan). sticky-deny. CNF-04 격리 |
| `components/StatusBar.tsx` | 없음 | 세그먼트 + useWindowSize 폭 기반 drop |
| `components/Divider.tsx` | 없음 | `─`.repeat(columns) |

---

## Testing Approach

### 기존 30개 테스트 보존 전략

기존 테스트는 `store/messages.ts`, `protocol.ts`, `ws/dispatch.ts`, `tty-guard.ts`를 대상으로 함. Phase 2에서 이 파일들을 수정할 때 기존 테스트가 깨지지 않도록:

- `store/messages.ts` 변경: `messages` 배열 분리 시 기존 `agentStart`/`appendToken`/`agentEnd` 테스트에서 `completedMessages` + `activeMessage`를 각각 검증하도록 테스트 업데이트 필요
- `protocol.ts` 변경: `ClientMsg`에 `CancelMsg` 추가 — 기존 테스트 영향 없음 (추가이므로)
- `ws/dispatch.ts` 변경: `slash_result` 케이스 확장 — 기존 exhaustive switch 테스트에 새 케이스 추가

### 신규 테스트 (Phase 2에서 추가할 것)

```typescript
// 우선순위 1: store reducer 단위 테스트
describe('completedMessages 분리', () => {
  it('agentEnd 시 activeMessage → completedMessages로 이동')
  it('스트리밍 중 activeMessage가 completedMessages에 없음')
})

// 우선순위 2: 컴포넌트 렌더 테스트 (ink-testing-library)
describe('ConfirmDialog', () => {
  it('mode=confirm_write 시 경로와 y/n 힌트 표시')
  it('mode=confirm_bash 시 커맨드와 위험도 라벨 표시')
  it('activeIsSelf=false 시 read-only 뷰')
})

describe('StatusBar', () => {
  it('좁은 폭(40)에서 path 축약')
  it('connected=false 시 ○ disconnected 표시')
})

// 우선순위 3: input 단위 테스트 (stdin mock)
describe('MultilineInput', () => {
  it('Enter 시 onSubmit 호출')
  it('Shift+Enter 시 개행')
  it('Ctrl+U 시 현재 줄 전체 삭제')
})

// 우선순위 4: 회귀 스냅샷
describe('Static 오염 방지', () => {
  it('500 토큰 스트리밍 후 completedMessages에 streaming:true 항목 없음')
  it('agentEnd 전까지 completedMessages에 active 메시지 없음')
})
```

### 수동 검증 필수 항목 (vitest로 자동화 불가)

1. macOS IME 한국어 조합 중 Enter → submit 안 됨 확인
2. 500줄 텍스트 paste → 첫 줄 submit 없이 전체 보존
3. 터미널 폭 200↔40 반복 resize → stale line 없음 (한국어 포함)
4. scrollback에 spinner 프레임 없음 (스트리밍 1분 후 Cmd+↑)
5. Ctrl+C 첫 번째 → "취소 요청 중..." 메시지, 두 번째(2초 내) → exit

---

## Wave Breakdown Recommendation

Phase 2는 다음 3 Wave로 분할하는 것을 권장한다.

### Wave 1 (기반 재조립)

**병렬 실행 가능:**

**Plan A: 스토어 확장 + 프로토콜 업데이트**
- `store/messages.ts` — `completedMessages` / `activeMessage` 분리 (RND-01)
- `store/input.ts` — history, slashOpen 추가 (INPT-03)
- `store/confirm.ts` — stickyDeny, resolve + WS 응답 (CNF-03)
- `protocol.ts` — `CancelMsg` 추가 (D-07)
- `ws/dispatch.ts` — `slash_result` cmd별 처리 확장
- 대응하는 store 단위 테스트 업데이트

**Plan B: 기반 컴포넌트 신규 생성**
- `components/Divider.tsx` — 단순 구현
- `components/StatusBar.tsx` — STAT-01, STAT-02
- `components/MessageList.tsx` — Static/active slot 구조 (D-04, D-05)
- `components/Message.tsx` — role별 기본 렌더 (syntax highlight 없이)
- `slash-catalog.ts` — 13개 명령 정적 목록 (INPT-07)
- `theme.ts` — 기본 테마 감지 (RND-10)
- `App.tsx` 전면 재작성 — 레이아웃 조립 + resize useEffect (D-01, D-02, RND-04)

### Wave 2 (입력 + Confirm)

**Plan C: MultilineInput + SlashPopup**
- `components/MultilineInput.tsx` — INPT-01..05 (bracketed paste 포함), INPT-09, INPT-10
- `components/InputArea.tsx` — MultilineInput + SlashPopup 컨테이너
- `components/SlashPopup.tsx` — INPT-06, D-09..11
- history 파일 I/O 통합
- vitest: MultilineInput 키 시퀀스 테스트

**Plan D: ConfirmDialog + ToolCard**
- `components/ConfirmDialog.tsx` — CNF-01..05 (Phase 2 범위: DiffPreview placeholder)
- `components/DiffPreview.tsx` — RND-07 (새 내용 미리보기)
- `components/ToolCard.tsx` — RND-08 + TOOL_META
- vitest: ConfirmDialog 렌더 테스트

### Wave 3 (렌더 품질 + 최종 통합)

**Plan E: Syntax Highlight + 렌더 최적화**
- `components/Message.tsx` — RND-06 cli-highlight 통합
- `components/ToolCard.tsx` — 상세 펼침 UX (Claude 판단)
- RND-05 검증: 500 토큰 스트리밍 CPU 50% 이하
- RND-09 ctx meter 격리 최종 확인
- 전체 통합 smoke + "Looks Done But Isn't" 체크리스트 검증

---

## Risk Factors and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| macOS IME Enter submit 오발사 | MEDIUM | HIGH | Wave 2 완료 직후 수동 검증. composition guard 추가 여지 확보 |
| `usePaste`가 bun에서 bracketed paste 미처리 | LOW | HIGH | Wave 2에서 500줄 paste 스모크 즉시 실행. 실패 시 stdin 레벨 수동 파싱 fallback |
| `<Static>` completedMessages 분리로 기존 30개 테스트 일부 파손 | HIGH | MEDIUM | Wave 1에서 테스트 업데이트를 store 변경과 동시에 수행 |
| `ink-select-input` Tab key 동작이 기대와 다름 | MEDIUM | MEDIUM | Wave 2에서 실제 사용 시 동작 확인. 필요 시 자체 Select 컴포넌트로 대체 |
| resize + Static 조합에서 stale line 발생 | MEDIUM | HIGH | Wave 3에서 200↔40 resize 스냅샷 회귀 테스트 |
| ToolCard appendToolEnd 로직이 멀티 tool 시 잘못된 항목 업데이트 | MEDIUM | MEDIUM | Phase 1 `messages.ts`의 reverse-find 로직 검증. tool name + streaming 동시 체크 |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `ink@7` | 모든 컴포넌트 | ✓ | 7.0.1 | — |
| `ink-spinner@5` | D-05 spinner | ✓ | 설치됨 | Phase 1 스텁(SPIN 배열) 유지 |
| `ink-select-input@6.2` | INPT-06 SlashPopup | ✓ | 6.2.0 | 자체 Select 구현 |
| `@inkjs/ui@2` | ConfirmDialog 보조 | ✓ | 2.0.0 | 자체 ConfirmInput |
| `cli-highlight@2` | RND-06 | ✓ | 2.1.11 | 원본 코드 그대로 표시 |
| `diff@9` | RND-07 | ✓ | 9.0.0 | placeholder 텍스트 |
| `~/.harness/history.txt` | INPT-03 | 선택적 | — | 파일 없으면 빈 history |
| `node:fs`, `node:os`, `node:path` | INPT-03 | ✓ | bun 내장 | — |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | vitest@4.1.5 + ink-testing-library@4.0.0 |
| Config file | `ui-ink/vitest.config.ts` (존재 확인 필요) |
| Quick run command | `cd ui-ink && bun run test` |
| Full suite command | `cd ui-ink && bun run test --reporter=verbose` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RND-01 | agent_end 후 completedMessages에 이동 | unit | `vitest run store.test.ts` | ✅ (업데이트 필요) |
| RND-02 | spinner가 completedMessages에 없음 | unit | `vitest run store.test.ts` | ✅ (추가 필요) |
| RND-03 | useShallow selector 적용 확인 | unit | `vitest run store.test.ts` | ❌ Wave 1 |
| RND-05 | 500 토큰 후 completedMessages에 streaming:true 없음 | unit | `vitest run store.test.ts` | ❌ Wave 3 |
| CNF-01 | confirm_write 다이얼로그 렌더 | component | `vitest run components` | ❌ Wave 2 |
| CNF-02 | confirm_bash 위험도 라벨 표시 | component | `vitest run components` | ❌ Wave 2 |
| CNF-03 | sticky-deny: 동일 경로 두 번째 자동 거부 | unit | `vitest run confirm.test.ts` | ❌ Wave 2 |
| CNF-04 | activeIsSelf=false 시 read-only | component | `vitest run components` | ❌ Wave 2 |
| STAT-01 | 세그먼트 렌더 확인 | component | `vitest run components` | ❌ Wave 1 |
| STAT-02 | 40col에서 세그먼트 drop | component | `vitest run components` | ❌ Wave 1 |
| INPT-02 | Enter=제출, Shift+Enter=개행 | component | `vitest run multiline.test.ts` | ❌ Wave 2 |
| INPT-05 | paste 시 submit 없음 | component | `vitest run multiline.test.ts` | ❌ Wave 2 |

### Wave 0 Gaps

- [ ] `ui-ink/vitest.config.ts` — 존재 확인 필요. 없으면 Wave 1에서 생성
- [ ] `ui-ink/src/__tests__/components.test.tsx` — ink-testing-library 기반 컴포넌트 테스트
- [ ] `ui-ink/src/__tests__/multiline.test.tsx` — MultilineInput 키 시퀀스 테스트
- [ ] `ui-ink/src/__tests__/confirm.test.ts` — stickyDeny 단위 테스트

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | 아니오 | WS 토큰은 Phase 1에서 처리 |
| V5 Input Validation | 예 | Slash command 입력 — `/` 프리픽스 외 특수문자 sanitize |
| V6 Cryptography | 아니오 | — |
| Terminal Injection | 예 | tool 결과 ANSI escape sanitize (`strip-ansi` 고려) |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| tool 결과에 악의적 ANSI escape 포함 | Tampering | `cli-highlight`가 입력을 파싱하므로 escape 무력화. 단 raw content 직접 표시 시 `strip-ansi` 적용 |
| slash command에 임의 텍스트 주입 | Tampering | 서버가 슬래시 명령을 파싱하므로 클라이언트는 단순 전달. 추가 sanitize 불필요 |
| confirm 다이얼로그 path XSS 등가 | — | N/A (터미널 환경) |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | bun + Ink 7 `usePaste`가 bracketed paste를 정확히 전달함 | INPT-05, Q1 | Wave 2에서 paste 스모크 실패. stdin 레벨 수동 파싱 fallback 필요 |
| A2 | macOS IME 조합 중 Enter가 Wave 2 기본 구현에서 문제없음 | Q2, INPT-02 | 한국어 IME submit 오발사. composition guard 추가 필요 |
| A3 | `@inkjs/ui@2`의 `ConfirmInput`이 ink@7에서 정상 동작 | CNF-01 | 자체 ConfirmInput 구현으로 교체 (50 LOC 수준) |
| A4 | `ink-select-input@6.2`에서 Tab key가 예상대로 동작함 | INPT-06, D-10 | 자체 Select 컴포넌트 구현 필요 |
| A5 | shell.py의 `classify_command` 로직을 클라이언트에서 재구현해도 충분 | CNF-02 | 서버 판정과 불일치. 보수적으로 판정하면 UX만 보수적, 보안 위험 없음 |

---

## Open Questions

1. **`@inkjs/ui ConfirmInput` vs 자체 구현**
   - Phase 1에서 설치는 됐으나 실제 `ConfirmInput` 사용 검증 안 됨
   - Recommendation: Wave 2 시작 시 5분 스모크. 동작 안 하면 자체 구현으로 즉시 전환

2. **vitest.config.ts 존재 여부**
   - 파일 목록 확인 안 됨
   - Recommendation: Wave 1 시작 시 `ls ui-ink/` 확인

3. **`completedMessages` 분리 시 `/clear` · `/undo` 처리**
   - `clearMessages()`가 `completedMessages`와 `activeMessage` 모두 비워야 하며, `<Static>`은 `key` prop 변경으로 remount 필요
   - Recommendation: Wave 1에서 `clearMessages` 로직과 Static key 패턴 동시 구현

---

## Sources

### Primary (HIGH confidence)
- `/Users/johyeonchang/harness/ui-ink/src/` — Phase 1 실제 구현 코드 (App.tsx, store/, ws/, protocol.ts)
- `/Users/johyeonchang/harness/harness_server.py` lines 205-219, 691-705 — `confirm_bash` / `confirm_write` 이벤트 서버 구현
- `/Users/johyeonchang/harness/tools/shell.py` — `classify_command` 로직 (danger_level 미전송 확인)
- `.planning/phases/02-core-ux/02-CONTEXT.md` — Phase 2 결정 사항
- `.planning/research/PITFALLS.md` — 20개 pitfall 상세 분석
- `.planning/research/ARCHITECTURE.md` — 컴포넌트 트리, 스트리밍 패턴
- `.planning/research/STACK.md` — 라이브러리 버전 및 호환성
- `.planning/research/FEATURES.md` — 기능 목록 및 우선순위
- `.planning/BB-2-DESIGN.md` — WS 프로토콜 ground truth

### Secondary (MEDIUM confidence)
- Ink 7 공식 README (`usePaste`, `useWindowSize`, `<Static>`, `useInput`) — vadimdemedes/ink
- jsdiff 공식 문서 (`structuredPatch`) — diff@9
- cli-highlight README — felixfbecker/cli-highlight
- ink-select-input README — vadimdemedes/ink-select-input

### Tertiary (LOW confidence — 검증 필요)
- macOS IME + Ink 7 `useInput` 조합 동작 — 실증 데이터 없음. Wave 2에서 검증
- bun + `usePaste` bracketed paste 호환성 — 공식 호환 매트릭스 없음

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Phase 1 실제 설치 확인 + package.json 직접 확인
- Architecture: HIGH — ARCHITECTURE.md + 실제 코드 교차 검증
- Pitfalls: HIGH — PITFALLS.md 20개 항목 + Python 동형 버그 이력
- IME/usePaste 동작: LOW → ASSUMED → Wave 2 검증 필요

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (30일 — 라이브러리 버전 변동 없으면 유효)
