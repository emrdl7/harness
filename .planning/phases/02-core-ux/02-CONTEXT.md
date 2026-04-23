# Phase 2: Core UX — Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1의 동작하는 스켈레톤 위에 **로컬 단독 사용 시 Python REPL 완전 대체** 가 가능한 수준의 UX를 완성한다.

- **In scope**: MultilineInput · 히스토리 · SlashPopup · Confirm 다이얼로그 · ToolCard · StatusBar · 스트리밍 렌더(Static/active) · 코드 syntax highlight · unified diff
- **Out of scope**: 리모트 Room turn-taking (Phase 3) · 재연결 backoff (Phase 3) · PEXT-01..05 서버 확장 (Phase 3, cancel 클라이언트 stub 제외) · Legacy 삭제 (Phase 5)

</domain>

<decisions>
## Implementation Decisions

### 레이아웃 구조

- **D-01: 수직 배치 순서** — `[Static 완결 메시지] → [active streaming 슬롯] → [구분선] → [InputArea / ConfirmDialog] → [구분선] → [StatusBar]`. Claude Code와 동일한 흐름.
- **D-02: 구분선** — active slot ↔ input 사이: **있음** (`─`×터미널 폭). input ↔ status bar 사이: **있음**. Static history 내부 구분선: 없음 (빈 줄로 그룹 구분).
- **D-03: Confirm 교체 방식** — confirm 모드일 때 `<InputArea>` 대신 `<ConfirmDialog>`를 조건부 렌더링. 동일 위치에 자연스럽게 대체되며 레이아웃 선 유지. Ink z-index 없음 대응 방식.

### 스트리밍 렌더 아키텍처

- **D-04: Static/active 경계** — 완결 메시지(agent_end 수신 후)는 `<Static>`에 push. 스트리밍 중인 active 메시지는 일반 트리(active slot). 완결 전까지 `<Static>`에 포함하지 않음 (RND-01 준수).
- **D-05: spinner** — Phase 1 스텁(`spinRef` 카운터)을 `ink-spinner` 컴포넌트로 교체. active slot 앞에 표시. `<Static>` 에는 절대 push 하지 않음 (RND-02).

### 슬래시 카탈로그 소스

- **D-06: 정적 하드코딩** — `src/slash-catalog.ts` 에 13개 명령 메타를 고정. harness_core 변경 시 수동 동기화 필요하나, 자주 바뀌는 데이터가 아님. Phase 2에서 가장 단순한 구현. WS 이벤트 방식은 Phase 3 PEXT 논의 시 재검토 가능.

### Ctrl+C 취소 (INPT-09 Phase 2 범위)

- **D-07: 클라이언트 stub** — Phase 2에서 `ClientMsg` 에 `cancel` 타입 추가 + 전송만 구현. 서버가 아직 처리 불가하므로 클라이언트는 "취소 요청 중..." 시스템 메시지 표시. 서버 측 cancel 처리(PEXT-05) + 재연결 연계(WSR-04)는 Phase 3에서 완성.
- **D-08: 두 번 입력 exit** — busy 상태가 아닐 때 Ctrl+C 두 번을 2초 이내 입력 시 exit. INPT-09 원문 그대로.

### SlashPopup 세부 동작

- **D-09: 트리거 타이밍** — `/` 입력 즉시 전체 명령 목록 표시, 이후 타이핑으로 실시간 필터링. Claude Code 스타일.
- **D-10: Tab 동작** — 선택된 명령을 입력창에 채우고 팝업 닫힘. Enter로 다시 확인 후 제출 (인자 있는 명령에 유용). Tab = 보완, Enter = 제출로 분리.
- **D-11: 팝업 위치** — 입력창 바로 위에 인라인 렌더 (`flexDirection='column'`). scrollback을 위로 밀어내는 방식. Ink 포지셔닝 없이 자연스럽게 연결.

### Claude's Discretion

- **RND-04 resize clear** — `useStdout().stdout.on('resize')` 감지 후 `\x1b[2J\x1b[3J\x1b[H` 강제 clear 타이밍과 구현 방식은 Claude 판단.
- **RND-09 ctx 미터 격리** — ctx/토큰 업데이트가 전체 리렌더를 유발하지 않도록 분리하는 구체적 방법(별도 상태 슬라이스 or useRef 기반)은 Claude 판단.
- **RND-10 테마 감지** — `COLORFGBG` / `TERM_PROGRAM` 파싱 방식과 fallback 색 팔레트 선택은 Claude 판단.
- **INPT-08 Tab 자동완성 인자** — 경로/세션/room 이름 자동완성 구현 범위와 방식(로컬 파일시스템 스캔 여부 등)은 Claude 판단.
- **ToolCard 상세 펼침** — 1줄 요약 + 상세 펼침 트리거 키 및 UX는 Claude 판단.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 요구사항 및 성공 기준
- `.planning/ROADMAP.md` §Phase 2 — 6개 Success Criteria (성능·입력·슬래시·confirm·StatusBar·렌더 전부 포함)
- `.planning/REQUIREMENTS.md` §INPT-01..10, §RND-01..11, §CNF-01..05, §STAT-01..02 — Phase 2 전체 REQ-ID

### WS 프로토콜 및 서버 경계
- `.planning/BB-2-DESIGN.md` — 공유 Room · turn-taking · confirm 격리 설계 (WS 프로토콜 ground truth)
- `ui-ink/src/protocol.ts` — ServerMsg/ClientMsg discriminated union (Phase 2에서 `cancel` 타입 추가 필요)
- `ui-ink/src/ws/dispatch.ts` — slash_result/quit stub — Phase 2에서 확장 필요

### 기존 코드 패턴
- `ui-ink/src/store/` — 5슬라이스 구조 (messages/input/status/room/confirm) — Phase 2에서 confirm 슬라이스 완성
- `ui-ink/src/App.tsx` — Phase 1 최소 구현, Phase 2에서 전면 교체 대상

### 기술 리서치
- `.planning/research/PITFALLS.md` — "Looks Done But Isn't" 체크리스트, Static 오염·spinner 잔재·IME 관련 함정
- `.planning/research/STACK.md` — Ink 7 usePaste/useWindowSize, ink-select-input 사용 패턴
- `.planning/research/FEATURES.md` — MultilineInput 구현 참고 (POSIX 단축키, bracketed paste)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ui-ink/src/tty-guard.ts` — `isInteractiveTTY()` 순수 함수. Phase 2 one-shot 분기에서 재사용.
- `ui-ink/src/ws/client.ts` — `HarnessClient` 클래스 (connect/send/close/heartbeat). Phase 2에서 그대로 사용.
- `ui-ink/src/ws/parse.ts` — `parseServerMsg()` — 그대로 사용.
- `ui-ink/src/store/messages.ts` — `appendToken` in-place 패턴, `appendSystemMessage`, `appendUserMessage` 확정.
- `ui-ink/src/__tests__/` — 기존 30개 테스트 green 유지 필수. Phase 2 테스트 추가 시 동일 파일 패턴(`*.test.ts`) 사용.

### Established Patterns
- `useShallow` — 모든 Zustand 슬라이스 선택자에 의무 적용 (CLAUDE.md 금지 규칙).
- `crypto.randomUUID()` — 메시지 id, React key (index key 절대 금지).
- `assertNever` — `dispatch.ts` exhaustive switch에 이미 적용. Phase 2 추가 이벤트 케이스에도 동일 패턴.
- `patchConsole: false` — `render()` 호출에 이미 적용됨. 변경 금지.
- `process.stdout.write` / `console.log` / `<div>` / `child_process.spawn` — ESLint 금지, CI 실패.

### Integration Points
- `App.tsx` 전면 교체 — Phase 2 컴포넌트들(`<MessageList>`, `<ActiveSlot>`, `<MultilineInput>`, `<SlashPopup>`, `<ConfirmDialog>`, `<StatusBar>`)을 새 `App.tsx`에서 조립.
- `store/confirm.ts` — `ConfirmMode` 타입과 payload 저장이 이미 있음. Phase 2에서 `<ConfirmDialog>` 컴포넌트 완성.
- `dispatch.ts` `slash_result` — 현재 시스템 메시지만. Phase 2에서 cmd별 처리 확장.

</code_context>

<specifics>
## Specific Ideas

- "Claude Code 급 경험" — scrollback 오염 0, spinner 잔재 0, 한국어 IME Enter 오발사 0이 핵심 기준 (PITFALLS.md 참조).
- `~/.harness/history.txt` — Python REPL과 동일 포맷(줄 단위), 마이그레이션 없이 즉시 호환 필요 (INPT-03).
- `confirm_write` DiffPreview — Phase 2는 "placeholder" (경로 + 새 내용 미리보기). `old_content` 기반 실제 diff는 PEXT-02(Phase 3) 이후 완성. ROADMAP 성공 기준 원문: "diff 패널 (경로 + DiffPreview placeholder)".
- `tools/shell.py` classifier 결과 — `confirm_bash` 위험도 라벨(CNF-02)을 위해 서버가 `danger_level` 필드를 이미 전송하는지 `BB-2-DESIGN.md` 확인 필요.

</specifics>

<deferred>
## Deferred Ideas

- WS 이벤트 기반 slash catalog broadcast — Phase 2에서 정적 JSON으로 결정. Phase 3 PEXT 논의 시 재검토 가능.
- SlashPopup 인자 자동완성(INPT-08) — 구현 복잡도 높음. Claude 판단 범위 위임. Phase 2 exit criteria에는 포함되지 않음.
- PEXT-05 서버 cancel 처리 — Phase 3. Phase 2에서는 ClientMsg cancel 타입 추가 + 전송 stub만.

</deferred>

---

*Phase: 02-core-ux*
*Context gathered: 2026-04-24*
