---
phase: 01-foundation
plan: A
type: execute
wave: 1
depends_on: []
files_modified:
  - ui-ink/package.json
  - ui-ink/tsconfig.json
  - ui-ink/eslint.config.js
  - ui-ink/scripts/ci-no-escape.sh
autonomous: true
requirements:
  - FND-01
  - FND-02
  - FND-09
  - FND-10
  - FND-11

must_haves:
  truths:
    - "bun install 이후 ink@7, react@19.2, zustand@5, ws@8.20.0, @types/react@19.2 가 node_modules 에 설치된다"
    - "@inkjs/ui@2, ink-spinner@5, ink-select-input@6.2, ink-link@5, diff@9, cli-highlight@2, vitest@4, ink-testing-library@4 가 설치된다"
    - "ink-text-input 이 package.json 에서 제거된다"
    - "tsc --noEmit 가 react-jsx + moduleResolution:bundler + strict + lib:ES2022 설정으로 green 이다"
    - "ESLint 가 process.stdout.write / console.log / div/span JSX / child_process.spawn 를 오류로 잡는다"
    - "grep '\\x1b\\[?1049\\|?1000' ui-ink/src/ 가 빈 결과를 반환한다 (CI 가드 스크립트)"
  artifacts:
    - path: "ui-ink/package.json"
      provides: "정확한 의존성 버전 선언"
      contains: '"ink": "^7.0.1"'
    - path: "ui-ink/tsconfig.json"
      provides: "TypeScript 빌드 설정"
      contains: '"jsx": "react-jsx"'
    - path: "ui-ink/eslint.config.js"
      provides: "금지 패턴 ESLint 규칙"
      contains: "no-restricted-syntax"
    - path: "ui-ink/scripts/ci-no-escape.sh"
      provides: "alternate screen / mouse tracking 금지 CI 가드"
  key_links:
    - from: "ui-ink/package.json"
      to: "node_modules/ink"
      via: "bun install"
      pattern: '"ink": "\\^7'
    - from: "ui-ink/eslint.config.js"
      to: "ui-ink/src/*.tsx"
      via: "eslint --max-warnings=0"
      pattern: "no-restricted-syntax"
---

<objective>
ui-ink 의 의존성과 빌드 도구를 Phase 2+ 가 요구하는 상태로 완전히 업그레이드한다.

Purpose: 현재 스켈레톤은 ink@5 / react@18 / zustand@4 로 묶여있어 Phase 2 에서 필요한 usePaste · useWindowSize 등 Ink 7 훅을 사용할 수 없다. 이 plan 은 그 물리적 전제를 해소한다.
Output: 업그레이드된 package.json, 수정된 tsconfig.json, ESLint 금지 규칙, CI 가드 스크립트
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/johyeonchang/harness/.planning/PROJECT.md
@/Users/johyeonchang/harness/.planning/ROADMAP.md
@/Users/johyeonchang/harness/.planning/STATE.md
@/Users/johyeonchang/harness/CLAUDE.md

<interfaces>
<!-- 현재 package.json (bump 대상) -->
현재 의존성:
  ink: "^5.0.1"          → 목표: "^7.0.1"
  react: "^18.3.1"       → 목표: "^19.2.5"
  zustand: "^4.5.2"      → 목표: "^5.0.12"
  ws: "^8.18.0"          → 목표: "^8.20.0"
  ink-text-input: "^6.0.0" → 제거

현재 devDependencies:
  @types/react: "^18.3.3"  → 목표: "^19.2.5" (또는 최신 19.x)
  typescript: "^5.4.5"     → 목표: "^6.0.3"

추가할 dependencies:
  @inkjs/ui: "^2.0.0"
  ink-spinner: "^5.0.0"
  ink-select-input: "^6.2.0"
  ink-link: "^5.0.0"
  diff: "^9.0.0"
  cli-highlight: "^2.1.11"

추가할 devDependencies:
  vitest: "^4.1.5"
  ink-testing-library: "^4.0.0"
  @types/ws: "^8.5.10"  (유지)
  eslint: "^9.0.0" (신규)

현재 tsconfig.json:
  "jsx": "react"           → 목표: "react-jsx"
  "moduleResolution": "bundler" (이미 맞음 — 유지)
  "lib": ["ES2022"]        (이미 맞음 — 유지)
  "strict": true           (이미 맞음 — 유지)
  DOM 타입 없음             (이미 맞음 — 유지)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task A-1: package.json 의존성 업그레이드 및 ink-text-input 제거</name>
  <files>ui-ink/package.json</files>
  <read_first>
    - /Users/johyeonchang/harness/ui-ink/package.json (현재 의존성 전체 확인 필수)
  </read_first>
  <action>
ui-ink/package.json 을 아래 최종 상태로 교체한다. bun install 후 bun run typecheck 가 통과하는지 확인한다.

최종 package.json 내용:
```json
{
  "name": "harness-ink",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "bun run src/index.tsx",
    "dev": "bun run --watch src/index.tsx",
    "typecheck": "tsc --noEmit",
    "lint": "eslint src --max-warnings=0",
    "test": "vitest run",
    "ci:no-escape": "bash scripts/ci-no-escape.sh"
  },
  "engines": {
    "bun": ">=1.2.19",
    "node": ">=22.0.0"
  },
  "dependencies": {
    "@inkjs/ui": "^2.0.0",
    "cli-highlight": "^2.1.11",
    "diff": "^9.0.0",
    "ink": "^7.0.1",
    "ink-link": "^5.0.0",
    "ink-select-input": "^6.2.0",
    "ink-spinner": "^5.0.0",
    "react": "^19.2.5",
    "ws": "^8.20.0",
    "zustand": "^5.0.12"
  },
  "devDependencies": {
    "@types/bun": "latest",
    "@types/react": "^19.1.0",
    "@types/ws": "^8.5.10",
    "eslint": "^9.0.0",
    "ink-testing-library": "^4.0.0",
    "typescript": "^6.0.3",
    "vitest": "^4.1.5"
  }
}
```

주의:
- ink-text-input 은 완전히 제거. dependencies 에 등장하면 안 된다 (FND-01).
- ink@7 peer 는 react >=19.2.0 강제이므로 react: "^19.2.5" 정확히 표기.
- ws@8.20.0 은 커스텀 헤더(x-harness-token, x-harness-room) 지원 버전이다.
- "engines" 필드에 bun >=1.2.19, node >=22.0.0 명시 (Pitfall 18 방지).

교체 후 반드시 실행:
```bash
cd /Users/johyeonchang/harness/ui-ink && bun install
```
  </action>
  <verify>
    <automated>cd /Users/johyeonchang/harness/ui-ink && grep '"ink":' package.json | grep '"\^7' && grep '"react":' package.json | grep '"\^19' && grep '"zustand":' package.json | grep '"\^5' && ! grep 'ink-text-input' package.json && echo "OK"</automated>
  </verify>
  <acceptance_criteria>
    - package.json 에 `"ink": "^7.0.1"` 포함
    - package.json 에 `"react": "^19.2.5"` 포함
    - package.json 에 `"zustand": "^5.0.12"` 포함
    - package.json 에 `"ws": "^8.20.0"` 포함
    - package.json 에 `@inkjs/ui`, `ink-spinner`, `ink-select-input`, `ink-link`, `diff`, `cli-highlight` 모두 포함
    - package.json 에 `vitest`, `ink-testing-library` devDependencies 포함
    - package.json 에 `ink-text-input` 문자열이 0건
    - `bun install` 이 에러 없이 완료
  </acceptance_criteria>
  <done>bun install 완료, node_modules/ink 버전 7.x, node_modules/ink-text-input 없음</done>
</task>

<task type="auto" tdd="false">
  <name>Task A-2: tsconfig.json 수정 — react-jsx 설정</name>
  <files>ui-ink/tsconfig.json</files>
  <read_first>
    - /Users/johyeonchang/harness/ui-ink/tsconfig.json (현재 설정 확인)
    - /Users/johyeonchang/harness/ui-ink/src/App.tsx (import React 패턴 확인 — react-jsx 로 바꾸면 명시적 import 불필요)
  </read_first>
  <action>
tsconfig.json 의 `"jsx"` 값을 `"react"` 에서 `"react-jsx"` 로 변경한다. 나머지 설정은 유지.

변경 후 최종 tsconfig.json:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2022"],
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "allowImportingTsExtensions": true,
    "noEmit": true
  },
  "include": ["src/**/*"]
}
```

주의:
- `"jsx": "react-jsx"` 로 바꾸면 각 .tsx 파일에서 `import React from 'react'` 가 없어도 JSX 가 동작한다. 기존 App.tsx 는 이미 `import React from 'react'` 를 가지고 있으므로 중복이 되지만 에러는 아니다. 이번 태스크에서 .tsx 파일 수정은 필요 없다.
- DOM 타입(lib 에 "DOM" 없음)은 유지한다. Ink 앱에 document/window 없음.
- `strict: true` 는 유지한다.

변경 후 타입 검사:
```bash
cd /Users/johyeonchang/harness/ui-ink && bun run typecheck
```
현 스켈레톤의 App.tsx 가 ink@5 import 를 쓰고 있어 ink@7 로 업그레이드 후 타입 에러가 날 수 있다. 타입 에러는 Plan B(WS 프로토콜 재구성) 에서 파일들을 교체하면 해소되므로 이 태스크에서는 tsconfig.json 값 변경만 확인한다.
  </action>
  <verify>
    <automated>cd /Users/johyeonchang/harness/ui-ink && grep '"jsx"' tsconfig.json | grep 'react-jsx' && echo "OK"</automated>
  </verify>
  <acceptance_criteria>
    - tsconfig.json 에 `"jsx": "react-jsx"` 포함 (쌍따옴표 포함)
    - tsconfig.json 에 `"moduleResolution": "bundler"` 포함
    - tsconfig.json 에 `"strict": true` 포함
    - tsconfig.json 의 lib 배열에 `"DOM"` 이 없음 (`grep '"DOM"' tsconfig.json` 빈 결과)
  </acceptance_criteria>
  <done>tsconfig.json 에 react-jsx 설정 반영, DOM 타입 없음 확인</done>
</task>

<task type="auto" tdd="false">
  <name>Task A-3: ESLint 금지 규칙 설정 + CI escape 가드 스크립트</name>
  <files>ui-ink/eslint.config.js, ui-ink/scripts/ci-no-escape.sh</files>
  <read_first>
    - /Users/johyeonchang/harness/CLAUDE.md (절대 금지 목록 — 어떤 패턴을 막아야 하는지)
    - /Users/johyeonchang/harness/ui-ink/package.json (eslint 스크립트 확인)
  </read_first>
  <action>
두 파일을 새로 생성한다.

**1) ui-ink/eslint.config.js** — ESLint flat config 형식 (ESLint 9 방식):

```js
// ESLint flat config — Ink 금지 패턴 강제 (FND-10)
import js from '@eslint/js'

export default [
  js.configs.recommended,
  {
    files: ['src/**/*.{ts,tsx}'],
    rules: {
      // Ink 이중 렌더 붕괴 방지 (CLAUDE.md 절대 금지)
      'no-restricted-syntax': [
        'error',
        {
          selector: "CallExpression[callee.object.name='process'][callee.property.name='stdout'][callee.property.object.property.name='write']",
          message: 'process.stdout.write 금지 — Ink 이중 렌더 붕괴. Ink <Text> 컴포넌트 사용'
        },
        {
          selector: "CallExpression[callee.object.name='console'][callee.property.name='log']",
          message: 'console.log 금지 — Ink 이중 렌더 붕괴. Ink <Text> 컴포넌트 사용'
        },
        {
          selector: "CallExpression[callee.object.name='console'][callee.property.name='error']",
          message: 'console.error 금지 — Ink 이중 렌더 붕괴. Ink <Text> 컴포넌트 사용'
        },
        {
          selector: "CallExpression[callee.object.name='console'][callee.property.name='warn']",
          message: 'console.warn 금지 — Ink 이중 렌더 붕괴. Ink <Text> 컴포넌트 사용'
        },
        {
          // child_process.spawn 금지 — Ink 화면 박살 (bun#27766)
          selector: "CallExpression[callee.object.name='child_process'][callee.property.name='spawn']",
          message: 'child_process.spawn 금지 — Ink 화면 붕괴. 서버에서만 사용'
        },
        {
          // <div> JSX 금지 — Ink 에는 DOM 태그 없음
          selector: "JSXOpeningElement[name.name='div']",
          message: '<div> 금지 — Ink 에는 DOM 태그 없음. <Box> 사용'
        },
        {
          // <span> JSX 금지
          selector: "JSXOpeningElement[name.name='span']",
          message: '<span> 금지 — Ink 에는 DOM 태그 없음. <Text> 사용'
        }
      ]
    }
  }
]
```

주의: `@eslint/js` 패키지가 eslint@9 에 번들되어 있지 않으면 devDependencies 에 추가 필요. eslint@9 flat config 는 `@eslint/js` 를 별도로 설치해야 함. package.json devDependencies 에 `"@eslint/js": "^9.0.0"` 를 추가한다.

**2) ui-ink/scripts/ci-no-escape.sh** — alternate screen / mouse tracking 금지 CI 가드:

```bash
#!/usr/bin/env bash
# CI 가드: alternate screen(ESC[?1049h) / mouse tracking(ESC[?1000h 계열) 금지 (FND-11)
# harness CLAUDE.md 절대 금지 목록 자동 검증

set -e

RESULT=$(grep -rn $'\x1b\[\?1049\|\x1b\[\?1000\|\x1b\[\?1002\|\x1b\[\?1003\|\x1b\[\?1006' ui-ink/src/ 2>/dev/null || true)

if [ -n "$RESULT" ]; then
  echo "오류: alternate screen 또는 mouse tracking escape 코드 발견"
  echo "$RESULT"
  exit 1
fi

# 문자열 리터럴로도 검색
RESULT2=$(grep -rn '1049h\|1000h\|?1002\|?1003\|?1006\|smcup\|rmcup' ui-ink/src/ 2>/dev/null || true)

if [ -n "$RESULT2" ]; then
  echo "오류: alternate screen 관련 패턴 발견"
  echo "$RESULT2"
  exit 1
fi

echo "OK: alternate screen / mouse tracking escape 코드 없음"
```

스크립트를 실행 가능하게 설정:
```bash
chmod +x /Users/johyeonchang/harness/ui-ink/scripts/ci-no-escape.sh
mkdir -p /Users/johyeonchang/harness/ui-ink/scripts
```

scripts/ 디렉토리가 없으면 먼저 생성한다.
  </action>
  <verify>
    <automated>cd /Users/johyeonchang/harness/ui-ink && test -f eslint.config.js && grep 'no-restricted-syntax' eslint.config.js && test -f scripts/ci-no-escape.sh && bash scripts/ci-no-escape.sh && echo "OK"</automated>
  </verify>
  <acceptance_criteria>
    - ui-ink/eslint.config.js 파일 존재
    - eslint.config.js 에 `no-restricted-syntax` 규칙 포함
    - eslint.config.js 에 `process.stdout.write`, `console.log`, `child_process.spawn`, `div`, `span` 관련 금지 셀렉터 포함
    - ui-ink/scripts/ci-no-escape.sh 파일 존재
    - `bash scripts/ci-no-escape.sh` 실행 시 현재 src/ 에서 오류 없이 "OK" 출력
    - ci-no-escape.sh 에 `1049h` 또는 `?1049` 패턴 grep 로직 포함
  </acceptance_criteria>
  <done>ESLint 금지 규칙 파일 생성 완료, CI 가드 스크립트 실행 가능 상태</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| 개발자 → package.json | npm/bun 레지스트리에서 pull 하는 패키지가 악의적 변경을 포함할 수 있음 |
| CI 가드 스크립트 → src/ | 가드 우회 시 alternate screen 코드가 빌드에 포함될 수 있음 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01A-01 | Tampering | package.json 의존성 | mitigate | bun install --frozen-lockfile 로 lockfile 기반 재현 가능 빌드 강제 (Phase 4 CI) |
| T-01A-02 | Tampering | ci-no-escape.sh | accept | 로컬 개발 도구, 외부 공격 벡터 없음. 스크립트 변조는 git 이력으로 탐지 |
| T-01A-03 | Elevation of Privilege | ESLint 우회 (// eslint-disable) | mitigate | --max-warnings=0 로 경고도 빌드 실패 처리 |
</threat_model>

<verification>
```bash
# 1. 의존성 버전 확인
cd /Users/johyeonchang/harness/ui-ink
grep '"ink":' package.json    # ^7.0.1 이어야 함
grep '"react":' package.json  # ^19.2.5 이어야 함
grep '"zustand":' package.json # ^5.0.12 이어야 함
! grep 'ink-text-input' package.json  # 없어야 함

# 2. tsconfig jsx 확인
grep '"jsx"' tsconfig.json  # "react-jsx" 이어야 함

# 3. ESLint 파일 확인
test -f eslint.config.js && grep 'no-restricted-syntax' eslint.config.js

# 4. CI 가드 실행
bash scripts/ci-no-escape.sh
```
</verification>

<success_criteria>
- package.json 에 ink@7.0.1, react@19.2.5, zustand@5.0.12 선언
- ink-text-input 제거 확인
- @inkjs/ui, ink-spinner, ink-select-input, ink-link, diff, cli-highlight, vitest, ink-testing-library 추가 확인
- tsconfig.json "jsx": "react-jsx" 확인
- eslint.config.js 에 process.stdout.write / console.log / div/span / child_process.spawn 금지 규칙
- scripts/ci-no-escape.sh 실행 시 현재 src/ 에서 green
</success_criteria>

<output>
완료 후 `/Users/johyeonchang/harness/.planning/phases/01-foundation/01-A-SUMMARY.md` 생성.
</output>
