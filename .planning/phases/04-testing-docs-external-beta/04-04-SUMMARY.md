---
phase: 04-testing-docs-external-beta
plan: "04"
subsystem: docs
tags:
  - documentation
  - beta-prep
  - protocol
  - client-setup
dependency_graph:
  requires:
    - 04-03
  provides:
    - CLIENT_SETUP.md (bun/ui-ink 기반 설치 가이드)
    - PROTOCOL.md (WS 프로토콜 완전 명세 v1)
    - RELEASE_NOTES.md (Python REPL 마이그레이션 노트)
  affects: []
tech_stack:
  added: []
  patterns:
    - TypeScript interface 수준 프로토콜 명세 (AI 에이전트 친화적)
key_files:
  created:
    - PROTOCOL.md
    - RELEASE_NOTES.md
  modified:
    - CLIENT_SETUP.md
decisions:
  - D-08 준수: CLIENT_SETUP.md 명령어 위주, git clone → bun install --frozen-lockfile → env var 3개 → bun start
  - D-09 준수: PROTOCOL.md TypeScript interface 형식, 시퀀스 다이어그램 없음, AI 에이전트 구현 가능 밀도
  - D-10 준수: RELEASE_NOTES.md Python REPL 대비 달라진 점 중심, history.txt 호환 명시
metrics:
  duration: "10분"
  completed: "2026-04-24"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 3
---

# Phase 04 Plan 04: 외부 Beta 문서 3종 완성 Summary

외부 2인 beta를 위한 문서 3종(CLIENT_SETUP.md 재작성, PROTOCOL.md 신규, RELEASE_NOTES.md 신규)을 완성했습니다. bun/ui-ink 기준 설치 가이드 + AI 에이전트가 WS 프로토콜을 구현할 수 있는 TypeScript interface 수준 명세 + Python REPL 마이그레이션 노트.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | CLIENT_SETUP.md 재작성 + RELEASE_NOTES.md 신규 작성 | c16363e | CLIENT_SETUP.md, RELEASE_NOTES.md |
| 2 | PROTOCOL.md 신규 작성 | 8591a87 | PROTOCOL.md |

## What Was Built

### CLIENT_SETUP.md (완전 재작성)

- Node.js/npm/`ui/` 기반 구버전 → bun/`ui-ink/` 기준으로 완전 교체
- D-08 준수: 명령어 위주, why 생략. `git clone → bun install --frozen-lockfile → env var 3개 → bun start` 순서
- 3종 env var(`HARNESS_URL`, `HARNESS_TOKEN`, `HARNESS_ROOM`) 명시
- 문제 해결 섹션: bun 미설치, native dep 실패, 연결 오류, macOS IME

### PROTOCOL.md (신규)

- 26종 ServerMsg + 6종 ClientMsg 전수 TypeScript interface 정의
- WS 연결 헤더 4종: `x-harness-token`(필수), `x-harness-room`, `x-resume-from`, `x-resume-session`
- 모든 서버 메시지의 `event_id: number` 필드 명시 (PEXT-03)
- PEXT-01~05 확장 목록 표 + 각 해당 interface inline 주석
- Known Bugs 섹션: CR-01 상세 기술 (심각도·현상·원인·수정 방법)
- 기본 REPL 흐름 / Room 흐름 / 재연결 흐름 텍스트 시퀀스

### RELEASE_NOTES.md (신규)

- Python REPL vs ui-ink 실행 방법 비교표
- 키 바인딩 대조표 (Enter/Ctrl+J/Ctrl+C/Ctrl+D 등)
- `~/.harness/history.txt` 포맷 호환 명시 (마이그레이션 불필요)
- 새로 생긴 기능: 공유 Room, 자동 재연결, Diff 미리보기, 슬래시 팝업, one-shot
- 알려진 버그: CR-01 confirm_write 승인이 거부로 처리되는 문제
- 업그레이드 경로: git pull → bun install --frozen-lockfile → history.txt 유지 → config.yaml → env var 이전

## Deviations from Plan

None — 플랜 그대로 실행되었습니다.

## Threat Surface Scan

T-04-09 준수: CLIENT_SETUP.md에 실제 토큰/IP 없음. 예시값(`ws://서버IP:7891`, `토큰문자열`)만 사용.
T-04-11 준수: PROTOCOL.md에 `x-harness-token`을 "필수"로 명시. 예제에 더미값 사용.

## Self-Check: PASSED

| 항목 | 결과 |
|------|------|
| CLIENT_SETUP.md 존재 | FOUND |
| PROTOCOL.md 존재 | FOUND |
| RELEASE_NOTES.md 존재 | FOUND |
| 04-04-SUMMARY.md 존재 | FOUND |
| 커밋 c16363e 존재 | FOUND |
| 커밋 8591a87 존재 | FOUND |
