---
phase: 04-testing-docs-external-beta
plan: 02
subsystem: ci
tags: [ci, github-actions, matrix, bun, node, pytest, TST-04]
dependency_graph:
  requires: []
  provides: [.github/workflows/ci.yml]
  affects: []
tech_stack:
  added: [GitHub Actions, oven-sh/setup-bun@v2, actions/setup-python@v5]
  patterns: [OS×runtime matrix, fail-fast: false, conditional steps per runtime]
key_files:
  created: [.github/workflows/ci.yml]
  modified: []
decisions:
  - "ui-ink job: bun runtime에서만 typecheck/vitest/guard/ci:no-escape 실행 (node runtime은 install 검증만)"
  - "Python 3.14 allow-prereleases: true 추가 — T-04-06 mitigate (3.14 pre-release 설치 실패 방지)"
  - "fail-fast: false — 한 OS 실패가 다른 OS 결과를 숨기지 않도록"
metrics:
  duration: 56s
  completed_date: "2026-04-24"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Phase 04 Plan 02: CI Matrix 생성 Summary

**One-liner:** ubuntu+macOS × bun+Node22 매트릭스로 ui-ink 4단계(typecheck/vitest/guard/ci:no-escape) + Python pytest 2-OS 검증을 자동화하는 GitHub Actions CI 파이프라인 생성.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | .github/workflows/ci.yml 생성 | 8101d9d | .github/workflows/ci.yml |

---

## What Was Built

`.github/workflows/ci.yml` — GitHub Actions CI 파이프라인 단일 파일.

### ui-ink job (4개 matrix 조합)

- **Matrix:** `ubuntu-latest + macos-latest` × `bun + node`
- **bun runtime:** `bun install --frozen-lockfile` → `typecheck` → `vitest run` → `guard` → `ci:no-escape`
- **node runtime:** `npm ci` (설치 검증만 — bun 전용 스크립트는 조건부 스킵)
- **트리거:** push + pull_request (main 브랜치)

### python job (2개 OS)

- **Matrix:** `ubuntu-latest + macos-latest`
- **Python 버전:** 3.14 (`allow-prereleases: true` — T-04-06 mitigate)
- **설치:** `pip install -e ".[dev]"` fallback `requirements.txt`
- **실행:** `python -m pytest -x --tb=short`

### 보안 (T-04-04 mitigate)

- `HARNESS_TOKEN`, `HARNESS_URL`, `HARNESS_ROOM` 하드코딩 없음
- 테스트는 Fake WS 서버 기반 — 실제 서버 연결 불필요
- `actions/checkout@v4`, `oven-sh/setup-bun@v2`, `actions/setup-python@v5` 공식 Actions 사용

---

## Deviations from Plan

없음 — 플랜이 지정한 yml 구조를 그대로 구현함.

---

## Known Stubs

없음.

---

## Threat Flags

없음. 위협 모델(T-04-04, T-04-05, T-04-06) 모두 플랜 내 정의됨.

---

## Self-Check: PASSED

- [x] `.github/workflows/ci.yml` 존재 확인
- [x] yaml 파싱 OK (`import yaml; yaml.safe_load(...)`)
- [x] ubuntu-latest + macOS-latest 양쪽 존재
- [x] runtime: [bun, node] matrix 존재
- [x] bun install --frozen-lockfile 포함
- [x] bun run guard 스텝 포함
- [x] bun run ci:no-escape 스텝 포함
- [x] pytest 스텝 포함
- [x] HARNESS_TOKEN/HARNESS_URL 하드코딩 없음
- [x] 커밋 8101d9d 존재
