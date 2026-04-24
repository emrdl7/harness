---
phase: 02-core-ux
plan: E
wave: 3
type: execute
depends_on: [B, C, D]
autonomous: false
files_modified:
  - ui-ink/src/components/Message.tsx
  - ui-ink/src/components/StatusBar.tsx
  - ui-ink/src/components/ToolCard.tsx
requirements:
  - RND-06
  - RND-09
  - RND-05
must_haves:
  truths:
    - "500 토큰 연속 스트리밍 시 CPU 50% 미만 + flicker 0 + scrollback 에 spinner 잔재 0 (Phase 2 SC-1)"
    - "MultilineInput Enter/Shift+Enter/Ctrl+J/↑↓ history/POSIX 편집/500줄 paste 전부 동작 (Phase 2 SC-2)"
    - "/ 입력 시 SlashPopup 에 13개 명령 렌더 + 필터 + 방향키 + Tab/Enter/Esc (Phase 2 SC-3)"
    - "confirm_write y/n/d · confirm_bash 위험도 라벨 · sticky-deny 로컬 거부 동작 (Phase 2 SC-4)"
    - "StatusBar path · model · mode · turn · ctx% · room[members] 전 세그먼트 + graceful drop 동작 (Phase 2 SC-5)"
    - "코드 펜스 cli-highlight · ToolCard 1줄 요약 (Phase 2 SC-6) — DiffPreview 는 경로 + 새 내용 처음 10줄 placeholder 렌더를 제공한다 (diff@9 structuredPatch 통합은 Phase 3 PEXT-02 이후)"
    - "터미널 resize 200↔40 반복 시 stale line 0 (한국어 + emoji 포함)"
    - "ctxTokens 변경이 StatusBar 의 CtxMeter 서브트리에만 리렌더를 유발 (RND-09)"
  artifacts:
    - path: "ui-ink/src/components/Message.tsx"
      provides: "cli-highlight 코드 펜스 하이라이트"
      contains: "from 'cli-highlight'"
    - path: "ui-ink/src/components/StatusBar.tsx"
      provides: "격리된 CtxMeter 서브컴포넌트"
      contains: "CtxMeter"
    - path: "ui-ink/src/components/ToolCard.tsx"
      provides: "Space/Enter 토글 상세 펼침"
      contains: "useFocus"
  key_links:
    - from: "ui-ink/src/components/Message.tsx"
      to: "cli-highlight"
      via: "highlight() 호출 (코드 펜스 파싱 후)"
      pattern: "highlight\\("
    - from: "ui-ink/src/components/StatusBar.tsx"
      to: "store ctxTokens selector"
      via: "CtxMeter 서브컴포넌트 독립 구독"
      pattern: "CtxMeter"
    - from: "ui-ink/src/components/ToolCard.tsx"
      to: "Ink useFocus"
      via: "Space/Enter 토글 상태"
      pattern: "useFocus\\(\\)"
---

<objective>
Wave 1+2 에서 구축된 컴포넌트 위에 렌더 품질 레이어를 완성하고, Phase 2 exit criteria 6개 전부를 최종 검증합니다.

Purpose: cli-highlight 통합(RND-06) · ctx meter 격리(RND-09) · 500 토큰 성능 검증(RND-05) 으로 Phase 2 를 closing 하고, Phase 3 (Remote Room + Session) 진입이 가능한 안정 상태를 확보합니다.

Output:
- Message.tsx 에 코드 펜스 cli-highlight 통합
- ToolCard.tsx Space/Enter 토글 완성
- StatusBar.tsx 내부에 CtxMeter 서브컴포넌트 격리
- Phase 2 exit criteria 6개 자동 + 수동 검증 완료
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/research/PITFALLS.md
@.planning/phases/02-core-ux/02-PLAN-B-base-components.md
@.planning/phases/02-core-ux/02-PLAN-C-multiline-input.md
@.planning/phases/02-core-ux/02-PLAN-D-confirm-toolcard.md

<interfaces>
<!-- Wave 1+2 에서 생성될 컴포넌트 계약. Plan E 는 이 계약 위에서만 동작한다. -->

From ui-ink/src/components/Message.tsx (Wave 1, Plan B):
```typescript
// Wave 1 Plan B 의 B-4 에서 생성됨. 메시지 텍스트를 Ink <Text> 로 role 별 prefix/색상으로 렌더.
// Plan E 는 이 컴포넌트 내부의 텍스트 렌더 파이프라인에 cli-highlight 를 주입한다.
export interface MessageProps {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  streaming?: boolean
}
export function Message(props: MessageProps): JSX.Element
```

From ui-ink/src/components/StatusBar.tsx (Wave 1, Plan B):
```typescript
// Wave 1 Plan B 의 B-3 에서 생성됨. path · model · mode · turn · ctx% · room[members] 렌더 + graceful drop.
// Plan E 는 ctxTokens selector 를 StatusBar 본체에서 제거하고 CtxMeter 서브컴포넌트로 이관한다.
export function StatusBar(): JSX.Element
```

From ui-ink/src/components/ToolCard.tsx (Wave 2, Plan D):
```typescript
// Wave 2 에서 stub 으로 생성됨. 1줄 요약 + Space/Enter 토글 stub.
// Plan E 는 useFocus + useState 로 토글 동작을 완성한다.
export interface ToolCardProps {
  tool: string
  summary: string
  detail?: string
}
export function ToolCard(props: ToolCardProps): JSX.Element
```

From ui-ink/src/store/*.ts (Phase 1):
```typescript
// ctxTokens 는 status slice 에 있음. selector 격리용.
export const useStatusStore: StoreApi<StatusState>
// 예: useStatusStore(useShallow((s) => ({ctxTokens: s.ctxTokens})))
```
</interfaces>

<cli_highlight_pattern>
# cli-highlight 사용 패턴 (RND-06)

```typescript
import {highlight} from 'cli-highlight'

function highlightCode(code: string, lang?: string): string {
  try {
    return highlight(code, {language: lang, ignoreIllegals: true})
  } catch {
    return code  // 언어 감지 실패 시 원본 반환
  }
}
```

코드 펜스 파싱 정규식: `/```(\w*)\n([\s\S]*?)```/g`

- cli-highlight output 은 ANSI escape 를 포함한 문자열
- Ink `<Text>` 는 ANSI pass-through 를 지원 — 그대로 `<Text>{highlighted}</Text>` 로 렌더
- `process.stdout.write` 로 흘리면 안 됨 (CLAUDE.md 절대 금지)
</cli_highlight_pattern>

<pitfalls_phase2>
# PITFALLS.md — Phase 2 관련 "Looks Done But Isn't" 체크리스트

- Pitfall A: Spinner 가 completedMessages 에 없는지 (scrollback 확인)
- Pitfall B: streaming=true 인 메시지가 completedMessages 에 없는지
- Pitfall C: Ctrl+J IME Enter 충돌
- Pitfall D: resize 이벤트 stdout.write + setState 동시 처리
- Pitfall E: useStore 전체 messages 구독 없음 (useShallow 필수)
</pitfalls_phase2>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task E-1: Message.tsx 에 cli-highlight 코드 펜스 하이라이트 통합 (RND-06)</name>
  <files>ui-ink/src/components/Message.tsx, ui-ink/src/components/Message.test.tsx</files>
  <read_first>
    - ui-ink/src/components/Message.tsx — Wave 1 Plan B 의 B-4 가 생성한 현재 구조 확인
    - ui-ink/package.json — cli-highlight 의존성 이미 존재하는지 확인 (Phase 1 에서 설치됨)
  </read_first>
  <behavior>
    - Test 1: ` ```ts\nconst x = 1\n``` ` 을 포함한 content 가 들어오면 highlight() 가 호출되고 ANSI 문자열이 포함된 Text 가 렌더된다.
    - Test 2: 언어 지정 없는 ` ```\nplain\n``` ` 펜스는 lang=undefined 로 highlight() 호출 + 실패 시 원본 반환.
    - Test 3: 잘못된 언어(` ```nonexistent_lang\n... ` )는 ignoreIllegals:true 로 throw 하지 않고 원본 반환.
    - Test 4: 코드 펜스 밖 일반 텍스트는 highlight() 가 호출되지 않는다 (spy 로 확인).
    - Test 5: 복수 펜스 블록이 있는 content 도 각 블록이 독립적으로 highlight 된다.
  </behavior>
  <action>
    Message.tsx 에 다음을 구현합니다:

    1. `import {highlight} from 'cli-highlight'` 추가.

    2. 헬퍼 함수 `highlightCode(code: string, lang?: string): string` 정의 — try/catch 로 감싸 실패 시 원본 반환, `ignoreIllegals: true` 옵션 사용.

    3. content 파싱 함수 `splitByCodeFence(content: string): Array<{type: 'text' | 'code', text: string, lang?: string}>` 정의 — 정규식 `/```(\w*)\n([\s\S]*?)```/g` 로 펜스 구간과 일반 텍스트 구간을 분리.

    4. Message 컴포넌트 렌더에서 `splitByCodeFence(props.content)` 로 분할 → 각 세그먼트를 `<Text>` 로 렌더. code 세그먼트는 `highlightCode(seg.text, seg.lang)` 결과를 Text children 으로 직접 전달 (ANSI pass-through).

    5. `<div>`/`<span>` 금지 — Ink `<Box>`/`<Text>` 만 사용. `process.stdout.write` 금지 — Ink 렌더 트리만 사용.

    6. 주석은 한국어로 — 예: `// 코드 펜스 하이라이트 — cli-highlight 의 ANSI 출력을 Ink Text 로 pass-through`.

    Message.test.tsx 에서 위 behavior 5건을 ink-testing-library `render()` 로 작성. highlight spy 는 `vi.spyOn` 또는 `vi.mock('cli-highlight')` 로 확인.
  </action>
  <verify>
    <automated>cd ui-ink && bun run test -- Message.test.tsx</automated>
  </verify>
  <done>
    - Message.test.tsx 5건 전부 green
    - Message.tsx 내 `highlight(` 호출 존재 (grep)
    - Message.tsx 에 `<div>`/`<span>`/`process.stdout.write`/`console.log` 0건 (grep)
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task E-2: ToolCard.tsx Space/Enter 토글 펼침 완성</name>
  <files>ui-ink/src/components/ToolCard.tsx, ui-ink/src/components/ToolCard.test.tsx</files>
  <read_first>
    - ui-ink/src/components/ToolCard.tsx — Wave 2 Plan D 가 생성한 stub 확인 (useFocus · useState 미완성 가능성)
    - ui-ink/src/components/ToolCard.test.tsx — 기존 테스트 확인 (D 에서 1줄 요약 테스트만 있을 가능성)
  </read_first>
  <behavior>
    - Test 1: 포커스가 있을 때 Space 키를 누르면 detail 이 렌더된다 (expanded=true).
    - Test 2: 다시 Space 를 누르면 detail 이 사라진다 (expanded=false, 토글 동작).
    - Test 3: Enter 키도 Space 와 동일한 토글 효과.
    - Test 4: 포커스가 없을 때는 Space/Enter 가 반응하지 않는다.
    - Test 5: detail prop 이 없을 때는 토글해도 빈 공간만 나타나고 크래시하지 않는다.
  </behavior>
  <action>
    ToolCard.tsx 를 다음 구조로 완성합니다:

    1. `import {useFocus, useInput, Box, Text} from 'ink'` 및 `import {useState} from 'react'` 추가.

    2. 컴포넌트 내부에서:
       ```tsx
       const {isFocused} = useFocus()
       const [expanded, setExpanded] = useState(false)
       useInput((input, key) => {
         if (!isFocused) return
         if (input === ' ' || key.return) setExpanded((v) => !v)
       })
       ```

    3. 렌더 트리:
       - 항상 1줄 요약 `<Text>{summary}</Text>` 렌더
       - `expanded && detail` 인 경우에만 하단 `<Box><Text>{detail}</Text></Box>` 추가

    4. 주석은 한국어로 — 예: `// 포커스 상태에서만 Space/Enter 로 상세 펼침 토글`.

    5. 절대 금지: `<div>`/`<span>`, index 를 React key 로 사용 금지.

    ToolCard.test.tsx 에서 behavior 5건을 ink-testing-library 로 작성. `stdin.write(' ')` · `stdin.write('\r')` 로 키 시뮬레이션.
  </action>
  <verify>
    <automated>cd ui-ink && bun run test -- ToolCard.test.tsx</automated>
  </verify>
  <done>
    - ToolCard.test.tsx 5건 전부 green
    - ToolCard.tsx 내 `useFocus()` 호출 존재 (grep)
    - ToolCard.tsx 내 `useInput(` 호출 존재 (grep)
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task E-3: StatusBar 에서 CtxMeter 서브컴포넌트 격리 (RND-09)</name>
  <files>ui-ink/src/components/StatusBar.tsx, ui-ink/src/components/StatusBar.test.tsx</files>
  <read_first>
    - ui-ink/src/components/StatusBar.tsx — Wave 1 Plan B 의 B-3 가 생성한 구조 확인. ctxTokens selector 가 본체에 있는지 확인
    - ui-ink/src/store/ 디렉토리 — ctxTokens 가 속한 slice 와 selector 패턴 확인
  </read_first>
  <behavior>
    - Test 1: ctxTokens 가 변경되어도 StatusBar 본체의 path/model/mode/turn/room 렌더 함수는 재실행되지 않는다 (render count spy).
    - Test 2: ctxTokens 가 변경되면 CtxMeter 서브컴포넌트만 재렌더된다.
    - Test 3: CtxMeter 는 store 에서 ctxTokens 만 구독 (useShallow 적용) — 다른 필드 변경 시 재렌더 안 됨.
    - Test 4: StatusBar 는 여전히 `path · model · mode · turn · ctx% · room[members]` 전 세그먼트를 렌더한다 (graceful drop Plan D 테스트와 호환).
  </behavior>
  <action>
    StatusBar.tsx 를 다음과 같이 리팩터합니다:

    1. 새 서브컴포넌트 `<CtxMeter>` 를 StatusBar.tsx 파일 내부에 정의 (별도 파일로 분리할 필요 없음):
       ```tsx
       // ctxTokens 만 격리 구독 — StatusBar 본체 리렌더 방지 (RND-09)
       function CtxMeter() {
         const {ctxTokens} = useStatusStore(useShallow((s) => ({ctxTokens: s.ctxTokens})))
         const pct = Math.round((ctxTokens / MAX_CTX) * 100)
         return <Text>ctx {pct}%</Text>
       }
       ```

    2. StatusBar 본체에서 ctxTokens selector 를 제거 — `path`, `model`, `mode`, `turn`, `room` 만 구독. 기존 ctx 세그먼트 자리에 `<CtxMeter />` 배치.

    3. `useShallow` import 확인 — Phase 1 에서 이미 사용 중.

    4. graceful drop 우선순위 (`ctx% → room → mode → turn → path`) 는 기존 로직 유지. CtxMeter 는 drop 대상 1순위 — StatusBar 가 좁은 폭에서 `<CtxMeter />` 를 조건부로 렌더 안 할 수 있음.

    5. 주석은 한국어 — `// RND-09: ctxTokens 변경 시 StatusBar 본체 리렌더 방지를 위한 격리 서브컴포넌트`.

    StatusBar.test.tsx 에 behavior 4건 추가. render count 는 `vi.fn()` 으로 컴포넌트 감싸 횟수 측정.
  </action>
  <verify>
    <automated>cd ui-ink && bun run test -- StatusBar.test.tsx</automated>
  </verify>
  <done>
    - StatusBar.test.tsx 신규 4건 + 기존 Plan D 테스트 모두 green
    - StatusBar.tsx 내 `function CtxMeter` 또는 `const CtxMeter` 존재 (grep)
    - StatusBar.tsx 내 본체 selector 에 ctxTokens 부재 (grep -v 로 확인)
  </done>
</task>

<task type="auto">
  <name>Task E-4: 전체 vitest + tsc + lint + CI 가드 통과 확인</name>
  <files>(없음 — 검증 전용)</files>
  <read_first>
    - ui-ink/package.json — script 이름 확인 (test, lint 등)
    - ui-ink/scripts/ci-no-escape.sh — Phase 1 에서 생성된 alternate screen 가드 스크립트
  </read_first>
  <action>
    Phase 2 자동 검증 게이트를 순차 실행합니다. 하나라도 실패하면 즉시 원인을 수정하고 재실행.

    1. `cd ui-ink && bun run test` — 모든 vitest 테스트 green (Plan A~E 전부 포함)
    2. `cd ui-ink && npx tsc --noEmit` — 타입 에러 0
    3. `cd ui-ink && bun run lint` — ESLint 금지 규칙 위반 0 (`process.stdout.write`, `console.log`, `<div>`, `<span>`, `child_process.spawn`)
    4. `cd ui-ink && bash scripts/ci-no-escape.sh` — alternate screen / mouse tracking 코드 0건
    5. `grep -rn "useStore()" ui-ink/src/ || true` — 전체 store 객체 구독 0건 (빈 결과)
    6. `grep -rn "process.stdout.write\|console.log" ui-ink/src/ || true` — 0건 확인
    7. `grep -rn "child_process" ui-ink/src/ || true` — 클라이언트 spawn 0건

    실패 시:
    - tsc 실패: 타입 수정. any 사용 금지 — 실제 타입 정의.
    - lint 실패: 금지 규칙 위반 제거.
    - vitest 실패: 원인 분석 후 해당 Task (A~E) 로 돌아가 수정.
    - escape 가드 실패: 해당 파일에서 escape sequence 제거.

    모든 게이트 통과 후 다음 단계로 진행.
  </action>
  <verify>
    <automated>cd ui-ink && bun run test && npx tsc --noEmit && bun run lint && bash scripts/ci-no-escape.sh</automated>
  </verify>
  <done>
    - 4개 자동 게이트 명령 모두 exit code 0
    - 3개 grep 명령 모두 빈 결과
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task E-5: Phase 2 exit criteria 6개 수동 검증</name>
  <what-built>
    Phase 2 Wave 1+2+3 전체 — MultilineInput · SlashPopup · ConfirmDialog · Message · StatusBar · ToolCard · cli-highlight · DiffPreview placeholder(diff@9 structuredPatch 는 Phase 3 PEXT-02) · CtxMeter 격리.
  </what-built>
  <how-to-verify>
    로컬 `harness_server.py` 를 구동한 뒤 `cd ui-ink && bun start` 로 ui-ink 클라이언트를 실행합니다 (환경변수: `HARNESS_URL=ws://127.0.0.1:7891`, `HARNESS_TOKEN`, `HARNESS_ROOM`).

    다음 6개 항목을 터미널에서 직접 검증하고 각 항목마다 ✓ 또는 ✗ 를 표시합니다.

    ## Phase 2 SC-1 — 스트리밍 성능 & scrollback 청결성 (RND-05)
    - [ ] 500 토큰 이상의 긴 응답을 요청 (예: "주어진 주제로 500 토큰 이상의 에세이를 써줘")
    - [ ] `top`/`htop` 으로 harness 프로세스 CPU 사용률이 스트리밍 중 **50% 미만** 유지되는지 관찰
    - [ ] 스트리밍 중 화면 flicker (깜빡임) **0회** 확인
    - [ ] 스트리밍 완료 후 scrollback (터미널 위로 스크롤) 에 spinner 프레임 잔재 **0개** 확인 (PITFALLS A)
    - [ ] 스트리밍 중 streaming=true 메시지가 Static `completedMessages` 에 들어가 있지 않은지 확인 (PITFALLS B)

    ## Phase 2 SC-1b — Resize 안정성
    - [ ] 스트리밍 도중 터미널 폭을 200 → 40 → 200 → 40 으로 3회 반복 resize
    - [ ] stale line (이전 폭의 잔재) **0개**
    - [ ] 한국어 + emoji 포함 메시지 wrap 정상 (글자 깨짐 0)
    - [ ] resize 중 console 에 `process.stdout.write` 출력 없음 (PITFALLS D)

    ## Phase 2 SC-2 — MultilineInput (INPT-01~10)
    - [ ] Enter 로 제출, Shift+Enter 로 개행 동작
    - [ ] Ctrl+J 로 개행 동작 (IME 한국어 조합 중 Enter 가 제출되지 않는지 — PITFALLS C)
    - [ ] ↑ ↓ 방향키로 `~/.harness/history.txt` 이전 입력 순회 (Python 포맷 호환 확인)
    - [ ] Ctrl+A / Ctrl+E / Ctrl+K / Ctrl+W / Ctrl+U POSIX 편집 단축키 동작
    - [ ] 500줄 텍스트를 클립보드에서 bracketed paste — 중간 submit 0회 + 전체 500줄 보존

    ## Phase 2 SC-3 — SlashPopup (INPT 슬래시)
    - [ ] `/` 입력 시 popup 열림, 13개 슬래시 명령 전부 렌더 (harness_core 메타 파생)
    - [ ] 필터: `/he` 입력 시 `help` 계열만 남음
    - [ ] 방향키 ↑↓ 네비게이션
    - [ ] Tab 으로 보완, Enter 로 선택, Esc 로 닫기

    ## Phase 2 SC-4 — ConfirmDialog (CNF-01~05)
    - [ ] `confirm_write` 요청 시 diff 패널 (경로 + DiffPreview placeholder) + y/n/d 키 동작
    - [ ] `confirm_bash` 요청 시 커맨드 프리뷰 + `tools/shell.py` 위험도 라벨 + y/n
    - [ ] `cplan_confirm` 이 동일 프레임 재사용
    - [ ] 동일 턴에서 같은 요청이 반복되면 sticky-deny 로 로컬에서 자동 거부

    ## Phase 2 SC-5 — StatusBar (STAT-01~02, RND-09)
    - [ ] `path · model · mode · turn · ctx% · room[members]` 전 세그먼트 렌더
    - [ ] 터미널 폭 축소 시 `ctx% → room → mode → turn → path` 우선순위로 graceful drop
    - [ ] ctx% 토큰 증가가 활발히 발생해도 다른 세그먼트가 flicker 없이 유지 (CtxMeter 격리 확인)

    ## Phase 2 SC-6 — 렌더 품질 (RND-06~11)
    - [ ] 응답에 코드 블록 (예: ` ```ts ... ``` `) 포함 시 cli-highlight 문법 색상 적용
    - [ ] DiffPreview placeholder (예: `confirm_write` 시 `d` 키) — 경로 + 새 내용 처음 10줄 초록색 `+` 접두사 렌더 (Phase 3 PEXT-02 이후 diff@9 structuredPatch 로 교체 예정)
    - [ ] tool 결과가 `<ToolCard>` 로 1줄 요약 (예: `read 120 lines (of 340)`)
    - [ ] ToolCard 에 포커스 후 Space 또는 Enter 로 상세 펼침 토글

    ## 종료 테스트
    - [ ] Ctrl+C 로 정상 종료 — 터미널 에코 · 라인 편집 · 커서 가시성 복구 (Phase 1 FND-16 회귀 없음)
    - [ ] `kill -9 <pid>` 후에도 터미널 복구 정상
  </how-to-verify>
  <resume-signal>
    모든 체크 완료 후 "approved" 라고 응답하거나, 실패 항목이 있으면 해당 번호와 재현 스텝을 작성해주세요.
  </resume-signal>
</task>

</tasks>

<verification>
## 최종 검증 명령

```bash
# 1. ui-ink 전체 테스트
cd ui-ink && bun run test

# 2. 타입 체크
cd ui-ink && npx tsc --noEmit

# 3. 린트
cd ui-ink && bun run lint

# 4. alternate screen / mouse tracking 가드
cd ui-ink && bash scripts/ci-no-escape.sh

# 5. 금지 패턴 grep (전부 빈 결과여야 함)
grep -rn "process.stdout.write\|console.log" ui-ink/src/
grep -rn "<div\|<span" ui-ink/src/
grep -rn "child_process" ui-ink/src/
grep -rn "useStore()" ui-ink/src/

# 6. Plan E 신규 구현 grep (전부 매치 존재해야 함)
grep -n "from 'cli-highlight'" ui-ink/src/components/Message.tsx
grep -n "CtxMeter" ui-ink/src/components/StatusBar.tsx
grep -n "useFocus()" ui-ink/src/components/ToolCard.tsx

# 7. Python pytest 회귀 없음 (199건 유지)
.venv/bin/python -m pytest
```

## Phase 2 전체 requirement coverage (실제 plan 구조 반영)

- store/protocol 계약 (RND-01..03, INPT-03, CNF-03..05) → Plan A
- 기반 컴포넌트 · App 레이아웃 (STAT-01..02, RND-04, RND-05, RND-10..11, INPT-07, INPT-09..10) → Plan B
- MultilineInput · SlashPopup · InputArea (INPT-01, 02, 04, 05, 06, 08) → Plan C
- ConfirmDialog · DiffPreview · ToolCard (CNF-01, 02, 04, 05, RND-07, RND-08) → Plan D
- cli-highlight 통합 (RND-06) · CtxMeter 격리 (RND-09) · 500 토큰 수동 성능 검증 (RND-05) · Phase 2 exit criteria 최종 검증 → Plan E

Phase 2 REQ-ID 전부 매핑 확인.
</verification>

<success_criteria>
Plan E 완료 기준:

- [ ] Task E-1 ~ E-3 의 vitest 테스트 전부 green (behavior 총 14건)
- [ ] Task E-4 자동 게이트 4개 + grep 3개 전부 통과
- [ ] Task E-5 수동 체크리스트 Phase 2 SC-1~SC-6 전부 ✓ (human approved)
- [ ] Python pytest 199건 유지 (회귀 없음)
- [ ] Message.tsx 에 cli-highlight 통합 완료
- [ ] StatusBar.tsx 에 CtxMeter 서브컴포넌트 격리 완료
- [ ] ToolCard.tsx Space/Enter 토글 완성
- [ ] Phase 2 exit criteria 6개 ROADMAP.md 기준 전부 충족

Phase 2 완료 상태. Phase 3 (Remote Room + Session Control) 진입 가능.
</success_criteria>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| WS server → ui-ink | harness_server.py 에서 수신한 content 문자열이 Message.tsx 로 흘러 cli-highlight 에 전달 — 서버 측 AI 응답에 악의적 ANSI / 제어문자가 섞일 가능성 |
| user keyboard → ToolCard | 포커스 상태에서 키 입력이 useInput 핸들러로 전달 — Space/Enter 외 키 조합이 예외를 유발할 가능성 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02E-01 | T (Tampering) | Message.tsx cli-highlight | mitigate | `ignoreIllegals: true` 로 hljs 내부 throw 차단 + try/catch 로 highlight 실패 시 원본 반환 (악성 언어 힌트로 크래시 차단) |
| T-02E-02 | D (DoS) | Message.tsx 코드 펜스 파싱 | mitigate | 정규식은 `[\s\S]*?` non-greedy — catastrophic backtracking 회피. 추가로 단일 펜스 최대 길이 제한 없음(화면 폭으로 자연 제한)이지만 500 토큰 수동 검증(E-5 SC-1)으로 성능 확인 |
| T-02E-03 | I (Info Disclosure) | cli-highlight ANSI output | accept | ANSI 색상 escape 는 Ink Text pass-through — scrollback 에 저장되지만 민감 정보 자체는 서버가 이미 보낸 content. UI 가 추가 유출 안 함 |
| T-02E-04 | D (DoS) | ToolCard useInput | mitigate | `if (!isFocused) return` 로 포커스 없을 때 이벤트 무시. Space/Enter 외 키는 토글 안 함 — 키 폭탄 방지 |
| T-02E-05 | T (Tampering) | StatusBar CtxMeter selector | accept | store 는 WS dispatch 로만 갱신 — UI 가 ctxTokens 를 임의로 조작할 경로 없음. selector 격리는 성능 격리일 뿐 보안 경계 아님 |
| T-02E-06 | R (Repudiation) | Phase 2 수동 검증 (E-5) | accept | 수동 체크리스트는 PITFALLS.md 와 ROADMAP.md 기록 + git 커밋 메시지로 감사 가능. 추가 로깅 불필요 |
</threat_model>

<output>
완료 후 `.planning/phases/02-core-ux/02-E-SUMMARY.md` 생성 — 구현 내용, 테스트 결과, Phase 2 수동 검증 체크리스트 결과, Phase 3 진입 시 주의사항 기록.
</output>
