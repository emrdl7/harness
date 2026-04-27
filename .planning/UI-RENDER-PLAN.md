# UI 렌더링 고도화 플랜

> 작성일: 2026-04-26
> 최종 갱신: 2026-04-27
> 상태: V1 전체 완료 · V2 대부분 완료 — 잔여 6항목 (AR-03b · IX-03 j/k/r/f · IX-04 · RX-02 full · RX-03 · EX-01/02)
>
> **요약**: V1 의 A/B/I/R/T 와 V2 의 AR-01/02/04, AR-03a, RX-01, IX-01/02, IX-03(step), RX-02(simple) 까지 구현 완료.
> 자세한 매핑은 본문 각 섹션의 ✅ / ⬜ 마커 참조. 실제 잔여 작업은 문서 맨 아래 "잔여 작업" 섹션 참조.

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

## Feature A: 파일 변경 Diff 표시 ✅ 완료 (06a488e + 46f0e0e fix)

`FileEditBlock.tsx` 로 흡수. write_file/edit_file 결과에 unified diff 컬러링 적용.

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

## Feature I: 인풋 영역 너비 안정화 ✅ 완료 (방식 C — 동적 유지 + 텍스트 clamp)

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

## Feature B: Bypass Permissions ✅ 완료 (61d7368 + 60ec3a4 + de2dc76)

### B1 — ConfirmDialog "항상 허용" ✅ (61d7368)
- `confirm.ts`에 `allowedPaths: Set<string>`, `allowedCmds: Set<string>` 추가
- `a` 키 → `addAllowed` 후 `resolve(true)`
- `setConfirm` 진입 시 `isAllowed` 체크 → 자동 허용 (dialog 안 뜸)
- 힌트 업데이트: `y 허용 · a 항상 허용 · n 거부 · d 미리보기 · Esc 취소`

### B2 — `/permit` 슬래시 ⬜ (미구현 — `.harness.toml` 으로 대체됨)
대신 B3 형태로 흡수: `.harness.toml` 의 `confirm` 설정을 BIND 분기 없이 항상 존중하는 방향으로 확정.

### B3 — config 파일 지원 ✅ (60ec3a4 + de2dc76)
- `.harness.toml` 의 `confirm_writes`/`confirm_bash` 설정을 서버 시작 시 profile 에 반영
- 로컬 BIND 여부와 무관하게 동일하게 동작

---

## Feature R: AI 응답 텍스트 렌더링 확장 ✅ 완료 (R1~R5 전부)

### R1 — 마크다운 테이블 ✅ (6b9a015)
- `| col | col |` → box-drawing 테이블
- `splitByTable` + `TableBlock` 컴포넌트 신규

### R2 — JSON 블록 자동 감지 ✅ (77de095)
- `{`/`[` 로 시작하는 멀티라인 → `JSON.parse` → pretty-print
- `splitByJson` + `JsonBlock` 컴포넌트

### R3 — 파일 경로 하이라이트 ✅ (ef77dd0)
- `InlineText` 내 `/path/to/file:42` 패턴 cyan + underline

### R4 — 스택 트레이스 렌더 ✅ (db91b74)
- Python Traceback / JS call stack 자동 컬러링

### R5 — 숫자/단위 강조 ✅ (64e3af9)
- `245ms`, `1.2 MB`, `98.5%` 자동 yellow 강조

---

## Feature T: 도구 결과 전용 렌더 ✅ 완료 (T1~T6 전부 — AR-01 registry 위에 통합됨)

**핵심 아이디어**: `tool_end.name` 기반으로 렌더 컴포넌트 분기. 실제 구현은 V2 AR-01 의 `components/tools/` registry 로 흡수됨.

| 계획 ID | 실제 컴포넌트 | 커밋 |
|---|---|---|
| T1 ShellResultBlock | `BashBlock.tsx` | d766957 (V2 통합) |
| T2 GrepResultBlock | `GrepResultBlock.tsx` | a3d317a |
| T3 FileTreeBlock | `ListFilesBlock.tsx` | 60cf713 |
| T4 FileContentBlock | `ReadFileBlock.tsx` | d766957 |
| T5 GitLogBlock | `GitLogBlock.tsx` | c64ebdf |
| T6 WebResultBlock | `WebSearchBlock.tsx` | 991efda |
| (A 흡수) FileEditBlock | `FileEditBlock.tsx` | 06a488e |

---

## 구현 우선순위 요약 (히스토리)

> 본 표는 작성 시점 우선순위. 모든 V1 항목 완료. 잔여 작업은 V2 미완 + 문서 하단 "잔여 작업" 참조.

| 순서 | Feature | 상태 |
|------|---------|------|
| 0 | I1 인풋 너비 고정 | ✅ |
| 1 | T1 ShellResultBlock | ✅ (BashBlock) |
| 2 | R1 마크다운 테이블 | ✅ |
| 3 | T2 GrepResultBlock | ✅ |
| 4 | T4 FileContentBlock | ✅ (ReadFileBlock) |
| 5 | A (파일 diff) | ✅ |
| 6 | B1 항상 허용 | ✅ |
| 7 | R2 JSON 자동감지 | ✅ |
| 8 | T3 FileTreeBlock | ✅ (ListFilesBlock) |
| 9 | T5 GitLogBlock | ✅ |
| 10 | R3 경로 하이라이트 | ✅ |
| 11 | R4 스택트레이스 | ✅ |
| 12 | B2 /permit 슬래시 | ⬜ (`.harness.toml` 으로 대체) |
| 13 | T6 WebResultBlock | ✅ (WebSearchBlock) |
| 14 | R5 숫자 강조 | ✅ |

---

## 관련 파일 참조

| 파일 | 역할 |
|------|------|
| `ui-ink/src/components/Message.tsx` | 메시지 렌더 (코드블록, 인라인 마크다운) |
| `ui-ink/src/components/tools/index.ts` | AR-01 tool registry — name → component |
| `ui-ink/src/components/tools/*Block.tsx` | 툴 결과 전용 렌더 컴포넌트 (T1~T6, A) |
| `ui-ink/src/components/DiffPreview.tsx` | diff/신규파일 미리보기 (ConfirmDialog용) |
| `ui-ink/src/components/ToolIndicator.tsx` | 툴 실행 인디케이터 (단일) |
| `ui-ink/src/components/QueueIndicator.tsx` | AR-04 입력 큐 인디케이터 |
| `ui-ink/src/store/messages.ts` | 메시지 슬라이스 + AR-02 coalescer |
| `ui-ink/src/store/inputQueue.ts` | AR-04 입력 큐 |
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

| 도입할 패턴 | 출처 | 우리 ID | 상태 |
|---|---|---|---|
| 툴 정의에 `renderResult()` co-locate | Pi Mono | AR-01 | ✅ d766957 |
| Streaming frame-rate limiter (60fps coalesce) | Codex CLI | AR-02 | ✅ d766957 |
| Normalized message store + 격리 렌더 | (best practice) | AR-03 | ◐ AR-03a 완료 / AR-03b 보류 |
| Two-lane input queue (steer/followUp) | Pi Mono (game-engine 패턴) | AR-04 | ✅ d766957 (+ af7e2ee fix) |
| `@` 퍼지 파일 픽커 | Codex CLI (nucleo) | IX-01 | ✅ 010d540 (+ 3b1c183 fix, 3792659 UX) |
| 슬래시 명령 인자 인텔리센스 | Claude Code | IX-02 | ◐ a354730 (hint 한 줄 — dropdown 아님) |
| 메시지 인라인 액션 (j/k/c/r/f) | (신규 발상) | IX-03 | ◐ 932f72f (Ctrl+Y 코드복사만 — j/k/r/f ⬜) |
| 병렬 툴 큐 카드 (read 동시 실행) | Claude Code (reader-writer lock) | IX-04 | ⬜ 미구현 |
| Context overflow auto-compact | Pi Mono | RX-01 | ✅ e6c43bd |
| JSONL 세션 트리 + 분기 | Pi Mono | RX-02 | ◐ af98ea8 + 6a74284 (단일 파일 누적/auto_resume — 트리 분기 ⬜) |
| Plan/Verify 분리 패널 | Codex CLI | RX-03 | ⬜ 미구현 |
| 30+ event hook 확장 시스템 | Pi Mono | EX-01 | ⬜ 미구현 |
| `protocol.ts → PROTOCOL.md` 자동 sync | (drift 방지) | EX-02 | ⬜ 미구현 |

---

## Tier 1 — 기반 아키텍처 ★★★★★ (다른 모든 것의 전제)

### AR-01 — Tool-owned rendering registry ✅ 완료 (d766957)

**문제**: V1 의 `TOOL_RENDERERS` dict 는 새 툴 추가 시 두 군데(백엔드 툴 + 프론트 dict) 수정 필요.

**해법**: 각 툴이 자기 컴포넌트를 export. 프론트엔드는 `tool_end.name → registry[name]` 으로 자동 라우팅. 모르는 툴은 fallback `<DefaultToolBlock>`.

**실제 파일 구조** (구현 완료):
```
ui-ink/src/components/tools/
├── index.ts                  # registry: name → component
├── types.ts
├── DefaultToolBlock.tsx      # 모르는 툴 fallback
├── BashBlock.tsx             # run_command (T1)
├── GrepResultBlock.tsx       # grep_search (T2)
├── ListFilesBlock.tsx        # list_files (T3)
├── ReadFileBlock.tsx         # read_file (T4)
├── FileEditBlock.tsx         # edit_file, write_file (A)
├── GitLogBlock.tsx           # git_log (T5)
└── WebSearchBlock.tsx        # search_web (T6)
```

후속 fix: 8979861 (activeToolMessage 슬롯 — in-place 업데이트 화면 반영)

### AR-02 — Streaming frame-rate limiter ✅ 완료 (d766957)

**문제**: 현재 stream chunk 매번 `appendStream()` → Zustand setState → 모든 구독자 리렌더 → Ink 재조정. 한글/긴 코드에서 깜빡거림 의심.

**해법**: store layer 에 `requestAnimationFrame` 같은 16ms coalescer. 구현은 `store/messages.ts` 안 pendingChunks + flushTimer 패턴.

### AR-03 — Normalized message store + 격리 렌더

**조사 후 발견 (2026-04-27)**: 기존 store 가 이미 `completedMessages: Message[]` + `activeMessage: Message | null` 로 분리되어 있고, `MessageList.tsx` 가 `<Static items={completed}>` 로 완료 메시지를 격리 — Ink Static 은 추가만 렌더, 기존은 다시 그리지 않음. 즉 **격리의 핵심은 이미 구현되어 있음**. 진짜 비용은 active 메시지의 매 token flush 마다 `splitByCodeFence`/`InlineText` 재실행.

### AR-03a — React.memo + segments useMemo ✅ 완료 (2026-04-27)
- `Message.tsx`: `MessageBase` → `React.memo(MessageBase)` 로 wrap
- `splitByCodeFence` 결과를 `useMemo([content, streaming])` 로 캐싱
- 회귀 0 (vitest 161/165, 실패 4건 무관)

### AR-03b — byId/allIds 정규화 ⏸ 후속 (RX-02 full 과 통합)
**근거**: 단순 streaming 격리에는 byId 가 marginal. 진짜 가치는 RX-02 full (JSONL session tree branching) 의 "과거 메시지 jump + 분기 lookup" 에서 발휘. 두 task 동시 진행이 자연스러움.

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

### AR-04 — Two-lane input queue (steer / followUp) ✅ 완료 (d766957 + af7e2ee fix)

`busy=true` 일 때 인풋 enqueue → 턴 종료 시 한 항목씩 flush. 인풋 위 `▸ N queued: "..."` 인디케이터 (`QueueIndicator.tsx`).

> **참고**: `steer` / `followUp` 분기는 단일 `steer` 모드로 단순화됨. Shift+Enter 분리는 미구현 (필요 시 후속).

---

## Tier 2 — 신규 인터랙션 ★★★★

### IX-01 — `@` 퍼지 파일 픽커 ✅ 완료 (010d540 + 3b1c183 fix, 3792659 UX)

`@src/comp` 입력 시 `FilePicker.tsx` 오버레이 — working_dir 파일 자동완성. 선택 시 buffer 의 `@token` 치환.

### IX-02 — 슬래시 명령 인자 인텔리센스 ◐ 부분 완료 (a354730)

현재: 슬래시 입력 시 인자 hint 한 줄 표시 (`/permit <writes|bash|off>` 식).
원안 dropdown 후보 picker 는 미구현 — hint 만으로 충분히 동작 중.

### IX-03 — 메시지 인라인 액션 ◐ 부분 완료 (932f72f — c 단계만)

| 키 | 기능 | 상태 |
|---|---|---|
| `Ctrl+Y` | 가장 최근 응답의 첫 코드블록 클립보드 복사 | ✅ |
| `j/k` | 메시지 네비 (커서 이동) | ⬜ |
| `r` | `run_command` 결과 재실행 | ⬜ |
| `f` | 메시지 fold/unfold | ⬜ |

좌측 마커(`▎`)도 미구현. 메시지 네비 모드 자체가 없는 상태 — 도입하려면 키 모드 + 커서 상태 + 렌더 마커 일괄 도입 필요.

### IX-04 — 병렬 툴 큐 카드 ⬜ 미구현

현재 `<ToolIndicator>` 는 단일 active tool 만. 다중 툴 carousel 형태 (`◐ read_file × 3   ◑ grep_search   ⠋ edit_file`) 는 미구현.

> **참고**: `QueueIndicator.tsx` 는 IX-04 가 아니라 AR-04 (입력 큐) 용. 별개.

---

## Tier 3 — 회복력/관찰 가능성 ★★★★

### RX-01 — Context overflow auto-compact ✅ 완료 (e6c43bd)

`agent.py` 에서 토큰 한도 근접 감지 → 자동 요약 → retry. UI 배너에 정보 풍부 표시 (단순화 옵션 적용).

추가 튜닝: 7b5df9c (CONTEXT_WINDOW 비례식 + tool 결과 캡 8K), ad8a544 (mlx 백엔드 라우팅 fix).

### RX-02 — JSONL 세션 트리 + 분기 ◐ simple 완료 (af98ea8 + 6a74284)

| 단계 | 상태 |
|---|---|
| simple: turn 종료 시 세션 자동 저장 (단일 파일 누적) | ✅ af98ea8 |
| simple: startup 시 working_dir latest 세션 자동 복원 | ✅ 6a74284 |
| full: JSONL 한 줄 = 한 메시지/툴 결과 분리 저장 | ⬜ |
| full: 과거 메시지 커서 + `b` 키 → 그 시점부터 분기 | ⬜ |
| full: 세션 트리 UI (분기 시각화) | ⬜ |

AR-03b 와 함께 진행 권장.

### RX-03 — Plan/Verify 분리 패널 ⬜ 미구현

응답 내 `**Plan:**` 헤더 또는 `<plan>...</plan>` 태그 감지 → 별도 fold 패널 (인풋 위 mini-panel). 토글 키 `p`.

---

## Tier 4 — 확장성 ★★★ (장기)

### EX-01 — Extension hook 시스템 ⬜ 미구현

Pi Mono 30+ 훅 미니 버전. `~/.harness/extensions/*.ts` 자동 로드. 시작 5훅:
- `tool_call.before` — 입력 검열/수정
- `tool_result.after` — 결과 후처리
- `slash.register` — 커스텀 슬래시 등록
- `compact.before` — 요약 전략 교체
- `message.append` — 메시지 추가 시 가로채기

### EX-02 — `protocol.ts → PROTOCOL.md` 자동 sync ⬜ 미구현

`protocol.ts` 의 인터페이스 → `docs/PROTOCOL.md` 자동 생성 스크립트. 이미 PROTOCOL.md 있음, drift 방지.

---

## V2 실행 순서 (의존성 — 원안)

```
Phase α (기반):    AR-01 ✅  →  AR-02 ✅  →  AR-03 ◐      (AR-03b 만 잔여)
Phase β (확장):    AR-04 ✅  ‖  IX-01 ✅  ‖  RX-01 ✅
Phase γ (인터랙):  IX-02 ◐  ‖  IX-03 ◐  ‖  IX-04 ⬜
Phase δ (장기):    RX-02 ◐ → RX-03 ⬜ → EX-01 ⬜ → EX-02 ⬜
```

V1 의 T1-T6 / R1-R5 / A / B 는 AR-01 위에 흡수 완료.

---

## 잔여 작업 (2026-04-27 기준)

우선순위 순.

### 1. IX-04 — 병렬 툴 큐 카드 ★★★ (낮은 난이도)
단일 `ToolIndicator` 를 다중 carousel 로 확장. 백엔드 변경 없이 UI 만 수정 가능 — `activeTool` 단일 → `activeTools[]` 배열.

### 2. IX-03 full — 메시지 인라인 액션 ★★★ (중간)
- `j/k` 메시지 네비 모드 (Esc 로 모드 진입)
- 활성 메시지 좌측 `▎` 마커
- `f` fold/unfold (긴 메시지 접기)
- `r` `run_command` 결과 재실행
- 키 모드 충돌 검토 필요 (현재 입력 활성 시 useInput 가로챔)

### 3. RX-02 full — JSONL 트리 분기 ★★★★ (큰 작업)
- 단일 파일 누적 → JSONL 분리 (한 줄 = 한 이벤트)
- 과거 메시지 커서 + `b` → 분기 새 세션
- AR-03b (byId/allIds 정규화) 와 함께 진행

### 4. AR-03b — byId/allIds 정규화 ⏸ (RX-02 full 과 묶음)
RX-02 full 의 메시지 jump/lookup 위해 필요. 단독 진행은 marginal.

### 5. RX-03 — Plan/Verify 분리 패널 ★★ (중간)
응답 안 plan 블록 감지 → 별도 mini-panel. 토글 `p`.

### 6. EX-02 — protocol.ts → PROTOCOL.md sync ★★ (낮음, 유지보수성)
TypeScript 인터페이스 → 마크다운 자동 생성 스크립트. CI 게이트로 drift 방지.

### 7. EX-01 — Extension hook 시스템 ★★★ (큰 작업, 장기)
플러그인 로더 + 5개 훅 정의. 보안 검토 필요 (사용자 코드 실행).

---

## 후속 갱신 가이드

새 commit 으로 V2 잔여 항목 구현 시 본 문서의 해당 마커 (`⬜` → `✅`) + commit hash 갱신.
"외부 패턴 도입 매핑" 표 + Tier 별 세부 + "잔여 작업" 섹션 세 곳을 동기화.
