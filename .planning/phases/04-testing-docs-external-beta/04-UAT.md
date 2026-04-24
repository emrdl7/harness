---
status: complete
phase: 04-testing-docs-external-beta
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md, 04-04-SUMMARY.md, 04-05-SUMMARY.md]
started: 2026-04-24T09:00:00Z
updated: 2026-04-24T09:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. vitest 전체 통과 (163건)
expected: `cd ui-ink && bun run test` → 163건 전체 PASS (또는 그 이상). 에러 0건.
result: pass

### 2. TypeScript 타입체크 통과
expected: `cd ui-ink && bun run tsc --noEmit` 실행 시 에러 0건. 타입 오류 없이 완료.
result: pass

### 3. guard 스크립트 통과 (금지 패턴 검사)
expected: `cd ui-ink && bun run guard` 실행 시 process.stdout.write / console.log / alternate screen escape 등 금지 패턴 0건. PASSED 메시지 출력.
result: pass

### 4. ci:no-escape 통과 (alternate screen 금지)
expected: `cd ui-ink && bun run ci:no-escape` (또는 `guard-forbidden.sh`) 실행 시 \x1b[?1049h 등 금지 이스케이프 0건. 스크립트 종료 코드 0.
result: pass

### 5. CI 워크플로우 파일 구조 확인
expected: `.github/workflows/ci.yml` 파일이 존재하며, ubuntu-latest + macos-latest 두 OS, bun + node 두 런타임의 matrix가 정의되어 있음. Python pytest 스텝도 포함.
result: pass

### 6. pytest 전체 통과 (Python 백엔드)
expected: `.venv/bin/python -m pytest -x --tb=short` 실행 시 260건 이상 PASS. Phase 3 추가 테스트(TestEventBuffer, TestAgentStartFromSelf 등) 포함.
result: pass

### 7. CLIENT_SETUP.md — bun/ui-ink 기반 설치 가이드
expected: 루트에 `CLIENT_SETUP.md`가 존재하며, 내용에 `bun install --frozen-lockfile`, `HARNESS_URL`, `HARNESS_TOKEN`, `HARNESS_ROOM` 세 env var가 명시되어 있음. 구버전 `ui/` 경로나 `npm` 명령이 없음.
result: pass

### 8. PROTOCOL.md — WS 프로토콜 명세
expected: 루트에 `PROTOCOL.md`가 존재하며, ServerMsg / ClientMsg TypeScript interface 정의와 WS 헤더 4종(`x-harness-token`, `x-harness-room`, `x-resume-from`, `x-resume-session`), CR-01 Known Bug 섹션이 포함되어 있음.
result: pass

### 9. RELEASE_NOTES.md — 마이그레이션 노트
expected: 루트에 `RELEASE_NOTES.md`가 존재하며, Python REPL vs ui-ink 비교표, 키 바인딩 대조표, `~/.harness/history.txt` 포맷 호환 명시가 포함되어 있음.
result: pass

### 10. PITFALLS 체크리스트
expected: `.planning/phases/04-testing-docs-external-beta/04-PITFALLS-CHECKLIST.md`가 존재하며, P01~P17 항목이 모두 포함되어 있음. 자동 검증 명령어 섹션과 수동 검증 테이블이 분리되어 있음.
result: pass

### 11. CR-01 서버 수정 확인
expected: `harness_server.py`에서 `confirm_write_response` 처리 코드가 `msg.get('result', msg.get('accept', False))` 패턴 (또는 동등한 accept 필드 우선 읽기)으로 되어 있음. grep으로 확인 가능.
result: pass

## Summary

total: 11
passed: 11
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
