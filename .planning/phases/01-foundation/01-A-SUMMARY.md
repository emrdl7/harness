---
phase: 01-foundation
plan: A
subsystem: ui-ink/build
tags: [dependencies, typescript, eslint, ci-guard, ink7, react19]
requires: []
provides: [ink7-deps, react19-deps, zustand5-deps, eslint-forbidden-rules, ci-escape-guard]
affects: [ui-ink/package.json, ui-ink/tsconfig.json, ui-ink/eslint.config.js, ui-ink/scripts/ci-no-escape.sh]
tech_stack:
  added:
    - ink@7.0.1
    - react@19.2.5
    - zustand@5.0.12
    - ws@8.20.0
    - "@inkjs/ui@2.0.0"
    - ink-spinner@5.0.0
    - ink-select-input@6.2.0
    - ink-link@5.0.0
    - diff@9.0.0
    - cli-highlight@2.1.11
    - vitest@4.1.5
    - ink-testing-library@4.0.0
    - eslint@9.0.0
    - typescript@6.0.3
  removed:
    - ink-text-input@6.0.0
  patterns:
    - ESLint flat config (eslint.config.js, ESLint 9)
    - CI bash 가드 스크립트
key_files:
  created:
    - ui-ink/eslint.config.js
    - ui-ink/scripts/ci-no-escape.sh
    - ui-ink/bun.lock
  modified:
    - ui-ink/package.json
    - ui-ink/tsconfig.json
decisions:
  - "@eslint/js 를 devDependencies에 명시 추가 — ESLint 9 flat config에서 별도 설치 필요"
  - "ci-no-escape.sh는 절대 경로 대신 SCRIPT_DIR 기반 상대 경로로 src/ 탐색 — 워크트리/다른 경로에서도 동작"
  - "ESLint selector를 MemberExpression 타입 명시 형태로 작성 — 플랫 AST 셀렉터 정확도 향상"
metrics:
  duration: "약 5분"
  completed: "2026-04-24"
  tasks_completed: 3
  files_changed: 5
---

# Phase 1 Plan A: 의존성·빌드 업그레이드 Summary

ink@7/react@19.2/zustand@5 로 의존성 전면 업그레이드, react-jsx tsconfig 설정, ESLint 금지 규칙 + CI alternate screen 가드 스크립트 구축.

## 완료된 태스크

| Task | 이름 | 커밋 | 핵심 파일 |
|------|------|------|-----------|
| A-1 | package.json 의존성 업그레이드 | 7ecb606 | ui-ink/package.json, ui-ink/bun.lock |
| A-2 | tsconfig.json react-jsx 설정 | 84427ef | ui-ink/tsconfig.json |
| A-3 | ESLint 금지 규칙 + CI 가드 스크립트 | f896797 | ui-ink/eslint.config.js, ui-ink/scripts/ci-no-escape.sh |

## 변경 상세

### Task A-1: package.json 의존성 업그레이드

- ink: `^5.0.1` → `^7.0.1` — Phase 2에서 필요한 `usePaste`, `useWindowSize` 등 Ink 7 훅 사용 가능
- react: `^18.3.1` → `^19.2.5` — ink@7 peer 요구사항
- zustand: `^4.5.2` → `^5.0.12`
- ws: `^8.18.0` → `^8.20.0` — 커스텀 헤더 (x-harness-token, x-harness-room) 지원 버전
- **ink-text-input 완전 제거** (FND-01)
- 신규 추가: @inkjs/ui, ink-spinner, ink-select-input, ink-link, diff, cli-highlight
- devDependencies 추가: vitest@4.1.5, ink-testing-library@4.0.0, eslint@9, @eslint/js@9, typescript@6.0.3
- engines 필드 추가: bun>=1.2.19, node>=22.0.0 (Pitfall 18 방지)
- scripts 추가: lint, test, ci:no-escape

### Task A-2: tsconfig.json react-jsx 설정

- `"jsx": "react"` → `"jsx": "react-jsx"` — 명시적 `import React` 없이 JSX 동작
- DOM 타입 미포함 유지 (`lib: ["ES2022"]`)
- strict: true, moduleResolution: bundler 유지

### Task A-3: ESLint 금지 규칙 + CI escape 가드

**eslint.config.js** (ESLint 9 flat config):
- `no-restricted-syntax` 7개 규칙:
  - `process.stdout.write` 금지 — Ink 이중 렌더 붕괴
  - `console.log`, `console.error`, `console.warn` 금지 — Ink 이중 렌더 붕괴
  - `child_process.spawn` 금지 — Ink 화면 붕괴
  - `<div>` JSX 금지 — DOM 태그 없음, `<Box>` 사용
  - `<span>` JSX 금지 — DOM 태그 없음, `<Text>` 사용

**scripts/ci-no-escape.sh**:
- ESC 코드 리터럴(`\x1b[?1049`, `\x1b[?1000` 등) grep 검색
- 문자열 패턴(`1049h`, `1000h`, `smcup`, `rmcup` 등) 이중 검색
- 현재 src/ 에서 실행 시 "OK" 반환 확인

## 플랜 대비 이탈 사항

### 자동 수정 이슈

**1. [Rule 2 - 개선] ci-no-escape.sh 경로를 절대 경로 대신 SCRIPT_DIR 기반으로 변경**
- 플랜의 예시는 `ui-ink/src/`를 하드코딩했으나 워크트리·다른 위치에서도 동작하도록 `$(dirname "$SCRIPT_DIR")/src` 로 수정
- 파일: `ui-ink/scripts/ci-no-escape.sh`

**2. [Rule 2 - 개선] ESLint selector에 타입 명시 추가**
- 플랜의 selector 예시에서 `callee.object.name='process'` 형태는 MemberExpression 중첩 구조에서 부정확할 수 있어 `callee.type='MemberExpression'` 명시 형태로 작성
- 파일: `ui-ink/eslint.config.js`

## Known Stubs

없음 — 이 플랜은 설정 파일만 다루므로 데이터 흐름 스텁 없음.

## Threat Flags

없음 — 새로운 네트워크 엔드포인트, 인증 경로, 파일 접근 패턴 변경 없음.

## Self-Check: PASSED

- [x] `ui-ink/package.json` 존재 및 ink@7.0.1, react@19.2.5, zustand@5.0.12 포함
- [x] `ui-ink/bun.lock` 존재
- [x] `ui-ink/tsconfig.json` 존재 및 `"jsx": "react-jsx"` 포함
- [x] `ui-ink/eslint.config.js` 존재 및 `no-restricted-syntax` 포함
- [x] `ui-ink/scripts/ci-no-escape.sh` 존재 및 실행 시 "OK" 출력
- [x] 커밋 7ecb606 존재 (Task A-1)
- [x] 커밋 84427ef 존재 (Task A-2)
- [x] 커밋 f896797 존재 (Task A-3)
