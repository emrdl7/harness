# UI 렌더링 고도화 플랜

> 작성일: 2026-04-26  
> 상태: 진행 중 (Feature C 완료)

---

## 완료된 작업 (2026-04-26)

### ✅ 스트리밍 코드블록 높이 점프 수정
- `splitByCodeFence(content, streaming)` — 열린 펜스만 있어도 즉시 CodeBlock 렌더
- `CodeBlock(streaming?)` — 스트리밍 중 하이라이팅 비활성화, 높이 일정 유지
- 파일: `ui-ink/src/components/Message.tsx`

### ✅ 긴 코드 30줄 캡
- 스트리밍 중 30줄 초과 시 `… +N줄` 표시 후 마지막 30줄만 렌더
- Gemini CLI는 `availableTerminalHeight - 2` 동적 계산 (추후 개선 가능)
- 파일: `ui-ink/src/components/Message.tsx` (`MAX_STREAMING_LINES = 30`)

### ✅ Feature C: ToolIndicator (툴 실행 중 인디케이터)
- `busy` 상태이면 인풋 영역 바로 위에 스피너 표시
- 툴 실행 중: `⠋ write_file  src/index.html`
- 순수 LLM 스트리밍: `⠋ 생성 중…`
- StatusBar 스피너 제거 → `● connected` 색상으로 busy 표현 (yellow)
- 신규 파일: `ui-ink/src/components/ToolIndicator.tsx`
- 변경 파일: `store/status.ts`, `ws/dispatch.ts`, `App.tsx`, `StatusBar.tsx`

---

## Feature A: 파일 변경 Diff 표시 ⬜

### A1 — `tools/fs.py`
`write_file`, `edit_file`, `delete_file` 반환 dict에 diff 관련 필드 추가:

```python
# edit_file / write_file (기존 파일)
import difflib
file_diff = ''.join(difflib.unified_diff(
    old_content.splitlines(keepends=True),
    new_content.splitlines(keepends=True),
    fromfile=path, tofile=path, n=3
))
return {'ok': True, 'file_diff': file_diff}

# write_file (신규 파일)
return {'ok': True, 'is_new_file': True, 'new_content': content}

# delete_file (있으면)
return {'ok': True, 'is_deleted': True, 'old_content': old}
```

### A2 — `harness_server.py`
`tool_end` broadcast에 필드 추가:
```python
file_diff   = result_dict.get('file_diff')
is_new_file = result_dict.get('is_new_file')
new_content = result_dict.get('new_content')
is_deleted  = result_dict.get('is_deleted')
old_content = result_dict.get('old_content')

broadcast(room, type='tool_end', name=name, result=result_str,
          file_diff=file_diff, is_new_file=is_new_file,
          new_content=new_content, is_deleted=is_deleted,
          old_content=old_content)
```

### A3 — `protocol.ts`
```typescript
export interface ToolEndMsg {
  type: 'tool_end'
  name: string
  result: string
  file_diff?: string
  is_new_file?: boolean
  new_content?: string
  is_deleted?: boolean
  old_content?: string
}
```

### A4 — `messages.ts`
`Message` 인터페이스에 추가:
```typescript
fileDiff?: string
isNewFile?: boolean
newContent?: string
isDeleted?: boolean
oldContent?: string
```
`appendToolEnd(name, result, meta?)` 시그니처로 확장

### A5 — `dispatch.ts`
```typescript
case 'tool_end':
  messages.appendToolEnd(msg.name, msg.result, {
    fileDiff: msg.file_diff,
    isNewFile: msg.is_new_file,
    newContent: msg.new_content,
    isDeleted: msg.is_deleted,
    oldContent: msg.old_content,
  })
  status.setActiveTool(null)
```

### A6 — `Message.tsx` tool role 렌더
- `fileDiff` 있으면 기존 `DiffBlock` 재사용 (unified diff 형식)
- `isNewFile` → 전체 내용 초록색 렌더 (기존 `DiffPreview` 신규파일 분기 재사용)
- `isDeleted` → 전체 내용 빨간색 렌더

예시 출력:
```
⚙ [edit_file] index.html

╭─ diff ─────────────────────
  44  │   <header>
- 45  │     <h1>사이트 제목</h1>
  46  │   </header>
╰─────────────────────────────
```

---

## Feature I: 인풋 영역 너비 안정화 ⬜

### 문제
`useStdout()`의 `stdout.columns`은 터미널 리사이즈 시 즉시 갱신됨.
`<Box width={columns}>` → Yoga가 레이아웃을 다시 계산 → 버퍼 텍스트가 새 너비를 초과하면 줄바꿈 → 배경색(`#222222`)이 두 줄 이상을 채움.

### Gemini CLI 비교
Gemini CLI도 `useStdout()` + `width={stdout.columns}` 동적 방식을 그대로 사용.
StatusBar는 priority 기반 세그먼트 드롭으로 overflow를 방지하지만, InputArea 자체의 리사이즈 고정 로직은 별도로 두지 않음. 즉 **표준 해법이 없고, 프로젝트마다 직접 처리**.

### 선택지 비교

| 방식 | 동작 | 장점 | 단점 |
|------|------|------|------|
| A. `useRef` freeze (초기 너비 고정) | 첫 렌더 시 `columns` 캡처, 이후 변경 무시 | 가장 단순, 재레이아웃 없음 | 터미널 확장 시 인풋이 늘어나지 않음 |
| B. `Math.max(columns, initialColumns)` | 초기 이하로는 줄어들지 않음, 늘어나면 추종 | 커짐에 적응 | 터미널이 초기보다 좁아지면 Ink가 초기 너비로 그리려다 물리 터미널에서 wrap 발생 가능 |
| C. 동적 유지 + 텍스트 clamp | 너비는 현재 columns 추종, MultilineInput 렌더 텍스트를 너비로 truncate/스크롤 | 항상 정확한 Box 크기 | MultilineInput 내 수평 스크롤 구현 필요 — 공수 큼 |

### 결정: **방식 C (동적 유지 + 텍스트 clamp)** 채택 ✅ 구현 완료
- A(useRef freeze) 시도했으나 Box가 물리 터미널보다 넓어져 오른쪽에 유령 박스 생성 → 역효과
- **Box 너비는 `stdout.columns` 동적 유지**, 대신 MultilineInput 내 텍스트 렌더를 가용 폭에 clamp

### I1 — `MultilineInput.tsx` 수정
- `columns?: number` prop 추가
- 비-커서 라인: `wrap='truncate'` 적용 → 긴 텍스트가 줄바꿈 없이 잘림
- 커서 라인: viewport sliding (`viewStart = max(0, cursor.col - (textWidth - 1))`) 으로 커서가 항상 보이도록 하고, `after`는 `wrap='truncate'`이 처리
- `textWidth = max(4, columns - 6)` — paddingX(4) + prefix(2) 제외

### I2 — `InputArea.tsx` 수정
- `<MultilineInput columns={columns} ...>` 로 현재 columns 전달

---

## Feature B: Bypass Permissions ⬜

### B1 — ConfirmDialog에 "항상" 옵션 (세션 레벨)
- `confirm.ts`에 `allowedPaths: Set<string>`, `allowedCmds: Set<string>` 추가
- `a` 키 → `addAllowed` 후 `resolve(true)`
- `setConfirm` 진입 시 `isAllowed` 체크 → 자동 허용 (dialog 안 뜸)
- 힌트 업데이트: `y 허용 · a 항상 허용 · n 거부 · d 미리보기 · Esc 취소`

### B2 — 슬래시 커맨드 `/permit`
- `/permit writes` → `profile.confirm_writes = False`
- `/permit bash`   → `profile.confirm_bash = False`
- `/permit off`    → 둘 다 `True` 복원
- 백엔드: `set_profile` WS 메시지 타입 + `harness_server.py` 핸들러

### B3 — config 파일 지원
- `~/.harness/config.json` 에 `bypass_writes: true` 설정
- 서버 시작 시 profile에 반영

---

## Feature R: AI 응답 텍스트 렌더링 확장 ⬜

### R1 — 마크다운 테이블 (우선순위 2)
- `| col | col |` → box-drawing 테이블
- `Message.tsx` 텍스트 세그먼트 파싱 단계에 테이블 감지 추가
- 구현: `TableBlock` 컴포넌트 신규

### R2 — JSON 블록 자동 감지 (우선순위 5)
- `{`/`[` 로 시작하는 멀티라인 → `JSON.parse` 시도 → pretty-print + 컬러
- key: bold, string: green, number: yellow
- 실패 시 plain text fallback

### R3 — 파일 경로 하이라이트 (우선순위 8)
- `InlineText` 내 `/path/to/file:42` 패턴 감지
- cyan + 밑줄

### R4 — 스택 트레이스 렌더 (우선순위 9)
- Python Traceback / JS call stack 자동 감지
- 파일명 cyan, 줄번호 yellow, 에러 메시지 red bold

### R5 — 숫자/단위 강조 (우선순위 11)
- `245ms`, `1.2 MB`, `98.5%` 등 자동 포맷
- 단위별 색상

---

## Feature T: 도구 결과 전용 렌더 ⬜

**핵심 아이디어**: `tool_end.name` 기반으로 렌더 컴포넌트 분기

백엔드: `tool_end`에 `result_structured` 필드 추가 (기존 `result` string 유지)
```python
broadcast(room, type='tool_end', name=name,
          result=result_str,
          result_structured=result_dict if isinstance(result, dict) else None)
```

프론트엔드 라우팅:
```typescript
const TOOL_RENDERERS = {
  run_command:  ShellResultBlock,
  run_python:   ShellResultBlock,
  grep_search:  GrepResultBlock,
  list_files:   FileTreeBlock,
  read_file:    FileContentBlock,
  git_log:      GitLogBlock,
  git_diff:     DiffBlock,       // 이미 있음
  search_web:   WebResultBlock,
  fetch_page:   WebPageBlock,
}
```

### T1 — ShellResultBlock (우선순위 1) ★★★★★
현재 `run_command` 반환: `{ok, stdout, stderr, returncode}`

```
╭─ $ npm install ──── ✓ 0 ────╮
│ added 127 packages            │  stdout (white)
├───────────────────────────────┤
│ ⚠ npm warn deprecated...     │  stderr (yellow)
╰───────────────────────────────╯
```
- stdout/stderr 분리
- 종료코드 배지: `✓ 0` (green) / `✗ 1` (red)
- 30줄 cap + 접기 토글 (e 키)

### T2 — GrepResultBlock (우선순위 3) ★★★★
```
검색: "useState"  —  3개 파일, 7개 결과

src/App.tsx:12      import { useState } from 'react'
src/hooks/use.ts:3  const [val, setVal] = useState(0)
```
- 파일명:줄번호 cyan
- 매칭 부분 bold

### T3 — FileTreeBlock (우선순위 6) ★★★
```
harness/
├── ui-ink/
│   ├── src/
│   └── package.json
└── tools/
```

### T4 — FileContentBlock (우선순위 4) ★★★★
- 파일 확장자 → 언어 자동 감지 → `cli-highlight`
- `read_file` 결과에 하이라이팅 적용

### T5 — GitLogBlock (우선순위 7) ★★★
```
● abc1234  feat: 한글 IME 커서 수정
  johyeon  2026-04-26  main
```

### T6 — WebResultBlock (우선순위 10) ★★
```
┌─ 검색: "Ink streaming" ──────────┐
│ 1. React Ink Guide                │
│    ink.js.org · description...    │
└───────────────────────────────────┘
```

---

## 구현 우선순위 요약

| 순서 | Feature | 임팩트 | 난이도 |
|------|---------|--------|--------|
| 0 | **I1 인풋 너비 고정** | ★★★★ | **매우 낮음** |
| 1 | T1 ShellResultBlock | ★★★★★ | 낮음 |
| 2 | R1 마크다운 테이블 | ★★★★ | 중간 |
| 3 | T2 GrepResultBlock | ★★★★ | 낮음 |
| 4 | T4 FileContentBlock | ★★★★ | 낮음 |
| 5 | A (파일 diff) | ★★★★ | 중간 |
| 6 | B1 항상 허용 | ★★★ | 낮음 |
| 7 | R2 JSON 자동감지 | ★★★ | 중간 |
| 8 | T3 FileTreeBlock | ★★★ | 중간 |
| 9 | T5 GitLogBlock | ★★★ | 낮음 |
| 10 | R3 경로 하이라이트 | ★★★ | 낮음 |
| 11 | R4 스택트레이스 | ★★★ | 중간 |
| 12 | B2 /permit 슬래시 | ★★ | 중간 |
| 13 | T6 WebResultBlock | ★★ | 높음 |
| 14 | R5 숫자 강조 | ★★ | 낮음 |

---

## 관련 파일 참조

| 파일 | 역할 |
|------|------|
| `ui-ink/src/components/Message.tsx` | 메시지 렌더 (코드블록, 인라인 마크다운) |
| `ui-ink/src/components/DiffPreview.tsx` | diff/신규파일 미리보기 (ConfirmDialog용, A에서 재사용) |
| `ui-ink/src/components/ToolIndicator.tsx` | 툴 실행 인디케이터 (완료) |
| `ui-ink/src/store/messages.ts` | 메시지 슬라이스 |
| `ui-ink/src/store/status.ts` | busy/activeTool 상태 |
| `ui-ink/src/ws/dispatch.ts` | WS 이벤트 → store 디스패치 |
| `ui-ink/src/protocol.ts` | WS 타입 정의 |
| `tools/fs.py` | write_file, edit_file, read_file, list_files |
| `tools/shell.py` | run_command, run_python |
| `tools/git.py` | git_log, git_diff, git_status |
| `harness_server.py` | tool_end broadcast |

---

# V2 — Advanced Architecture (2026-04-27 추가)

> 출처: `NeuZhou/awesome-ai-anatomy` 의 15개 코딩 에이전트 해부 (Pi Mono, Claude Code, Codex CLI, Cline, Goose, OpenHands 등)
>
> V1(T1~T6, R1~R5, A, B)은 "렌더 결과를 예쁘게". V2는 "렌더 아키텍처 자체를 격상".
>
> **이유**: V1 의 `TOOL_RENDERERS` dict 방식으로 6개 만들고 7번째 툴 추가하면 또 dict 손봐야 함. V2 AR-01(tool-owned registry) 위에 V1 의 T1-T6 을 얹으면 영구히 자체 확장됨.

---

## 외부 패턴 도입 매핑

| 도입할 패턴 | 출처 | 우리 ID |
|---|---|---|
| 툴 정의에 `renderResult()` co-locate | Pi Mono | AR-01 |
| Streaming frame-rate limiter (60fps coalesce) | Codex CLI | AR-02 |
| Normalized message store + 격리 렌더 | (best practice) | AR-03 |
| Two-lane input queue (steer/followUp) | Pi Mono (game-engine 패턴) | AR-04 |
| `@` 퍼지 파일 픽커 | Codex CLI (nucleo) | IX-01 |
| 슬래시 명령 인자 인텔리센스 | Claude Code | IX-02 |
| 메시지 인라인 액션 (j/k/c/r/f) | (신규 발상) | IX-03 |
| 병렬 툴 큐 카드 (read 동시 실행) | Claude Code (reader-writer lock) | IX-04 |
| Context overflow auto-compact | Pi Mono | RX-01 |
| JSONL 세션 트리 + 분기 | Pi Mono | RX-02 |
| Plan/Verify 분리 패널 | Codex CLI | RX-03 |
| 30+ event hook 확장 시스템 | Pi Mono | EX-01 |
| `protocol.ts → PROTOCOL.md` 자동 sync | (drift 방지) | EX-02 |

---

## Tier 1 — 기반 아키텍처 ★★★★★ (다른 모든 것의 전제)

### AR-01 — Tool-owned rendering registry

**문제**: V1 의 `TOOL_RENDERERS` dict 는 새 툴 추가 시 두 군데(백엔드 툴 + 프론트 dict) 수정 필요.

**해법**: 각 툴이 자기 컴포넌트를 export. 프론트엔드는 `tool_end.name → registry[name]` 으로 자동 라우팅. 모르는 툴은 fallback `<DefaultToolBlock>`.

**파일 구조**:
```
ui-ink/src/components/tools/
├── index.ts                  # registry: { run_command: ShellResultBlock, ... }
├── DefaultToolBlock.tsx      # 모르는 툴 fallback (현재 plain string 동작)
├── ShellResultBlock.tsx      # run_command, run_python
├── GrepResultBlock.tsx       # grep_search
├── FileReadBlock.tsx         # read_file
├── FileTreeBlock.tsx         # list_files
├── FileEditBlock.tsx         # edit_file, write_file (diff 포함)
├── FileDeleteBlock.tsx       # delete_file
├── GitLogBlock.tsx           # git_log
└── DiffBlock.tsx             # git_diff (이미 있음, 이전)
```

**Message.tsx 변경**:
```tsx
import { TOOL_REGISTRY, DefaultToolBlock } from './tools'

// tool role 분기
const Renderer = TOOL_REGISTRY[msg.toolName] ?? DefaultToolBlock
return <Renderer name={msg.toolName} payload={msg.toolPayload} />
```

**백엔드 (선택, AR-01 단계에선 보류)**: 추후 `tool_end` broadcast 에 `result_structured` 필드 추가 가능 — 일단은 기존 `result` string + 새로운 `result_dict` 만 추가.

### AR-02 — Streaming frame-rate limiter

**문제**: 현재 stream chunk 매번 `appendStream()` → Zustand setState → 모든 구독자 리렌더 → Ink 재조정. 한글/긴 코드에서 깜빡거림 의심.

**해법**: store layer 에 `requestAnimationFrame` 같은 16ms coalescer.

```ts
// ui-ink/src/store/messages.ts
let pendingChunks: string[] = []
let flushTimer: ReturnType<typeof setTimeout> | null = null

const FLUSH_INTERVAL = 16  // 60fps

export function appendStream(messageId: string, chunk: string) {
  pendingChunks.push(chunk)
  if (flushTimer) return
  flushTimer = setTimeout(() => {
    const merged = pendingChunks.join('')
    pendingChunks = []
    flushTimer = null
    set(state => {
      const m = state.byId[messageId]
      if (m) m.content += merged
    })
  }, FLUSH_INTERVAL)
}
```

**측정**: 도입 전후 chunk 1000개 시뮬레이션 → setState 호출 횟수 비교.

### AR-03 — Normalized message store + 격리 렌더

**조사 후 발견 (2026-04-27)**: 기존 store 가 이미 `completedMessages: Message[]` + `activeMessage: Message | null` 로 분리되어 있고, `MessageList.tsx` 가 `<Static items={completed}>` 로 완료 메시지를 격리 — Ink Static 은 추가만 렌더, 기존은 다시 그리지 않음. 즉 **격리의 핵심은 이미 구현되어 있음**. 진짜 비용은 active 메시지의 매 token flush 마다 `splitByCodeFence`/`InlineText` 재실행.

### AR-03a — React.memo + segments useMemo ✅ 완료 (2026-04-27)
- `Message.tsx`: `MessageBase` → `React.memo(MessageBase)` 로 wrap
- `splitByCodeFence` 결과를 `useMemo([content, streaming])` 로 캐싱
- 회귀 0 (vitest 161/165, 실패 4건 무관)

### AR-03b — byId/allIds 정규화 ⏸ 후속 (RX-02 와 통합)
**근거**: 단순 streaming 격리에는 byId 가 marginal. 진짜 가치는 RX-02 (JSONL session tree branching) 의 "과거 메시지 jump + 분기 lookup" 에서 발휘. 두 task 동시 진행이 자연스러움.

**원래 설계 (RX-02 와 함께 진행 시 참고)**: `byId + allIds` 정규화 + `useShallow` 로 streaming 중인 ID 만 구독.

```ts
// store/messages.ts
type State = {
  byId: Record<string, Message>
  allIds: string[]
  streamingId: string | null
}

// MessageList.tsx
const ids = useMessages(s => s.allIds)  // shallow array compare
return ids.map(id => <MessageItem key={id} id={id} />)

// MessageItem.tsx — 자기 ID 만 구독
const msg = useMessages(s => s.byId[id])
```

streaming 중인 메시지만 매 16ms 리렌더, 나머지는 reference equality 로 skip.

### AR-04 — Two-lane input queue (steer / followUp)

**문제**: 현재 `busy=true` 일 때 인풋 disabled. Pi Mono 패턴: 사용자가 LLM 답변 도중에도 타이핑 → 큐잉.

**해법**:
- `steer` (Enter): 현 LLM 턴 끝나면 다음 턴 입력으로 인젝션
- `followUp` (Shift+Enter): 전체 멈춘 뒤 입력
- 인풋 위 mini-indicator: `▸ 1 queued (steer)`

**store**:
```ts
type Queue = { kind: 'steer' | 'followUp'; text: string }
queuedInputs: Queue[]
enqueueInput(text, kind)
flushQueue()  // 턴 종료 hook 에서 호출
```

---

## Tier 2 — 신규 인터랙션 ★★★★

### IX-01 — `@` 퍼지 파일 픽커

`@src/comp` 입력 시 modal overlay (ConfirmDialog 레이어 재사용). `fuse.js` 매칭. 선택 → prompt 에 절대경로 인라인.

### IX-02 — 슬래시 명령 인자 인텔리센스

`/permit ` 까지 입력 → SlashPopup 확장: dropdown 으로 `writes/bash/off` 후보. 인자 정의는 `/cmd` 등록 시 schema 로.

### IX-03 — 메시지 인라인 액션

활성 메시지 좌측 마커 (`▎`) + 키바인딩:
- `j/k` 메시지 네비
- `c` code block copy (clipboard)
- `r` `run_command` 결과 재실행
- `f` 메시지 fold/unfold

### IX-04 — 병렬 툴 큐 카드

현재 `<ToolIndicator>` (단일) → `<ToolQueueIndicator>` (다중):
```
◐ read_file × 3   ◑ grep_search   ⠋ edit_file
```

백엔드는 이미 sync 처리 중일 가능성 — UI 만 다중 carousel.

---

## Tier 3 — 회복력/관찰 가능성 ★★★★

### RX-01 — Context overflow auto-compact

`agent.py` 에서 토큰 한도 근접 / 401 context-overflow 감지 → 자동 요약 → retry. UI 배너:
```
↻ context compacted (12.3k → 4.1k tokens · 3 turns kept)
```

WS 신규 이벤트: `context_compacted { before, after, kept_turns }`.

### RX-02 — JSONL 세션 트리 + 분기

`~/.harness/sessions/<id>.jsonl` 한 줄 = 한 메시지/툴 결과. 사용자가 과거 메시지에 커서 두고 `b` → 그 시점부터 분기 새 세션.

### RX-03 — Plan/Verify 분리 패널

응답 내 `**Plan:**` 헤더 또는 `<plan>...</plan>` 태그 감지 → 별도 fold 패널 (인풋 위 mini-panel). 토글 키 `p`.

---

## Tier 4 — 확장성 ★★★ (장기)

### EX-01 — Extension hook 시스템

Pi Mono 30+ 훅 미니 버전. `~/.harness/extensions/*.ts` 자동 로드. 시작 5훅:
- `tool_call.before` — 입력 검열/수정
- `tool_result.after` — 결과 후처리
- `slash.register` — 커스텀 슬래시 등록
- `compact.before` — 요약 전략 교체
- `message.append` — 메시지 추가 시 가로채기

### EX-02 — `protocol.ts → PROTOCOL.md` 자동 sync

`protocol.ts` 의 인터페이스 → `docs/PROTOCOL.md` 자동 생성 스크립트. 이미 PROTOCOL.md 있음, drift 방지.

---

## V2 실행 순서 (의존성)

```
Phase α (기반):    AR-01  →  AR-02  →  AR-03      (순차)
Phase β (확장):    AR-04  ‖  IX-01  ‖  RX-01       (병렬 OK)
Phase γ (인터랙):  IX-02  ‖  IX-03  ‖  IX-04
Phase δ (장기):    RX-02 → RX-03 → EX-01 → EX-02
```

V1 의 T1-T6 / R1-R5 / A / B 는 AR-01 완료 후 자연스럽게 통합 — 각 툴 컴포넌트로 흡수.
