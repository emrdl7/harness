# harness — Requirements (v1.1)

> v1.0 의 85 REQ-ID 는 archive ([`milestones/v1.0-REQUIREMENTS.md`](milestones/v1.0-REQUIREMENTS.md)).
> 본 문서는 v1.1 (Client-side Tool Execution) 의 신규 REQ-ID 만 정의.

## v1.1 REQ-ID 목록

### RPC — Client-side Tool RPC

| ID | Phase | Description | DoD |
|---|---|---|---|
| RPC-01 | 1 | WS 프로토콜에 `tool_request` / `tool_result` 메시지 타입 정의. `call_id` 기반 correlation. 오류 시 `ok=false` + `error: {kind, message}` | `protocol.ts` 에 두 타입 추가, `harness_server.py` 에 `pending_calls: dict[str, asyncio.Future]` 도입, ui-ink `dispatch.ts` 에 `tool_request` 수신 핸들러 |
| RPC-02 | 1 | `agent.py` 의 도구 dispatch 분기 — `CLIENT_SIDE_TOOLS = {...}` 에 든 도구는 `await rpc_call(name, args)` (서버 측 직접 실행 안 함) | Phase 1 시작 시 `{'read_file'}` 만, Phase 2/3 진행하며 확장. 서버 측 잔존 도구 (web/claude_cli/improve) 는 그대로 dispatch |
| RPC-03 | 1~3 | ui-ink 측 tool runtime — `ui-ink/src/tools/{registry,fs,shell,git}.ts`. 각 함수는 (args) → result 비동기. registry 가 name 으로 lookup | Phase 1: registry + fs.read_file. Phase 2: fs 전체. Phase 3: shell + git |
| RPC-04 | 2 | Confirm 플로우 클라 측 통합 — write_file/edit_file/run_command 시 ConfirmDialog 띄움 → 사용자 응답 → 클라 도구 실행. 서버는 confirm 묻지 않음 (`tool_request` 만 보냄) | Phase 2 (fs) + Phase 3 (shell) 에서 자체 confirm. broadcast 없음 (1인 가정) |
| RPC-05 | 1~3 | pytest fs/shell/git 케이스를 vitest 동등 변환 (~70건 추정) | Phase 별 분할: fs ~30, shell ~25, git ~15. 각 phase 에서 deletion 직전 vitest green |
| RPC-06 | 3 | 타임아웃 + disconnect 처리 — per-call 30s 기본 (run_command 별도), ws disconnect 시 `pending_calls` 일괄 cancel + `RpcAbortedError` 전파 → agent 컨텍스트에 `tool_error: connection lost` 삽입 | 서버 측 통합 테스트 + 수동 검증 (Phase 3 검증 시 disconnect 시뮬) |

### BBR — BB-2 deletion

| ID | Phase | Description | DoD |
|---|---|---|---|
| BBR-01 | 4 | BB-2 코드 일괄 deletion. server: Room/ROOMS/broadcast/broadcast_state/active_input_from/room_joined/room_busy/room_member_*/state_snapshot/`/who`. client: PresenceSegment/ReconnectOverlay/ObserverOverlay/store/room.ts/protocol.ts room_*/--room/HARNESS_ROOM. test: 관련 pytest ~30 + vitest room 관련. doc: BB-2-DESIGN.md → archive | grep `Room\|active_input_from\|room_joined\|HARNESS_ROOM` 결과 0 (테스트 + archive 디렉토리 제외). 1 ws ↔ 1 session 단순 구조 |

### SES — 세션 위치 이전

| ID | Phase | Description | DoD |
|---|---|---|---|
| SES-01 | 4 | RX-02 세션 저장 위치 = 서버 측 → 클라 측 `./.harness/sessions/`. 서버는 세션 메타 안 들고 있음 (1 ws ↔ 1 in-memory state 만) | 서버 재시작 시 세션 자동 복원 동작은 클라 측에서. 기존 서버 측 `~/.harness/sessions/` 코드 deletion |

### MCP — MCP 클라 이전

| ID | Phase | Description | DoD |
|---|---|---|---|
| MCP-01 | 5 | `tools/mcp.py` 의 MCP 서버 통신을 ui-ink 측으로 이전. 정의 파일 `~/.harness/mcp.json` 위치 = 클라. transport 는 기존 그대로 (stdio + JSON-RPC) | MCP 서버 호출 시 클라 PC 의 MCP 데몬에 연결. 서버 측 `tools/mcp.py` deletion |

### DOC — 문서 갱신

| ID | Phase | Description | DoD |
|---|---|---|---|
| DOC-01 | 5 | `docs/PROTOCOL.md` (RPC 추가, room_* 제거), `docs/CLIENT_SETUP.md` (--room 제거, 1인 1세션 명시), `RELEASE_NOTES.md` (v1.1 변경 요약) | 문서와 실제 protocol.ts 가 일치. CLIENT_SETUP.md 의 환경변수 표에서 HARNESS_ROOM 제거 |

---

## Traceability (Phase ↔ REQ)

| Phase | REQ |
|---|---|
| 1. RPC 골격 + read_file PoC | RPC-01, RPC-02, RPC-03 (read_file), RPC-05 (read_file) |
| 2. fs 전체 클라 이전 | RPC-03 (fs), RPC-04 (fs), RPC-05 (fs ~30건) |
| 3. shell + git 클라 이전 | RPC-03 (shell, git), RPC-04 (shell), RPC-05 (shell+git ~40건), RPC-06 |
| 4. BB-2 deletion + 세션 이전 | BBR-01, SES-01 |
| 5. MCP 이전 + cleanup | MCP-01, DOC-01 |

## Out of Scope (v1.1)

- PTY 기반 shell — simple spawn 으로 시작. PTY 는 v1.2+ 후보
- search_web/fetch_page 클라 이전 — 외부망 일관성으로 서버 유지
- claude_cli, improve, hooks 클라 이전 — API 키/자기수정/서버 자산 일관성으로 서버 유지
- Anthropic API 직접 호출
- 바이너리 배포 / 자동 업데이트
- 백엔드 언어 교체 (Python → TS 등)

---

*Created: 2026-04-27 — v1.1 milestone REQ definition*
