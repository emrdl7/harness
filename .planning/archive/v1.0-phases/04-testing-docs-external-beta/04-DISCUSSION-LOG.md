# Phase 4: Testing + Docs + External Beta — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 04-testing-docs-external-beta
**Areas discussed:** 통합 테스트 방식, CI matrix, 문서 타겟/깊이, Beta 준비 범위

---

## 통합 테스트 방식 (TST-02)

| Option | Description | Selected |
|--------|-------------|----------|
| in-process 실제 ws 서버 | vitest 내 `ws` 라이브러리로 실제 WS 서버 기동 (랜덤 포트) | ✓ (Claude's Discretion) |
| vi.mock 이벤트 시뮬레이션 | HarnessClient WS 레이어 mock으로 이벤트 주입 | |
| Python 테스트 방식 참고 | 실제 서버 시나리오 실시 기반 | |

**User's choice:** "개발을 일단 마쳐야 함... 아직 하드웨어 준비 안됐음... 한동안 이 pc에서 돌려야 할지도 모름 참고해서 알아서 판단해"  
**Notes:** Claude's Discretion 적용. 단일 PC 환경이지만 in-process 랜덤 포트 서버로 충분히 동작. 하드웨어가 없을수록 자동 통합 테스트 신뢰도가 중요하므로 실제 WS 핸드셰이크 방식 채택.

---

## CI matrix (TST-04)

| Option | Description | Selected |
|--------|-------------|----------|
| ubuntu-latest 단일 | 빠르고 저렴 | |
| ubuntu + macOS matrix | 두 OS 커버 | ✓ (Claude's Discretion) |

| Option | Description | Selected |
|--------|-------------|----------|
| 레포 root .github/ | ui-ink + Python 통합 | ✓ |
| ui-ink/ 별도 | — | |

**User's choice (CI 위치):** 레포 root .github/  
**User's choice (OS):** "한명은 맥, 한명은 윈도우 wsl 환경이야... 참고해서 알아서 판단해.."  
**Notes:** Claude's Discretion — ubuntu가 WSL 커버, macOS가 mac 커버. Windows native runner 불필요.

---

## 문서 타겟 및 깊이 (TST-06/07)

| Option | Description | Selected |
|--------|-------------|----------|
| 외부 beta 참가자용 CLIENT_SETUP.md | 10분 설치 수준 | |
| 내부 개발자용 최소화 | 명령어만 | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| 내부 개발자 레퍼런스 PROTOCOL.md | 타입 정의 나열 | |
| AI 에이전트 친화적 PROTOCOL.md | JSON schema 수준 정밀도 | ✓ |

**User's choice (CLIENT_SETUP):** "내가 직접 설명하면 되니까 메뉴얼은 최대한 간단하게"  
**User's choice (PROTOCOL):** "내가 읽을일은 없을꺼 같아... 클로드나 다른 ai가 알아서 할 수준?"  
**Notes:** CLIENT_SETUP.md = 명령어 3~4줄. PROTOCOL.md = Claude/Codex가 새 클라이언트 구현 가능한 정밀도.

---

## Beta 준비 범위 (TST-08)

| Option | Description | Selected |
|--------|-------------|----------|
| 준비 자료만 + 매뉴얼 체크리스트 | 실제 beta는 수동 진행 | ✓ |
| Phase 4에서 실제 beta 실행 | 2인 접속 + PITFALLS 수동 확인 | |

**User's choice:** 준비 자료만 + 매뉴얼 체크리스트  
**Notes:** 하드웨어 미준비. Phase 4 성공 기준에 실제 beta 실행 포함하지 않음.

---

## Claude's Discretion

- **TST-02 Fake WS 구현**: in-process ws 서버 (user가 Claude 판단 위임)
- **CI OS matrix**: ubuntu + macOS (user가 Claude 판단 위임)
- **TST-01 단위 테스트 보완 범위**: 기존 146건 대비 미커버 항목 Claude 분석 후 결정
- **TST-03 스냅샷 구현 방식**: ink-testing-library render output 기반 Claude 결정

## Deferred Ideas

- 실제 외부 beta 실행 — 하드웨어 준비 후
- 히스토리 마이그레이션 스크립트 — 필요 시 별도 추가
- 바이너리 배포 prototype (D2-04) — v2 여유분
