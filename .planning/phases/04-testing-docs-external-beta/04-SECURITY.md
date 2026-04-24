---
phase: 4
slug: 04-testing-docs-external-beta
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-24
---

# Phase 4 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Fake WS 서버 ↔ HarnessClient | 통합 테스트 내 in-process TCP — 실 네트워크 없음 | 더미 토큰 / 더미 메시지 |
| GitHub Actions | CI 워크플로우 실행 환경 | 소스코드만 — 실 HARNESS_TOKEN 없음 |
| CLIENT_SETUP.md / PROTOCOL.md | 외부 배포 문서 | 예시값만 — 실 IP/토큰 없음 |
| harness_server.py confirm 경로 | 인증된 WS 연결 내 confirm_write/bash 응답 | accept boolean (CR-01 수정 후) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-04-01 | Denial of Service | Fake WS 서버 (port:0) | mitigate | `afterAll`에서 `fakeServer.close()` Promise wrap 완전 종료. `integration.agent-turn.test.ts:23-26` | closed |
| T-04-02 | Information Disclosure | 테스트 내 token 값 | accept | 더미값('test-token' 등) — 실 토큰 없음. accepted risk. | closed |
| T-04-03 | Denial of Service | 3인 동시 재접속 시나리오 | mitigate | `clients.forEach(c => c.close())` afterEach 정리. describe별 독립 fakeServer. `integration.room.test.ts:97` | closed |
| T-04-04 | Information Disclosure | .github/workflows/ci.yml | mitigate | HARNESS_TOKEN 등 실 토큰 하드코딩 0건 확인. Fake WS 기반 테스트라 secrets 불필요. | closed |
| T-04-05 | Tampering | actions/checkout@v4 | accept | 공식 GitHub Actions 사용. SHA 고정은 이 규모에서 과도한 overhead. accepted risk. | closed |
| T-04-06 | Denial of Service | Python 3.14 allow-prereleases | mitigate | `ci.yml:70` `allow-prereleases: true` — 3.14 GA 이전 설치 실패 방지. | closed |
| T-04-07 | Tampering | 스냅샷 파일 (.snap) | accept | 스냅샷 git commit 대상. CI 불일치 = 자동 실패. accepted risk. | closed |
| T-04-08 | Denial of Service | ink-testing-library columns | accept | 테스트 환경 전용. 실 터미널 영향 없음. accepted risk. | closed |
| T-04-09 | Information Disclosure | CLIENT_SETUP.md | mitigate | 예시값만 포함 (`ws://123.45.67.89:7891`, `토큰문자열`). 실 IP/토큰 없음 확인. | closed |
| T-04-10 | Information Disclosure | PROTOCOL.md | accept | 프로토콜 명세는 공개 정보. CR-01 버그 공개도 보안 위협 아님 — 서버 토큰 인증으로 통제. accepted risk. | closed |
| T-04-11 | Spoofing | PROTOCOL.md x-harness-token | mitigate | `PROTOCOL.md:20` 헤더 테이블에 "필수" 명시. 예제는 더미 토큰만 사용. | closed |
| T-04-12 | Elevation of Privilege | harness_server.py confirm 수정 | mitigate | `harness_server.py:782,789` — `msg.get('accept', msg.get('result', False))`. accept 필드 우선, result fallback. T-04-14의 `active_input_from` 가드로 이중 보호. | closed |
| T-04-13 | Information Disclosure | 04-PITFALLS-CHECKLIST.md | accept | planning 문서 — 실 토큰/IP 없음 확인. accepted risk. | closed |
| T-04-14 | Spoofing | confirm_write_response accept 필드 | accept | WS 연결 자체가 x-harness-token 인증. `harness_server.py:780` `active_input_from` 가드로 추가 보호. | closed |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-04-01 | T-04-02 | 통합 테스트 더미 토큰 — 실 자격증명 없음 | gsd-security-auditor | 2026-04-24 |
| AR-04-02 | T-04-05 | 공식 Actions SHA 미고정 — 이 규모에서 overhead 대비 효익 낮음 | gsd-security-auditor | 2026-04-24 |
| AR-04-03 | T-04-07 | 스냅샷 파일 CI 자동 실패로 tamper 방지 | gsd-security-auditor | 2026-04-24 |
| AR-04-04 | T-04-08 | ink-testing-library columns 테스트 전용 DoS 위협 — 실 영향 없음 | gsd-security-auditor | 2026-04-24 |
| AR-04-05 | T-04-10 | PROTOCOL.md 공개 명세 — 보안 위협 해당 없음 | gsd-security-auditor | 2026-04-24 |
| AR-04-06 | T-04-13 | PITFALLS 체크리스트 planning 문서 — 민감 정보 없음 | gsd-security-auditor | 2026-04-24 |
| AR-04-07 | T-04-14 | confirm 응답 스푸핑 — WS 인증 + active_input_from 가드로 이중 방어 | gsd-security-auditor | 2026-04-24 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-24 | 14 | 14 | 0 | gsd-security-auditor (agent a6e17c394d718ae3a) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-24
