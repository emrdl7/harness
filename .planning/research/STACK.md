# Stack Research — harness ui-ink (Node + Ink TUI)

**Domain:** Node + Ink 기반 Claude Code 급 터미널 에이전트 UI (로컬 + 원격 2인 공유, Python WS 백엔드)
**Researched:** 2026-04-23
**Confidence:** HIGH (버전은 npm registry 직접 조회, Ink/React/Zustand 는 공식 릴리스 확인)

---

## 요약 (Executive)

ui-ink 스켈레톤(commit `5d275e3`)에 선언된 `ink@5 / react@18 / zustand@4 / ink-text-input@6` 은 **2026 년 기준 구세대**입니다. 2026 년 4 월 기준 Ink 생태계 중심축은:

- **ink@7.0.1** (2026-04-17, Node 22+ · React 19.2+ 강제)
- **react@19.2.5** (2026-04-22)
- **zustand@5.0.12** (v5 메이저 전환 완료)

즉 "스켈레톤의 방향은 맞으나 버전 pin 은 전부 올려야 함" 이 한 줄 결론입니다. 그리고 `ink-text-input@6` 은 **싱글라인 전용**이라 Enter=제출 / Shift+Enter=개행 을 구현하려면 **자체 구현이 필수**(오픈소스로 검증된 대체 패키지가 없음)입니다.

WebSocket 은 `ws@8.20.0` 을 그대로 쓰되, bun 런타임의 `ws` 호환성 이슈(`node:http` 경로 일부 헤더 미스매치)가 있어 **bun 로컬 개발 + node 22 프로덕션 실행** 을 기본 구성으로 권고합니다.

외부 2 인 배포는 `git clone + bun install + bun start` 로 이번 milestone 은 충분합니다. single-file executable(`bun build --compile`) 은 기술적으로 가능하나 이번 milestone Out-of-Scope.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| **Node.js** | `>=22.0.0` | 런타임 (프로덕션 기본) | Ink 7 peer 요구 사항. 로컬 `node v22.21.1` 이미 만족. | HIGH |
| **bun** | `>=1.2.19` | 개발 런타임 · 패키지 매니저 · 스크립트 러너 | 외부 2 인 배포 전제(`bun install` 고정). TypeScript · TSX 네이티브, `.env` 자동 로드, `bun --watch` HMR. | HIGH |
| **TypeScript** | `^6.0.3` | 타입 체크 | 2026-04 에 TS 6 릴리스. React 19 타입 완전 대응. `tsc --noEmit` 만 사용(bun 이 실제 실행). | HIGH |
| **React** | `^19.2.5` | Ink 의 컴포넌트 엔진 | Ink 7 peer 강제 요구 (`>=19.2.0`). `useEffectEvent`, `useActionState` 활용 가능. | HIGH |
| **Ink** | `^7.0.1` | 터미널 React 렌더러 (Yoga flex) | Claude Code 본체와 동일 엔진. `usePaste`, `useWindowSize`, Backspace 키 수정 등 TUI 품질이 v7 에서 크게 상승. | HIGH |
| **Zustand** | `^5.0.12` | 전역 상태 (messages / input / status / busy / room / confirm queue) | 3 KB, 단일 스토어, selector 기반 re-render 최소화. Ink 처럼 라이프사이클이 긴 TUI 에 가장 간결. v5 는 React 19 공식 대응. | HIGH |
| **ws** | `^8.20.0` | WebSocket 클라이언트 | 스켈레톤 이미 선언. `harness_server.py` 와 연결 검증된 구현. Node 22 / bun 양쪽 동작. | HIGH |

### Supporting Libraries (필수 — Phase 1 구현 필수)

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| **@inkjs/ui** | `^2.0.0` | 공식 Ink 컴포넌트 키트 (Spinner · ProgressBar · Alert · Badge · ConfirmInput · StatusMessage · TextInput) | confirm_write / confirm_bash 다이얼로그의 "y/n" 은 `ConfirmInput` 그대로. 상태 표시는 `StatusMessage` / `Badge`. `TextInput` 도 포함돼 있으나 싱글라인 한계는 동일. | HIGH |
| **ink-spinner** | `^5.0.0` | 스피너 프레임 | 현재 `App.tsx` 에 직접 구현한 `SPIN` 배열은 삭제하고 이걸로 교체. | HIGH |
| **ink-select-input** | `^6.2.0` | 화살표 키 셀렉트 | 슬래시 명령 autocomplete popup · 세션 목록 선택. | HIGH |
| **ink-link** | `^5.0.0` | OSC 8 하이퍼링크 | tool 결과에 파일 경로 / 문서 URL 렌더 시 사용. 미지원 터미널에선 일반 텍스트로 자동 fallback. | MEDIUM |
| **diff** | `^9.0.0` (`jsdiff`) | diff 파싱 / 생성 | `confirm_write` 의 before/after 를 hunk 로 쪼개고, 라인 단위 색상 입힐 때. 서버가 이미 patch 텍스트를 보내면 `parseDiff` 로 파싱. | HIGH |
| **cli-highlight** | `^2.1.11` | 터미널 코드 syntax highlight | tool 결과의 코드 펜스 / `Read` 결과 렌더. `highlight.js` 기반이라 언어 커버리지 넓음. ink-syntax-highlight 의 내부도 이것. | HIGH |
| **chalk** | `^5.6.2` | ANSI 색상 | Ink 가 내부적으로 이미 사용. 직접 import 는 문자열에 색상을 미리 박고 Ink `<Text>` 에 넘길 때만 (drift 주의). | MEDIUM |

### Supporting Libraries (선택 — 필요 시 Phase 2+)

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| **ink-syntax-highlight** | `^2.0.2` | Ink 래퍼 (cli-highlight) | Ink 컴포넌트 스타일로 바로 쓸 수 있음. cli-highlight 직접 + `<Text>` 래핑이 번거로우면 채택. | MEDIUM |
| **ink-gradient** | `^4.0.0` | 그라디언트 텍스트 | 시작 배너 "harness" 로고. 없어도 무방. | LOW |
| **ink-big-text** | `^2.0.0` | figlet 폰트 | 시작 배너 대형 텍스트. 취향. | LOW |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **bun** | dev runner · install · test | `bun run --watch src/index.tsx` 가 HMR · ts 컴파일 · `.env` 로드 까지 처리. 추가 도구 불필요. |
| **tsc** | 타입 체크 | 실행은 bun, 타입만 `tsc --noEmit`. CI 에서 회귀 가드. |
| **@types/bun** | bun 런타임 타입 | `Bun.env`, `Bun.file` 등을 쓰면 필요. 이미 선언됨. |
| **@types/node** | `^25.x` | `ws` 의 내부 타입, `process.env` 타입. Node 22 ABI 와 일치. |
| **@types/react** | `^19.2.x` | Ink 7 peer. 18.x 와 섞이면 JSX 타입 충돌. |
| **@types/ws** | `^8.x` | `WebSocket` / `MessageEvent` 타입. 이미 선언됨. |
| **vitest** | `^4.1.5` | 단위 테스트 러너 | bun test 대신 vitest 를 권장 — `ink-testing-library` 공식 예제가 전부 vitest/jest 기반이고 snapshot API 가 성숙. bun test 는 스냅샷 에러가 아직 덜 친절. |
| **ink-testing-library** | `^4.0.0` | Ink 컴포넌트 렌더 + `lastFrame()` | vitest 와 결합해 "messages 추가 후 마지막 프레임 문자열이 X 를 포함" 식 assertion. |

---

## Installation (권고 최종 package.json)

```bash
cd ui-ink

# Core
bun add react@^19.2.5 ink@^7.0.1 zustand@^5.0.12 ws@^8.20.0

# Ink 생태계 — Phase 1 필수
bun add @inkjs/ui@^2.0.0 ink-spinner@^5.0.0 ink-select-input@^6.2.0 ink-link@^5.0.0

# Diff / syntax highlight
bun add diff@^9.0.0 cli-highlight@^2.1.11

# Dev
bun add -d typescript@^6.0.3 @types/bun@latest \
  @types/react@^19.2.14 @types/ws@^8.5.10 @types/node@^25.6.0 \
  vitest@^4.1.5 ink-testing-library@^4.0.0
```

**스켈레톤 → 최종 전환 시 제거:**
- 현재 선언된 `ink@^5.0.1` → `^7.0.1` 로 업그레이드 (breaking)
- `react@^18.3.1` → `^19.2.5` (peer 강제)
- `@types/react@^18.3.3` → `^19.2.14`
- `zustand@^4.5.2` → `^5.0.12` (createStore 시그니처 변경 주의)
- `ink-text-input@^6.0.0` **제거**. 자체 멀티라인 input 으로 대체(아래 "질문별 답변" 섹션 참조)

---

## 질문별 직접 답변 (quality_gate 대응)

### 1. Ink 컴패니언 패키지 — 2026 프로덕션 등급

| 패키지 | 최신 | 채택 여부 | 이유 |
|--------|------|-----------|------|
| `@inkjs/ui` | 2.0.0 (2024-05) | **채택** | Ink 공식 팀 관리. Confirm/Select/Spinner/Alert 한 번에. Ink 5+ peer 선언이라 ink@7 에서 실전 검증 필요 — Phase 1 초반에 동작 확인 task 배치. |
| `ink-spinner` | 5.0.0 (2024-05) | **채택** | 사실상 표준. `App.tsx` 의 자체 spinner 교체. |
| `ink-select-input` | 6.2.0 (2025-04) | **채택** | 슬래시 popup / 세션 선택. 활발히 유지. |
| `ink-text-input` | 6.0.0 (2024-05) | **제거** | 싱글라인 전용. 멀티라인 요구 충족 불가. |
| `ink-link` | 5.0.0 (2025-09) | **채택** | OSC 8 링크 지원 터미널(iTerm2/WezTerm/Kitty)에서 클릭 가능. |
| `ink-gradient` | 4.0.0 (2026-02) | 선택 | 배너용. 필수 아님. |
| `ink-big-text` | 2.0.0 (2023-04) | 선택 | 배너용. 2 년 정체라 주의. |
| `ink-markdown` | 1.0.4 (2023-10) | **제외** | 3 년 정체, Ink 5+ 미확인. Markdown 은 cli-highlight + 자체 간단 렌더로 충분. |
| `ink-syntax-highlight` | 2.0.2 (2025-01) | 선택 | cli-highlight 얇은 래퍼. 바로 쓰면 편함. |
| `ink-task-list` | 2.0.0 (2023-04) | **제외** | 3 년 정체. |
| `ink-table` | 3.1.0 (2023-12) | **제외** | 2 년+ 정체, Ink 7 미검증. 테이블은 `<Box>` 직접 조립. |
| `ink-form` | 2.0.1 (2024-05) | **제외** | 사용처 없음 (confirm 다이얼로그만 필요). |
| `ink-confirm-input` | 2.0.0 (2023-04) | **제외** | `@inkjs/ui` 의 `ConfirmInput` 이 공식·최신. |
| `ink-scrollbar` | 1.0.0 (2022-05) | **제외** | 4 년 정체. 스크롤은 직접 구현. |
| `ink-multi-select` | 2.0.0 (2023-04) | **제외** | 필요 없으며 정체 상태. |

### 2. 멀티라인 입력 — 현재 최선 패턴

**결론: `ink-text-input` 폐기, 자체 `<MultilineInput>` 컴포넌트 작성.**

근거:
- `ink-text-input@6` 은 명시적으로 싱글라인. `\n` 입력이 `onSubmit` 을 트리거함.
- 2026 년 현재 프로덕션급 멀티라인 Ink 입력 패키지가 **npm 에 부재**. OpenCode(sst) 는 OpenTUI 기반의 자체 textarea 를 쓰고 Claude Code 본체는 내부 구현(`~140 Ink UI 컴포넌트` 중 하나).
- Ink 7 의 `useInput` 이 Shift 키를 정확히 보고(`key.shift`) 하고, `usePaste` 가 붙여넣기 이벤트를 별도로 준다. 자체 구현이 오히려 안정적.

구현 스케치(상세는 ARCHITECTURE.md 에):
```
buffer: string[]           // 라인 배열
cursor: {row, col}
useInput((ch, key) => {
  if (key.return && !key.shift) → onSubmit(buffer.join('\n'))
  if (key.return &&  key.shift) → insert '\n' at cursor
  if (key.backspace)            → delete before cursor
  if (key.leftArrow / rightArrow / upArrow / downArrow) → 커서 이동
  else if (ch)                  → insert at cursor
})
usePaste((text) => buffer.splice(...))  // 붙여넣기 = 다중 라인
render: buffer.map(line => <Text>{line}</Text>)  // 커서는 현재 줄에 역상
```

주의: 터미널마다 `Option+Enter` / `Cmd+Enter` / `Ctrl+J` 가 다르게 들어옵니다. Shift+Enter 는 대부분의 현대 터미널(iTerm2, Ghostty, WezTerm, Kitty, Alacritty)에서 CSI u 프로토콜 활성화 시에만 정확히 구분됩니다. **fallback 으로 `Ctrl+J` 도 개행 키로 받기**를 요구사항에 포함.

### 3. WebSocket — `ws` vs native

**결론: `ws@8.20.0` 유지 (스켈레톤 그대로).**

근거:
- Node 20 은 `WebSocket` 전역이 실험적, Node 22 에서 안정화되었으나 헤더 커스터마이즈(`x-harness-token` 같은 커스텀 헤더) 가 `WebSocket` 생성자에 직접 안 들어감. `ws` 는 `new WebSocket(url, {headers: {...}})` 를 네이티브로 지원.
- bun 의 `WebSocket` 클라이언트는 `node:http` 업그레이드 경로에서 헤더 변조 이슈가 리포트됨 (bun#5951, #6686). `ws` 를 쓰면 bun 에서도 일관.
- 재연결 로직 · ping/pong · close code 핸들링이 성숙.

"something else" 후보는 사실상 없음. `isomorphic-ws`, `reconnecting-websocket` 등은 브라우저 호환이 주 목적이라 Node 전용 TUI 에서는 오버헤드.

### 4. 상태 관리 — Zustand vs Jotai vs Valtio

**결론: Zustand 유지. 단 v4 → v5 업그레이드.**

비교:

| 관점 | Zustand | Jotai | Valtio |
|------|---------|-------|--------|
| 모델 | 단일 스토어 + selector | atom 조합 (bottom-up) | proxy mutate |
| 번들 | ~3 KB | ~4 KB | ~4 KB |
| Ink 적합성 | 최고 — 전역 스토어 1 개가 TUI 의 messages/input/status 와 자연스럽게 맞음 | 과잉 — atom 수백 개 쪼개는 가치가 TUI 엔 적음 | proxy 가 Ink 재렌더 트리거 방식과 드물게 충돌 (공식 Ink 예제 없음) |
| 외부 구독 | `useStore.getState()` · `subscribe()` — **ws.ts 같은 non-React 코드에서 쉬움** | Store 꺼내 쓰기 번거로움 | getSnapshot 강제 |
| React 19 호환 | v5 공식 지원 | 2.19+ 공식 지원 | 2.3+ 공식 지원 |

harness 의 `ws.ts` 가 React 바깥에서 `useStore.getState().appendMessage(m)` 를 직접 호출합니다(이미 스켈레톤에 구현됨). 이 패턴은 Zustand 에서 **자연스럽고**, Jotai 에서는 `getDefaultStore()` 를 강제로 꺼내야 하며, Valtio 는 proxy mutation 을 React 바깥에서 하면 subscribe 대상에서 누락되는 경우가 있어 위험합니다. Zustand 유지가 정답.

**v4 → v5 브레이킹:**
- `create` 는 동일하나 middleware 의 `setState` 시그니처가 엄격해짐. 현재 스켈레톤 코드는 `(set) => ({...})` 단순 형태라 무리 없이 마이그레이션.

### 5. Syntax highlight / diff 렌더링

| 용도 | 라이브러리 | 이유 |
|------|-----------|------|
| 코드 syntax highlight | **`cli-highlight@2.1.11`** | highlight.js 기반, 언어 185 개. 터미널에서 사실상 표준. 결과물이 pre-colored 문자열이라 `<Text>{colored}</Text>` 에 바로 박음. |
| 또는 | `ink-syntax-highlight@2.0.2` | cli-highlight 얇은 래퍼. Ink 스타일로 쓰려면 편함. 둘 중 하나만 쓰면 됨. |
| diff 파싱 | **`diff@9.0.0`** (jsdiff) | `structuredPatch` / `createTwoFilesPatch` / `parsePatch`. `confirm_write` 전에 서버가 patch 를 보내면 이걸로 hunk 분해. |
| diff 렌더 | **자체 구현** (`diff` + Ink `<Box>` + ANSI 색) | `diff2html` 은 HTML 생성이라 터미널 부적합. `react-diff-view` 도 DOM. Git 스타일 unified diff 를 Ink `<Text>` 로 그리기는 50~80 LOC. |

Shiki / Prism / highlight.js 직접 사용은 과잉 — cli-highlight 가 내부적으로 highlight.js 를 쓰면서 터미널 전용 출력을 이미 처리.

**하지 말 것:** chalk 를 직접 사용해 코드 라인마다 색상 박기 — 유지보수 악화. cli-highlight 에 맡긴다.

### 6. 번들링/배포 — 이번 milestone 결정

**이번 milestone: `git clone + bun install + bun start`.**

근거 (이것이 PROJECT.md 에 명시된 제약):
- 외부 2 인 → 단순 `git pull && bun install` 로 업데이트 전달 가능.
- `bun` 이 이미 전제이므로 bun 설치는 사용자가 한 번만 하면 됨.
- 토큰 / URL / room 은 env var 로 주입 → 배포 포맷과 무관.

`bun build --compile` 평가(참고용, 채택 아님):
- 장점: 단일 실행 파일, bun 미설치 환경에서도 실행.
- 단점: OS/아키별(macOS arm64/x64, Linux arm64/x64) 크로스빌드 관리 필요. 버전 롤링 시 재배포. 현재 사용자 3 명 규모에 과잉.
- 결론: **이번 milestone Out-of-Scope**. PROJECT.md 가 이미 "바이너리 배포 · 자동 업데이트 · Homebrew 탭 — 다음 milestone 후보" 로 명시.

`oclif`, `@vercel/ncc` 도 동일 이유로 Out-of-Scope. npm global install(`npm i -g harness-ink`) 은 private repo 라 publish 불가, 고려 가치 없음.

### 7. 테스팅 — ink-testing-library vs vitest 조합

**결론: `vitest@4.1.5` + `ink-testing-library@4.0.0`.**

근거:
- `ink-testing-library` 는 테스트 러너가 아님 — `render(<App/>)` 후 `lastFrame()` 으로 문자열 추출 유틸. 러너는 별도.
- bun test 도 동작은 하나 snapshot diff 가 vitest 보다 덜 친절 (2026-04 현재). 스냅샷 기반 TUI 회귀 테스트가 주 용도라 vitest 권장.
- vitest 4 는 Vite 7 기반으로 빠르고 ESM 네이티브, React 19 JSX 자동 변환 지원.

테스트 예:
```ts
import {render} from 'ink-testing-library'
import {test, expect} from 'vitest'

test('slash popup 렌더', () => {
  const {lastFrame, stdin} = render(<App/>)
  stdin.write('/')
  expect(lastFrame()).toContain('/help')
})
```

### 8. TypeScript 설정 패턴 (ui-ink/tsconfig.json)

권고 최종 형태:

```jsonc
{
  "compilerOptions": {
    "target": "ES2023",
    "lib": ["ES2023", "DOM"],        // DOM 은 WebSocket 타입용
    "module": "ESNext",
    "moduleResolution": "bundler",   // bun · vitest 양쪽 지원
    "jsx": "react-jsx",              // React 19 automatic runtime
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noEmit": true,
    "allowImportingTsExtensions": true,  // bun 이 .ts / .tsx 직접 import 허용
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "types": ["bun-types"]
  },
  "include": ["src/**/*"]
}
```

주의:
- `moduleResolution: "bundler"` 가 bun · vitest 동시 지원의 최소 공통 분모.
- `jsx: "react-jsx"` 는 React 17+ automatic runtime. `import React` 반복 불필요(현재 `App.tsx` 가 쓰는 구형 패턴은 유지해도 동작하나 자동 runtime 사용이 권고).

### 9. bun vs node — Ink 프로덕션에서 알려진 비호환

**결론: 로컬 개발은 bun, 외부 사용자 실행도 bun(package.json scripts 기준), 단 Node 22 fallback 가능하게 유지.**

확인된 이슈 (2026-04):
- bun 은 Ink 컴포넌트 렌더 자체는 정상 동작 (top 1000 npm 98% 호환, React/Ink 포함).
- `ws` + bun: `ws.WebSocket` 의 `upgrade` / `unexpected-response` 이벤트가 bun 에서 미구현 (bun#5951). harness 는 이 이벤트를 **현재 사용 안 함** 이지만, 혹시 재연결 로직에서 사용 시 주의.
- bun 의 `node:http` 헤더 변조가 외부 WS 핸드셰이크와 드물게 충돌. `ws` 라이브러리를 쓰면 회피됨.
- native C++ addon 을 쓰는 Ink 생태계 패키지는 현재 추천 목록에 없음 → 추가 리스크 없음.

**가드레일:**
- `bun run src/index.tsx` 가 기본.
- 회귀 테스트는 vitest 가 Node 에서 돌게 유지 (bun test 회피). 양쪽 런타임에서 최소 스모크 테스트.

### 10. Watch / Dev 체험

**결론: `bun run --watch src/index.tsx` (이미 스켈레톤 `scripts.dev` 에 설정됨). 추가 도구 불필요.**

비교:
- **bun --watch**: 파일 변경 시 프로세스 재시작. Ink 는 어차피 스테이트풀 HMR 과 궁합 좋지 않아(터미널 루프가 깨짐) 재시작이 현실적.
- **tsx watch**: Node 에서 TS 직접 실행 + watch. bun 이 이미 있는 환경에서는 중복.
- **vite**: Ink 용 Vite dev server 는 존재 의미 없음. Vite 는 브라우저 번들러.

권고: `bun run --watch` 유지. Ink HMR(`react-refresh`) 은 TUI 특성상 화면 클리어/리마운트 동기화가 복잡하므로 시도 가치 낮음.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Zustand 5 | Jotai 2.19 | atom-level 세밀 구독이 반드시 필요할 때(ex: 매우 큰 message list 의 메시지별 독립 재렌더). 현재 규모엔 과잉. |
| Zustand 5 | Valtio 2.3 | 팀이 Vue/MobX 출신이라 mutable API 선호할 때. Ink 재렌더 신뢰성은 Zustand 가 더 보수적. |
| 자체 `<MultilineInput>` | `ink-mde` (CodeMirror 기반) | WYSIWYG Markdown 편집 수준이 필요할 때. harness 의 프롬프트 입력엔 과잉 (0.34.0, 유지보수 느림). |
| `ws@8` | Node 내장 `WebSocket` (undici) | 커스텀 헤더 불필요 + Node 22+ 만 타겟일 때. harness 는 `x-harness-token` 커스텀 헤더 사용하므로 불가. |
| bun 런타임 | pnpm + Node 22 | 외부 사용자가 bun 설치를 극히 꺼릴 때. 현재 PROJECT.md 가 bun 고정이므로 N/A. |
| cli-highlight | Shiki 4 | VSCode 급 퀄리티 highlight 원할 때. 의존성 수십 MB, TUI 에 과잉. |
| vitest 4 | bun test | 테스트 코드가 매우 가볍고 스냅샷 없을 때. 현재는 회귀 가드가 중요해 vitest 가 안정. |
| `git clone + bun install` | `bun build --compile` 단일 바이너리 | 사용자가 3 명 → 50+ 로 증가할 때. 이번 milestone Out-of-Scope. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `ink-text-input@6` | 싱글라인 전용. Shift+Enter=개행 요구 불가. | 자체 `<MultilineInput>` 컴포넌트. |
| `ink@5.x` | Ink 7 대비 `usePaste`/`useWindowSize` 없음, Backspace/Escape 키 시맨틱 버그. | `ink@7.0.1` + React 19.2+. |
| `react@18.x` | Ink 7 peer `>=19.2.0` 강제. 18 로는 ink@7 설치 거부. | `react@^19.2.5`. |
| `zustand@4.x` | React 19 와 동작은 하나 v5 가 공식 지원. 타입 경미한 드리프트. | `zustand@^5.0.12`. |
| `ink-markdown@1.0.4` | 2023-10 이후 정체. Ink 5+ 호환 미확인. | cli-highlight + 자체 최소 markdown 렌더. |
| `ink-table@3.1.0` | 2 년 정체, Ink 7 미검증. | `<Box flexDirection="column">` 으로 직접 조립. |
| `ink-scrollbar@1.0.0` | 4 년 정체. | 스크롤 로직 자체 구현 (PgUp/PgDn + offset state). |
| `ink-big-text@2.0.0` / `ink-gradient` 필수화 | 배너는 부가요소. 넣더라도 LOW priority. | 옵셔널 — 기본 렌더는 plain text. |
| `diff2html` / `react-diff-view` | HTML/DOM 기반. 터미널 부적합. | `diff@9` + Ink `<Box>` 로 hunk 렌더. |
| Shiki / Prism / highlight.js 직접 | cli-highlight 가 이미 터미널 전용으로 래핑. | `cli-highlight@2.1.11`. |
| `pkg` (vercel) | Node.js 12 타겟, 2024 이후 정체. | `bun build --compile` — 필요해질 때. |
| `oclif` | 풀 CLI 프레임워크. harness 는 하나의 엔트리포인트만 필요. | `process.argv` + 간단 파싱 (+ 필요시 `commander@14`). |
| bun test (스냅샷 회귀 용도) | snapshot diff UX 가 vitest 대비 약함 (2026-04 기준). | `vitest@4.1.5`. |
| Ink alternate screen buffer (v7 신규) | PROJECT.md 가 명시적 금지 — scrollback 유지 필수. | 기본 inline 렌더(현재 스켈레톤 방식). |

---

## Stack Patterns by Variant

**로컬 단독 실행(`harness --resume <id>`):**
- WS 연결 스킵. agent 출력은 파일 replay 또는 로컬 `harness_server.py` 에 `HARNESS_URL=ws://127.0.0.1:7891` 로 접속.
- Zustand store 는 변경 없음.

**외부 원격 사용자:**
- env var 3 개만 세팅 (`HARNESS_URL`, `HARNESS_TOKEN`, `HARNESS_ROOM`).
- ws.ts 의 `connect()` 가 room 헤더 전송.
- Zustand store 에 `room.members: Member[]` 추가 (presence 렌더용).

**One-shot(`harness "질문"`):**
- Ink 앱을 full 렌더하지 않고 `render(<OneShotView prompt={...}/>)` 로 `waitUntilExit` 없이 stdout 스트리밍 후 자동 종료.
- 같은 Zustand store 재사용.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `ink@7.0.1` | `react@>=19.2.0`, `@types/react@>=19.2.0`, Node 22+ | peer dep 강제. 하나라도 낮으면 설치 거부 또는 런타임 에러. |
| `ink-text-input@6` | `ink@>=5`, `react@>=18` | 사용 안 함(위 참조). |
| `ink-select-input@6.2` | `ink@>=5.0.0`, `react@>=18.0.0` | ink@7 에서 실전 확인 필요 — Phase 1 초반 smoke. |
| `@inkjs/ui@2.0.0` | `ink@>=5` | ink@7 peer 선언 없음 — 실전 검증 task 필요. 문제 생기면 개별 대체 (ConfirmInput 자체 구현 등). |
| `zustand@5.0.12` | `react@>=18` (19 공식 권장) | v4 code 와 90% 호환. |
| `ws@8.20.0` | Node `>=10.0.0` | bun 은 공식 지원 아니나 동작 확인됨 (주의: `upgrade` 이벤트 미지원 bun#5951). |
| `vitest@4.1.5` | Node `>=20.19 / >=22.12`, Vite 7 | Node 22.21 에서 OK. |
| `cli-highlight@2.1.11` | Node `>=14` | 정체 중이나 안정. highlight.js 11 에 의존. |
| `diff@9.0.0` | Node `>=18` | 2026-04 에 v9 메이저, API 안정. |
| `bun@1.2.19` → package 설치 | 전체 | 스켈레톤 이미 bun 전제. |

---

## 스켈레톤 현황 vs 권고 (diff)

| 파일 | 현재 | 권고 조치 |
|------|------|-----------|
| `package.json` | ink@5 / react@18 / zustand@4 / ink-text-input | ink@7 / react@19.2 / zustand@5 로 전부 bump. `ink-text-input` 삭제. `@inkjs/ui`, `ink-spinner`, `ink-select-input`, `ink-link`, `diff`, `cli-highlight` 추가. dev 에 vitest + ink-testing-library 추가. |
| `scripts.dev` | `bun run --watch src/index.tsx` | 유지. |
| `scripts.typecheck` | `tsc --noEmit` | 유지. tsconfig 는 신규 작성(현재 없음 → 위 "8. TypeScript 설정 패턴" 적용). |
| `src/index.tsx` | (미확인, 스켈레톤 엔트리) | ink@7 의 `render` 시그니처 동일, 변경 불필요. |
| `src/App.tsx` | `SPIN` 배열 + `ink-text-input` 사용 | `SPIN` 삭제 → `ink-spinner`. `TextInput` → 자체 `<MultilineInput>`. 슬래시 popup `<Select>` 추가. |
| `src/store.ts` | zustand@4 `create<State>((set) => ...)` | v5 에서도 동일 동작. 타입은 `create<State>()(set => ...)` 의 curried 형태로 옮기면 더 엄격 (v5 권고). |
| `src/ws.ts` | `ws@8` + `useStore.getState()` | 유지. 추후 `confirm_write` / `confirm_bash` / `room_*` / `state_snapshot` 라우팅 추가(이 STACK 이 아니라 ARCHITECTURE 결정). |

---

## Sources

- npm registry CLI (`npm view <pkg> version`, `npm view <pkg> peerDependencies`) — **HIGH** confidence (작성 시각 2026-04-23 조회)
  - ink@7.0.1, react@19.2.5, zustand@5.0.12, ws@8.20.0, ink-text-input@6.0.0, ink-select-input@6.2.0, @inkjs/ui@2.0.0, ink-spinner@5.0.0, ink-link@5.0.0, ink-gradient@4.0.0, ink-markdown@1.0.4, ink-syntax-highlight@2.0.2, cli-highlight@2.1.11, diff@9.0.0, vitest@4.1.5, ink-testing-library@4.0.0, chalk@5.6.2, typescript@6.0.3, @types/react@19.2.14, @types/node@25.6.0, tsx@4.21.0, bun-types@1.3.13
- Ink GitHub releases — v7 breaking changes (Node 22, React 19.2) — **HIGH** — https://github.com/vadimdemedes/ink/releases
- DeepWiki sst/opencode TUI prompt component 문서 — 멀티라인 입력 레퍼런스 — **MEDIUM** — https://deepwiki.com/sst/opencode/6.5-tui-prompt-component-and-input-handling
- GitHub anomalyco/opencode#11763 — Ink + bun 호환 — **MEDIUM**
- GitHub oven-sh/bun#5951, #6686 — bun `ws` / WebSocket 클라이언트 이슈 — **HIGH** (공식 이슈 트래커)
- Bun 공식 docs: Single-file executable — **HIGH** — https://bun.com/docs/bundler/executables
- Claude Code 스택 유출 분석 (다수 미러 repo) — Ink + Bun + TS + Commander 스택 교차 검증 — **MEDIUM** (출처가 유출본이라 법적/정식 근거 아님, 기술 방향 참고만)
- Zustand 공식 비교 문서 — **HIGH** — https://zustand.docs.pmnd.rs/learn/getting-started/comparison
- 로컬 환경 확인: `bun@1.2.19`, `node@22.21.1` — **HIGH**

**미검증 / LOW confidence 항목:**
- `@inkjs/ui@2.0.0` 의 ink@7 실전 호환 — peer 는 `>=5` 만 선언, v7 에서 정식 검증 없음. Phase 1 초반에 스모크 확인 task 필수.
- `ink-select-input@6.2` 의 ink@7 실전 호환 — 동일.
- Ink 7 `usePaste` 가 bun 런타임에서 paste bracketed 모드 정확 전달하는지 — 공식 호환 매트릭스 부재.

---

*Stack research for: harness ui-ink (Node + Ink + Zustand + bun + TypeScript)*
*Researched: 2026-04-23*
