# Enhancement Opportunities — harness

**Analysis Date:** 2026-04-22
**Scope:** Forward-looking improvements grounded in actual code observation. Bugs/security issues are in `CONCERNS.md`; this document is about direction.
**Deployment target:** 집 머신 상시 서버 + 외부 사용자 2명 원격 접속

---

## Top 5 High-ROI Enhancements

1. **E-TOP-1: HarnessCore 공통 모듈 추출** (effort: L) — `main.py`, `harness_server.py`, `harness_app.py` 3곳이 슬래시 커맨드·에이전트 루프·confirm 콜백을 각자 구현 중. 이미 `confirm_write` 시그니처 drift 발생. 순수 코어 클래스 1개 + 프런트엔드 어댑터 3개 구조로 정리하면 버그 1번 수정 → 3곳 전파, 신규 커맨드 추가도 1곳에서 끝남. **고도화의 모든 전제가 되는 리팩터링.**

2. **E-TOP-2: 원격 사용자 프레즌스 & 활동 피드** (effort: M) — `harness_server.py`는 연결당 `Session` 인스턴스를 갖지만 **다른 연결이 있다는 걸 전혀 모름**. 두 사용자가 동시에 작업할 때 "A가 지금 뭐 하는 중"이 안 보임. 서버에 `connected_sessions: set[Session]` 추가하고 JSON 이벤트로 브로드캐스트만 해도 협업 경험이 질적으로 달라짐.

3. **E-TOP-3: 에이전트 루프 retry/backoff + 중간 실패 시각화** (effort: S) — `agent.py:57-71` `_stream_response`에 retry가 전혀 없음. Ollama가 503 한 번 뱉으면 전체 요청 실패. 3-retry + 지수 백오프 + UI에 "재시도 1/3" 표시하면 로컬 Ollama 불안정성을 크게 완화. 각 사용자 경험의 체감 차이 큼.

4. **E-TOP-4: idle_runner를 opt-in + git 커밋 강제** (effort: S) — `evolution/idle_runner.py`는 기본 활성 + `confirm_write=lambda p: True` 무인 승인. 집 머신에 배포하면 **원격 사용자가 접속 중일 때도 AFK 판정되면 코드가 혼자 바뀜.** 프로필 기본값을 `auto_evolve = false`로 바꾸고, 실행 시 반드시 `git commit` 남기도록 강제. 롤백 경로 없이 쓸 기능이 아님.

5. **E-TOP-5: 세션 "분기(branch)" 기능** (effort: M) — 현재 `session/store.py`는 단일 linear 세션만 지원. 긴 작업 중 "이 시점에서 다른 접근 시도해보고 싶다" 할 때 현재는 `/save`→`/resume`으로 우회해야 함. 세션에 `parent_id` 추가하고 `/branch <name>`만 있어도 실험적 시도를 안전하게 할 수 있음. Ollama 맥락 한계 때문에 이런 탐색이 더 자주 필요해짐.

---

## Axis 1: Agent Loop Quality

### E-1.1: 스트리밍 재시도 로직 (effort: S)
- **Location:** `agent.py:57-71` `_stream_response`
- **Current:** `requests.post(..., timeout=300)` 한 번 호출 + `raise_for_status()`. 실패 시 즉시 예외.
- **Proposed:** 지수 백오프 재시도 (3회, 1s→2s→4s). 재시도 사유는 `on_token`으로 UI에 표시.
- **Why:** Ollama는 로컬이어도 모델 로딩 타이밍에 503을 뱉고, 원격 서버면 네트워크 flakiness까지 겹침. 현재는 긴 대화 한 줄 실패로 전체 세션 신뢰도가 내려감.

### E-1.2: tool_result 크기 제한 및 요약 (effort: S)
- **Location:** `agent.py:13` `MAX_TOOL_RESULT_CHARS = 20_000`
- **Current:** 단순 truncate. `read_file`로 큰 파일 읽으면 20k에서 잘려 나머지는 유실.
- **Proposed:** truncate 시 "... [N chars truncated, call read_file with offset=N to continue]" 힌트 자동 주입. 또는 `read_file`에 자동 pagination.
- **Why:** 현재 에이전트는 잘린 뒷부분이 있는지도 모르고 답변함. 힌트 한 줄로 "더 읽을까?" 판단이 가능해짐.

### E-1.3: 실패 reflection 후 "같은 접근 재시도 금지" 힌트 (effort: S)
- **Location:** `agent.py:46` `_REFLECTION_PREFIX` + `tools.hooks.run_hook`
- **Current:** "다른 접근 방법으로 재시도하라"고 프롬프트하지만 모델이 종종 같은 툴·같은 인자로 재호출.
- **Proposed:** 실패한 `(tool, args)` 튜플을 이번 이터레이션에서 1회 금지하는 가드. 또는 reflection 프롬프트에 "이전 시도: `{tool}({args})`, 이 조합 재호출 금지" 명시.
- **Why:** Ollama 모델이 Claude보다 self-correction 약함. 구조적 가드가 가치 큼.

### E-1.4: 시스템 프롬프트 모듈화 (effort: S)
- **Location:** `agent.py:15-44` `SYSTEM_PROMPT`
- **Current:** 하드코딩된 긴 한국어 프롬프트. 프로젝트별로 커스터마이즈 어려움.
- **Proposed:** `HARNESS.md`의 "시스템 프롬프트 보강" 섹션을 `SYSTEM_PROMPT`에 자동 합성하는 로직은 있는 듯하나 확인 필요. 없으면 추가. `.harness.toml`에 `system_prompt_extra` 키 도입.
- **Why:** 프로젝트 도메인 컨텍스트 주입이 쉬워짐. CLAUDE.md 대응 기능.

### E-1.5: 컨텍스트 윈도우 사용률 표시 (effort: S)
- **Location:** `main.py:1403` `_ctx_status`
- **Current:** 이미 `ctx: 8k/32k` 형식으로 표시 중 (기존 메모리에 기록됨). 컴팩션 타이밍 판단용.
- **Proposed:** 임계치 (예: 80%) 넘으면 프롬프트에 경고 색상, 90%면 자동 compact 제안.
- **Why:** 현재는 수치가 있어도 "언제 compact 할지" 판단이 사용자 몫. 자동 넛지 한 줄이 UX 개선.

### E-1.6: ask_claude 위임 결과 캐싱 (effort: M)
- **Location:** `tools/claude_cli.py`, `SYSTEM_PROMPT`의 "Claude 위임 규칙"
- **Current:** `ask_claude` 호출 시 매번 `claude --print` 새로 띄움. 같은 질문 반복 호출 비용 큼.
- **Proposed:** 최근 N개 쿼리→응답을 `~/.harness/claude_cache/` 해시 기반 캐싱 (TTL 24h).
- **Why:** Claude CLI 호출은 latency + 비용 모두 비쌈. 리팩터링 루프에서 같은 코드블록 여러 번 물어보는 패턴 흔함.

---

## Axis 2: Remote Collaboration UX

### E-2.1: 연결된 사용자 목록 + 프레즌스 (effort: S)
- **Location:** `harness_server.py` `Session` 클래스 + `handler`
- **Current:** 연결당 독립 Session. 다른 연결의 존재를 모름.
- **Proposed:** 서버 레벨 `connected_sessions: dict[token → Session]`, `/who` 슬래시 커맨드로 "지금 접속 중인 사용자 목록" 표시.
- **Why:** "지금 다른 사람 쓰고 있나?"가 기본 궁금증. 집에서 혼자 쓸 때는 무시하면 되고, 2명일 때 큰 가치.

### E-2.2: Ollama 큐 대기 시각화 (effort: S)
- **Location:** `harness_server.py:26` `_ollama_lock = asyncio.Semaphore(1)` + `run_agent`
- **Current:** 다른 사용자가 생성 중이면 내 요청은 조용히 대기. 몇 초 걸릴지 모름.
- **Proposed:** Semaphore 획득 전에 `send(ws, type='queue', position=N)` 이벤트. 클라이언트에 "대기 중 (앞 1명)" 표시.
- **Why:** 무응답과 대기는 UX적으로 완전히 다른 경험. 2-user 시나리오에서 자주 발생.

### E-2.3: 공유 활동 피드 (effort: M)
- **Location:** 신규 — `harness_server.py` + `ui/index.js`
- **Current:** 각 연결은 서로 격리됨. 같은 레포에서 작업 중이어도 서로의 변경을 모름.
- **Proposed:** `write_file`, `run_command`(mutating), `git_commit` 같은 부작용 이벤트를 다른 연결로 브로드캐스트. 각자 터미널 하단에 "Bob이 main.py 수정함" 타이머 3초 노출.
- **Why:** 한 머신 공유 시 서로의 작업이 "보이지 않는 손"이 되어버림. Google Docs 수준의 완벽한 동기화가 아니어도 알림만으로 충돌 크게 줄어듦.

### E-2.4: working_dir 충돌 경고 (effort: S)
- **Location:** `harness_server.py:42` `self.working_dir = os.environ.get('HARNESS_CWD') or os.getcwd()`
- **Current:** 여러 세션이 같은 dir에서 작업해도 경고 없음.
- **Proposed:** 서버에서 `{dir → sessions}` 맵 유지. 같은 dir 진입 시 "B님도 지금 이 디렉토리 작업 중" 알림.
- **Why:** git 충돌 발생 전 예방이 핵심. E-2.3의 최소 버전으로도 대부분의 상황 커버.

### E-2.5: 세션 핸드오프 (effort: M)
- **Location:** 신규 `session/store.py` 확장
- **Current:** A가 저장한 세션을 B가 `/resume`으로 이어받을 수 없음 (토큰별 저장 경로 분리 시).
- **Proposed:** `/handoff <user>` 커맨드 — 세션 스냅샷을 지정 사용자 메일박스에 전달, 받는 쪽은 `/inbox`로 수령.
- **Why:** "여기까지 했으니 이어서 해줘" 패턴이 원격 협업의 핵심 유스케이스.

### E-2.6: 토큰별 권한 프로필 (effort: M)
- **Location:** `harness_server.py:24` `VALID_TOKENS = set(...)`
- **Current:** 토큰이 있거나 없거나. 권한 차등 없음. 모두 풀 권한.
- **Proposed:** `HARNESS_TOKENS="alice:full,bob:readonly"` 형식. `readonly`는 `write_file`/`run_command` 차단.
- **Why:** 실험하고 싶은 친구를 초대하되 내 집 머신에 파일 못 쓰게. 배포 안전성 크게 향상.

---

## Axis 3: Slash Command UX

**현재 커맨드 (main.py:974-1300):** `/clear /undo /plan /cplan /compact /cloop /index /improve /learn /evolve /history /restore /cd /commit /push /pull /files /save /resume /sessions /init /claude /mode /help`

### E-3.1: 커맨드 자동완성 강화 (effort: S)
- **Location:** `main.py:144-161` `SlashCompleter`
- **Current:** 이미 커스텀 Completer 있음. 커맨드 이름만 제안 중일 듯.
- **Proposed:** 인자도 제안 — `/cd <탭>` → 하위 디렉토리 목록, `/restore <탭>` → backup 파일 목록, `/sessions` → 최근 세션 이름.
- **Why:** 기억해야 할 것이 줄어듦. 특히 `/restore`의 timestamp 입력이 현재 불편.

### E-3.2: `/diff <file>` 커맨드 (effort: S)
- **Location:** 신규
- **Current:** git diff는 자연어로 가능하지만 특정 파일 diff를 에이전트 호출 없이 즉시 보고 싶을 때 경로 없음.
- **Proposed:** `/diff <file>` — `git diff <file>` 결과를 syntax highlighting 해서 렌더. `/diff`(인자 없음) = HEAD 전체.
- **Why:** 에이전트가 수정한 결과를 빠르게 검토하는 닫힌 루프. `confirm_write` UI 개선의 연장선.

### E-3.3: `/retry` — 마지막 유저 입력 재실행 (effort: S)
- **Location:** 신규
- **Current:** 실패하거나 불만족인 응답 후, 같은 질문을 다시 치려면 복붙 필요.
- **Proposed:** `/retry` = 마지막 user 메시지를 다시 agent에 보냄 (이전 assistant 턴은 세션에서 제거).
- **Why:** Ollama 답변 품질이 확률적임. 한 번 더 돌리기 비용이 낮아야 함.

### E-3.4: `/cost` — 세션 누적 토큰/시간 (effort: S)
- **Location:** 신규 — `session/analyzer.py` 확장
- **Current:** 세션이 얼마나 길어졌는지 직관적 피드백 없음. `_ctx_status`가 근사치지만 시간 아님.
- **Proposed:** `/cost` — 세션 내 tokens in/out, 벽시계 시간, 툴 호출 수, 실패율 요약.
- **Why:** 로컬 Ollama지만 시간 = 비용. 세션이 너무 길어졌는지 판단 가능.

### E-3.5: `/skills` 관리 (effort: S)
- **Location:** `skills/*.md` (현재 3개: korean-public-site, scss-bem, vue-accessibility)
- **Current:** Skill은 파일로 존재하지만 관리 UI 없음. 어떤 스킬이 로드됐는지 확인 불가.
- **Proposed:** `/skills list|on <name>|off <name>|reload`. 현재 활성 스킬이 시스템 프롬프트에 반영되는지 확인.
- **Why:** Skills 시스템이 최근 추가(`ee96445`)됐지만 observability가 부족.

### E-3.6: 커맨드 체이닝 (effort: M)
- **Location:** 신규 — `main.py handle_slash` 분기 앞단
- **Current:** `/commit && /push` 같은 체이닝은 자연어 "커밋하고 푸시"로만 가능. 슬래시는 단발.
- **Proposed:** `/commit ; /push` 또는 `/commit && /push` 파싱. 실패 시 단락 평가.
- **Why:** 파워유저가 반복 워크플로우를 1줄로 수행. 자연어 intent 매칭의 fragility(§1.4 CONCERNS) 회피.

---

## Axis 4: Evolution Engine Trust

### E-4.1: auto_evolve 기본값 false + 명시적 activate (effort: S)
- **Location:** `evolution/idle_runner.py` + `profile.py`
- **Current:** `auto_evolve = true` 프로필이면 유휴 5분 후 자동 실행. 집 머신에 올리면 원격 사용자 접속 중에도 트리거됨.
- **Proposed:** 기본 `false`. `/evolve on` 명시 후에만 활성. 원격 연결이 있을 때는 자동 skip.
- **Why:** "혼자 진화"는 멋진 데모지만 production 환경에서 예측 불가능성이 비용. 배포 시나리오에서 필수 가드.

### E-4.2: 모든 자가수정을 git 커밋으로 (effort: S)
- **Location:** `evolution/executor.py`
- **Current:** `backup_sources()` → 구현 → `validate_python()` → 적용. 백업은 `.harness_bak/`로.
- **Proposed:** 변경 후 `git add -A && git commit -m "evolution: <proposal title>"` 자동. 커밋 못하면 (dirty tree) 실행 거부.
- **Why:** 롤백 UX가 timestamp 입력(`/restore`)보다 `git revert HEAD`가 훨씬 직관적. 커밋 이력이 곧 진화 로그.

### E-4.3: 제안 예고 알림 (effort: S)
- **Location:** `evolution/proposer.py`, `engine.py`
- **Current:** 유휴 상태에서 제안 → 실행. 사용자는 깨어나서 결과만 확인.
- **Proposed:** 제안 생성 직후 notification (macOS `osascript` 또는 단순 `~/.harness/evolution/pending_notice.md` 파일) — "다음 진화 예정: <title>. 반대면 `/evolve cancel`".
- **Why:** 사용자 동의 없이 코드가 바뀌는 것과, 변경 전 예고 후 바뀌는 것은 신뢰도 차이 큼.

### E-4.4: 진화 점수 쇼케이스 (effort: S)
- **Location:** `evolution/scorer.py` (27줄 — 간단함)
- **Current:** 점수는 있는데 사용자에게 거의 안 보임.
- **Proposed:** `/evolve history`에 점수 열 추가 + 점수 낮은 제안 자동 dismiss.
- **Why:** 쓰레기 제안이 쌓이면 시스템 신뢰도 하락. 자동 필터링 필수.

### E-4.5: Dry-run 모드 (effort: S)
- **Location:** `evolution/executor.py`
- **Current:** 실제 파일 변경만 지원.
- **Proposed:** `/evolve dry-run` — 제안을 실행하되 diff만 생성하고 적용은 안 함. 사용자가 검토 후 `/evolve apply <id>`.
- **Why:** "이걸 하면 뭐가 바뀔까"를 먼저 볼 수 있는 경로. 신뢰 구축의 핵심.

---

## Axis 5: Developer Experience (DX)

### E-5.1: `.venv/bin/python` 하드코딩 → `python3` 심볼릭 (effort: S)
- **Location:** `run.sh`, `CLIENT_SETUP.md`, 관련 docs
- **Current:** `run.sh`가 `.venv/bin/python main.py` 직접 참조. venv 경로 달라지면 터짐. Python 3.14 (프리릴리스) 의존.
- **Proposed:** `run.sh` 상단에 activate 체크 + 버전 검증 + 친절한 에러. `pyproject.toml` + `uv` 도입 고려.
- **Why:** 새 기여자가 첫 5분 안에 막히는 대표적 지점.

### E-5.2: 구조화 로그 + 로그 뷰어 (effort: M)
- **Location:** `session/logger.py` (60줄), `~/.harness/logs/YYYYMMDD.jsonl`
- **Current:** JSONL 로그는 있음. 읽으려면 `jq` 수동.
- **Proposed:** `/logs [today|N|error]` 슬래시 — 포맷된 최근 로그 TUI. 필터링·검색.
- **Why:** "방금 뭐 실패했지?"를 즉시 볼 수 있으면 디버깅 속도 크게 향상.

### E-5.3: 에이전트 thought → UI 표시 (effort: S)
- **Location:** `agent.py` `_stream_response`, `main.py on_token`
- **Current:** 토큰은 스트리밍되지만 "지금 무엇을 하려는가"의 내부 추론은 숨겨짐.
- **Proposed:** 에이전트가 tool_call 하기 전 "왜 이 툴을 부르려는지"를 prefix 1줄로 내도록 시스템 프롬프트에 추가. UI에 흐린 색으로 표시.
- **Why:** 블랙박스감이 큼. Cursor/Claude Code의 thinking 구간이 주는 안도감.

### E-5.4: `pyproject.toml` + 테스트 스캐폴드 (effort: M)
- **Location:** 신규 — 루트
- **Current:** `pyproject.toml` 없음, 테스트 0개. Python 3.14 (프리릴리스) venv 전제.
- **Proposed:** `pyproject.toml` + `pytest` + `tests/` 디렉토리 + `tools/shell.py::classify_command`, `agent.py::_parse_text_tool_calls` 같은 순수 함수부터 테스트. pre-commit 훅.
- **Why:** 리팩터링 신뢰도 전제. `HarnessCore` 추출(E-TOP-1) 하기 전에 이거 먼저.

### E-5.5: 개발자 대시보드 (effort: M)
- **Location:** 신규 — `/dashboard` 커맨드 또는 별도 HTML
- **Current:** 툴 성공률, 자주 쓰는 커맨드, 평균 응답 시간 같은 메타데이터가 있지만 흩어져 있음 (evolution/tracker.py에 일부).
- **Proposed:** `/dashboard` — 터미널 표 또는 `~/.harness/dashboard.html` 열기. Tool stats, session stats, evolution history 한 화면.
- **Why:** 진화 엔진이 "쓸만한지" 판단하는 근거 데이터를 쉽게 볼 수 있어야 함.

---

## Quick Wins (< 1 day each)

- **QW-1:** `/retry` 커맨드 추가 (E-3.3). ~30분
- **QW-2:** `_stream_response`에 retry 3회 + backoff (E-TOP-3). ~1시간
- **QW-3:** tool result truncate 시 힌트 주입 (E-1.2). ~30분
- **QW-4:** Ollama 대기 중 큐 position 브로드캐스트 (E-2.2). ~1시간
- **QW-5:** `auto_evolve` 기본값 `false`로 변경 (E-4.1). ~10분
- **QW-6:** `/evolve history`에 점수 열 추가 (E-4.4). ~30분
- **QW-7:** 슬래시 인자 자동완성 (경로, 세션명) (E-3.1). ~2시간
- **QW-8:** `/diff [file]` 커맨드 (E-3.2). ~2시간

---

## Bold Bets (ambitious redesigns)

### BB-1: HarnessCore — 공통 코어 + 어댑터 패턴 재설계
`main.py`(CLI), `harness_server.py`(WS), `harness_app.py`(Textual) 3 구현이 slash command / agent loop / confirm callbacks를 각자 들고 있음. **순수 `HarnessCore(session_id, profile)` 클래스**로 추출하고 프런트엔드는 IO 어댑터만. 코어는 asyncio 기반, 콜백은 abstract method. 신규 커맨드 추가 → 한 곳. 버그 수정 → 한 번에 전파. 테스트 가능한 단위로 쪼개짐. 2-4주 프로젝트지만 이거 없이는 나머지 축 다 뻗기 힘듦.

### BB-2: 원격 페어 프로그래밍 — 공유 세션 모드
현재는 사용자당 독립 세션. **"페어 모드"**를 도입: 두 사용자가 하나의 세션을 공유하고 둘 다 입력 가능, agent 출력은 둘 다 봄. 터미널에서의 CRDT(Yjs 수준 아니라 단순 turn-taking) — 입력은 서버에서 시리얼라이즈, 출력은 브로드캐스트. "지금 너가 쳐" 같은 명시 제어. Cursor는 못 하는 영역. 집 머신 + 2명 시나리오에 정확히 맞음.

### BB-3: 진화 엔진 → 학습 가능한 에이전트
현재 `evolution/`은 "패턴 감지 → 코드 수정". 다음 단계: **툴 성공/실패 패턴을 시스템 프롬프트에 자동 보강.** 예: `read_file` 호출 시 `offset` 빠뜨려 반복 실패 → 프롬프트에 "큰 파일은 offset 사용" 추가. 메타 학습 루프. 위험하기에 `HARNESS.md`에 명시적 diff로만 반영, 사용자 승인 필수. 구현은 제안 생성 파이프라인에 한 스텝 추가하는 정도지만 효과 누적적.

---

## 다음 액션 제안

1. **QW-5 즉시 적용** (`auto_evolve` 기본값 false) — 배포 안전성 대비, 10분
2. **QW-2 + E-1.2 구현** — 에이전트 체감 신뢰도 즉시 상승
3. **E-TOP-1 (HarnessCore) 설계 단계 착수** — 이후 모든 고도화의 전제. `pyproject.toml` + 핵심 순수 함수 테스트(E-5.4)로 시작
4. **배포 직전 E-4.1/E-4.2 (진화 엔진 가드) 적용** — `CONCERNS.md §0 🟢` 체크리스트와 함께
