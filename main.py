#!/usr/bin/env python3
'''harness REPL 진입점 — 얇은 orchestrator.

핵심 기능은 cli.* 서브모듈로 분리됨(Phase 3.1-A ~ 3.1-F):
- cli.render     — console/THEME/spinner/슬래시 자동완성/도움말 표
- cli.setup      — 배너/환영/인덱싱/MCP 부팅/ctx 상태
- cli.callbacks  — on_token/on_tool/confirm_* + UI 상태
- cli.intent     — 자연어 → 슬래시 의도 매처
- cli.claude     — Claude CLI 호출/루프 + 메시지 변환
- cli.slash      — /cmd 디스패처 (harness_core로 위임 + 직접 처리 혼합)

main() 은 argparse → profile 로드 → 부팅 → REPL 루프만 담당한다.
tests/test_handle_slash.py + tests/test_main_intent.py 호환을 위해 해당
심볼들은 main.* 네임스페이스에 re-export 유지.
'''
import sys
import os
import argparse
import re as _re

from rich.prompt import Confirm
from rich.syntax import Syntax

import agent
import config
import profile as prof
import session as sess
from session.compactor import needs_compaction, compact
from tools import register_mcp_tools
import evolution
from tools.claude_cli import ask as claude_ask, is_available as claude_available

# ── 렌더 핵심 — cli.render로 분리 (Phase 3.1-B) ──────────────────
# console + THEME + 툴 메타 / 추정 / spinner / _short_dir 통합 이전.
# main.* 호환 위해 re-export.
from cli.render import (
    THEME,
    console,
    _TOOL_META,
    _tool_meta_for,
    _tool_result_hint,
    _infer_tool_purpose,
    SLASH_COMMANDS,
    PT_STYLE,
    SlashCompleter,
    _short_dir,
    _Spinner,
    _SPINNER_FRAMES,
)

# ── 부팅/세팅 헬퍼 — cli.setup으로 분리 (Phase 3.1-E) ────────────
# main.* 호환 re-export (tests/test_handle_slash.py는 main.get_context_snippets를 monkeypatch).
from cli.setup import (
    slash_completer,
    get_input,
)

# ── UI 콜백 + 상태 — cli.callbacks로 분리 (Phase 3.1-F-1) ────────
# main.* 호환 re-export.
from cli.callbacks import (
    _spinner,
    _token_buf,
    _flush_tokens,
    _UIState,
    _ui,
    on_token,
    on_tool,
    on_thought,
    on_thought_end,
    confirm_write,
    confirm_bash,
    _INSTALLABLE_TOOLS,
    _suggest_unknown_tools,
    _ctx_display,
    _response_header,
    _response_footer,
)


# ── 인덱싱 / 배너 / 환영 — cli.setup으로 분리 (Phase 3.1-E) ──────
# main.* 호환 re-export. 새 코드는 cli.setup에서 직접 import 권장.
from cli.setup import (  # noqa: E402
    do_index,
    get_context_snippets,
    _auto_sync,
    print_banner,
    print_welcome,
)


# ── 자연어 의도 매처 — cli.intent로 분리 (Phase 3.1-A) ───────────
# main.* 호환 위해 re-export. 새 코드는 `from cli.intent import ...` 직접 사용 권장.
from cli.intent import (
    _COMMIT_TRIGGERS,
    _PUSH_TRIGGERS,
    _PULL_TRIGGERS,
    _CPLAN_TRIGGERS,
    _is_push_intent,
    _is_commit_intent,
    _is_pull_intent,
    _extract_commit_msg,
    _is_cplan_intent,
    _extract_cplan_task,
)


# ── Claude CLI — pure 헬퍼(3.1-D) + REPL 호출/루프(3.1-F-2) ─────
# main.* 호환 re-export. 새 코드는 `from cli.claude import ...` 직접 사용 권장.
from cli.claude import (
    _CLAUDE_CTX_HEAD,
    _CLAUDE_CTX_TAIL,
    _truncate_for_claude,
    _build_claude_context,
    _summarize_session_for_claude,
    _run_claude_cli,
    _CLOOP_PLAN_TMPL,
    _CLOOP_REVIEW_TMPL,
    _CLOOP_MAX_ROUNDS,
    do_claude_loop,
)


# ── 슬래시 핸들러 — cli.slash로 분리 (Phase 3.1-F-3) ─────────────
# tests/test_handle_slash.py 가 main.handle_slash 를 호출하므로 re-export 유지.
from cli.slash import (  # noqa: E402
    _CORE_DELEGATED_SLASHES,
    handle_slash,
)
from cli.render import (  # noqa: E402,F401  Phase 3.1-C 재내보내기
    _render_core_notice,
    _render_sessions_table,
    _render_files_tree,
)


# ── /files 트리 + /help — cli.render로 분리 (Phase 3.1-C) ────────
from cli.render import _DIR_ICON, _FILE_ICONS, _print_help  # noqa: E402,F401


# ── 메인 ──────────────────────────────────────────────────────────
# MCP 부팅 / ctx 상태 문자열 — cli.setup으로 분리 (Phase 3.1-E)
from cli.setup import _start_mcp_servers, _ctx_status  # noqa: E402,F401


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-p', '--print', dest='one_shot', metavar='QUERY', default=None)
    parser.add_argument('--continue', dest='resume', action='store_true')
    parser.add_argument('extra', nargs='?', default=None)
    args, _ = parser.parse_known_args()

    working_dir = os.path.abspath(os.environ.get('HARNESS_CWD') or os.getcwd())
    profile = prof.load(working_dir)
    config.runtime_override(profile)
    session_msgs: list = []
    undo_count: int = 0

    # --continue: 이전 세션 복원
    _resumed_turns = 0
    if args.resume:
        data = sess.load_latest(working_dir)
        if data:
            session_msgs = data['messages']
            _resumed_turns = len([m for m in session_msgs if m['role'] == 'user'])
            working_dir = data.get('working_dir', working_dir)

    print_banner()
    print_welcome(working_dir)

    if args.resume and _resumed_turns:
        console.print(f'  [dim]이전 세션 재개 ({_resumed_turns}턴)[/dim]\n')

    # MCP 서버 초기화
    _mcp_clients: dict = {}
    if profile.get('mcp_servers'):
        _mcp_clients = _start_mcp_servers(profile)
        if _mcp_clients:
            registered = register_mcp_tools(_mcp_clients)
            if registered:
                console.print(f'  [dim]MCP 툴 등록: {len(registered)}개[/dim]\n')

    if profile.get('auto_index'):
        _auto_sync(working_dir)

    # proposer용 툴 통계 수집 래퍼 (_effective_on_tool로 분리해 스코프 충돌 방지)
    if profile.get('auto_evolve', False):
        from evolution.proposer import record_tool_call as _record_tool_call

        def _effective_on_tool(name: str, args: dict, result):
            on_tool(name, args, result)
            if result is not None:
                _tool_call_sequence.append(name)
                _record_tool_call(name, bool(result.get('ok')))
    else:
        _effective_on_tool = on_tool

    # approval_mode 기반 콜백 — config.APPROVAL_MODE를 직접 참조해 /mode 즉시 반영
    def _cw(path, content=None):
        mode = config.APPROVAL_MODE
        if mode == 'suggest':
            console.print(f'  [dim][suggest] 파일 수정 차단: {path}[/dim]')
            return False
        if mode == 'full-auto':
            return True
        return confirm_write(path, content)

    def _cb(cmd):
        mode = config.APPROVAL_MODE
        if mode == 'suggest':
            return False
        if mode == 'full-auto':
            return True
        return confirm_bash(cmd)

    # 파이프 입력
    if not sys.stdin.isatty():
        pipe_input = sys.stdin.read().strip()
        try:
            sys.stdin = open('/dev/tty')
        except Exception:
            pass
        if pipe_input:
            console.print(f'  [dim]파이프 입력 ({len(pipe_input)}자)[/dim]\n')
            snippets = get_context_snippets(pipe_input, working_dir, profile)
            _ctx_display[0] = _ctx_status(session_msgs)
            _response_header()
            _ui.reset()
            _, session_msgs = agent.run(
                pipe_input,
                session_messages=session_msgs,
                working_dir=working_dir,
                profile=profile,
                context_snippets=snippets,
                on_token=on_token,
                on_tool=_effective_on_tool,
                on_thought=on_thought,
                on_thought_end=on_thought_end,
                confirm_write=_cw if profile.get('confirm_writes', True) else None,
                confirm_bash=_cb if profile.get('confirm_bash', True) else None,
                hooks=profile.get('hooks', {}),
            )
            _response_footer()

    # 미등록 툴 + 툴 시퀀스 수집 — proposer용
    _unknown_tools: list[tuple[str, dict]] = []   # [(name, args), ...]
    _all_unknown_tools: list[str] = []             # 세션 전체 누적 (이름만)
    _tool_call_sequence: list[str] = []            # 세션 전체 툴 호출 순서

    def _on_unknown_tool(name: str, args: dict = None):
        if not any(n == name for n, _ in _unknown_tools):
            _unknown_tools.append((name, args or {}))
        if name not in _all_unknown_tools:
            _all_unknown_tools.append(name)

    def _run_agent(user_input, *, plan_mode=False, context_snippets=''):
        nonlocal session_msgs
        _unknown_tools.clear()
        _token_buf.clear()
        _ctx_display[0] = _ctx_status(session_msgs)
        _spinner.start()

        if needs_compaction(session_msgs):
            console.print('  [dim]세션 압축 중...[/dim]')
            new_msgs, dropped = compact(session_msgs)
            session_msgs = new_msgs
            console.print(f'  [dim]압축 완료 (메시지 {dropped}개 요약)[/dim]')

        _, session_msgs = agent.run(
            user_input,
            session_messages=session_msgs,
            working_dir=working_dir,
            profile=profile,
            context_snippets=context_snippets,
            plan_mode=plan_mode,
            on_token=on_token,
            on_tool=_effective_on_tool,
            on_thought=on_thought,
            on_thought_end=on_thought_end,
            confirm_write=_cw if profile.get('confirm_writes', True) else None,
            confirm_bash=_cb if profile.get('confirm_bash', True) else None,
            hooks=profile.get('hooks', {}),
            on_unknown_tool=_on_unknown_tool,
        )
        _flush_tokens()
        _suggest_unknown_tools(_unknown_tools)

    def _run_agent_for_core(user_input, *, plan_mode=False, context_snippets=''):
        '''harness_core.dispatch가 호출하는 wrapping — header/footer 포함.'''
        _response_header()
        _ui.reset()
        _run_agent(user_input, plan_mode=plan_mode, context_snippets=context_snippets)
        _response_footer()

    def _run_agent_ephemeral(user_input, *, system_prompt, working_dir, profile):
        '''/improve, /learn용 — 메인 세션과 분리된 임시 세션으로 agent 실행.'''
        session = [{'role': 'system', 'content': system_prompt}]
        _token_buf.clear()
        _unknown_tools.clear()
        _response_header()
        _ui.reset()
        _spinner.start()
        agent.run(
            user_input,
            session_messages=session,
            working_dir=working_dir,
            profile=profile,
            on_token=on_token,
            on_tool=_effective_on_tool,
            on_thought=on_thought,
            on_thought_end=on_thought_end,
            confirm_write=_cw if profile.get('confirm_writes', True) else None,
            confirm_bash=_cb if profile.get('confirm_bash', True) else None,
            hooks=profile.get('hooks', {}),
        )
        _flush_tokens()
        _response_footer()

    def _ask_claude_for_core(prompt):
        '''/cplan phase 1 — claude_cli로 플랜 스트리밍 수집.'''
        collected = []
        console.print('\n[bold blue]● Claude[/bold blue] [dim]플랜 작성 중...[/dim]')

        def _tok(line):
            collected.append(line)
            console.print(line, end='', highlight=False, markup=False)
        try:
            claude_ask(prompt, on_token=_tok)
        except (RuntimeError, KeyboardInterrupt) as e:
            console.print(f'\n  [tool.fail]✗[/tool.fail] {e}')
            return ''
        console.print('\n')
        return ''.join(collected).strip()

    def _confirm_execute_for_core(plan_text, task):
        '''/cplan phase 2 — 사용자 확인. 기본은 실행(True).'''
        console.print()
        return Confirm.ask('  위 플랜으로 [bold]로컬 모델이 실행[/bold]할까요?', default=True)

    # -p / --print one-shot 모드
    if args.one_shot:
        query = args.one_shot
        # --continue + -p 조합: 이전 세션에서 추가 질문
        snippets = get_context_snippets(query, working_dir, profile)
        _response_header()
        _ui.reset()
        _run_agent(query, context_snippets=snippets)
        _response_footer()
        for client in _mcp_clients.values():
            client.stop()
        return

    while True:
        try:
            turns = len([m for m in session_msgs if m['role'] == 'user'])
            user_input = get_input(turns, working_dir, session_msgs=session_msgs).strip()

            if not user_input:
                continue

            # @claude 프리픽스 — Claude CLI 질문 (세션에 기록)
            if user_input.startswith('@claude '):
                _run_claude_cli(user_input[8:].strip(), session_msgs=session_msgs, working_dir=working_dir, model=profile.get('claude_model') or None)
                continue

            if user_input.startswith('/'):
                if user_input in ('/quit', '/exit', '/q'):
                    evolution.run(
                        session_msgs=session_msgs,
                        working_dir=working_dir,
                        profile=profile,
                        console=console,
                        agent_run=agent.run,
                        on_token=on_token,
                        on_tool=_effective_on_tool,
                        confirm_write=lambda p: True,
                        undo_count=undo_count,
                        unknown_tools=_all_unknown_tools,
                        tool_call_sequence=_tool_call_sequence,
                    )
                    if session_msgs and Confirm.ask('  세션을 저장할까요?', default=False):
                        fn = sess.save(session_msgs, working_dir)
                        console.print(f'  [dim]저장됨: {fn}[/dim]')
                    console.print('  [dim]종료[/dim]')
                    break

                # /retry — 마지막 user 메시지까지 롤백 후 재실행
                if user_input.strip() == '/retry':
                    last_user_idx = None
                    for i in range(len(session_msgs) - 1, -1, -1):
                        if session_msgs[i]['role'] == 'user':
                            last_user_idx = i
                            break
                    if last_user_idx is None:
                        console.print('  [dim]재실행할 이전 입력이 없습니다[/dim]')
                        continue
                    stored = session_msgs[last_user_idx]['content']
                    # skills.build_context 프리픽스 제거 → 원본 user 입력 복원
                    original = stored.rsplit('\n\n---\n', 1)[-1] if '\n\n---\n' in stored else stored
                    session_msgs = session_msgs[:last_user_idx]
                    preview = original[:80] + ('...' if len(original) > 80 else '')
                    console.print(f'  [dim]재실행: {preview}[/dim]')
                    snippets = get_context_snippets(original, working_dir, profile)
                    _response_header()
                    _ui.reset()
                    _run_agent(original, context_snippets=snippets)
                    _response_footer()
                    continue

                # /diff [file] — git diff 결과를 syntax highlight로 표시
                if user_input.strip() == '/diff' or user_input.startswith('/diff '):
                    parts = user_input.split(maxsplit=1)
                    file_arg = parts[1].strip() if len(parts) > 1 else ''
                    import subprocess as _subp
                    cmd = ['git', '-C', working_dir, 'diff']
                    if file_arg:
                        cmd.extend(['--', file_arg])
                    try:
                        diff_result = _subp.run(cmd, capture_output=True, text=True, timeout=10)
                    except FileNotFoundError:
                        console.print('  [tool.fail]git 명령어를 찾을 수 없습니다[/tool.fail]')
                        continue
                    except _subp.TimeoutExpired:
                        console.print('  [tool.fail]git diff 타임아웃[/tool.fail]')
                        continue
                    if diff_result.returncode != 0:
                        stderr = (diff_result.stderr or '').strip()
                        console.print(f'  [tool.fail]{stderr or "git diff 실패"}[/tool.fail]')
                        continue
                    if not diff_result.stdout.strip():
                        target = file_arg or 'HEAD'
                        console.print(f'  [dim]변경사항 없음 ({target})[/dim]')
                        continue
                    console.print(Syntax(diff_result.stdout, 'diff', theme='monokai', line_numbers=False, word_wrap=False))
                    continue

                session_msgs, working_dir, undo_count = handle_slash(
                    user_input, session_msgs, working_dir, profile, undo_count,
                    run_agent=_run_agent_for_core,
                    run_agent_ephemeral=_run_agent_ephemeral,
                    ask_claude=_ask_claude_for_core,
                    confirm_execute=_confirm_execute_for_core,
                )
                if user_input.startswith('/cd'):
                    profile = prof.load(working_dir)
                continue

            # 자연어로 /commit+push / /push / /pull 트리거 감지
            if _is_push_intent(user_input):
                msg = _extract_commit_msg(user_input)
                if msg or _is_commit_intent(user_input):
                    # "커밋/푸시" 또는 "커밋하고 푸시" → commit 후 push
                    commit_cmd = f'/commit {msg}' if msg else '/commit'
                    session_msgs, working_dir, undo_count = handle_slash(
                        commit_cmd, session_msgs, working_dir, profile, undo_count
                    )
                session_msgs, working_dir, undo_count = handle_slash(
                    '/push', session_msgs, working_dir, profile, undo_count
                )
                continue
            if _is_pull_intent(user_input):
                session_msgs, working_dir, undo_count = handle_slash(
                    '/pull', session_msgs, working_dir, profile, undo_count
                )
                continue
            if _is_commit_intent(user_input):
                msg = _extract_commit_msg(user_input)
                commit_cmd = f'/commit {msg}' if msg else '/commit'
                session_msgs, working_dir, undo_count = handle_slash(
                    commit_cmd, session_msgs, working_dir, profile, undo_count
                )
                continue

            # shell 기본 명령어 직접 처리 (cd, ls, pwd, clear)
            _stripped = user_input.strip()
            if _re.match(r'^cd(\s+\S+)?$', _stripped):
                path = _stripped[2:].strip() or '~'
                session_msgs, working_dir, undo_count = handle_slash(
                    f'/cd {path}', session_msgs, working_dir, profile, undo_count
                )
                profile = prof.load(working_dir)
                continue
            if _re.match(r'^ls(\s.*)?$', _stripped):
                import subprocess as _sp
                args = _stripped[2:].strip()
                r = _sp.run(['ls'] + (args.split() if args else ['-la']),
                            cwd=working_dir, capture_output=True, text=True)
                console.print(r.stdout if r.stdout else r.stderr, end='', highlight=False, markup=False)
                continue
            if _stripped == 'pwd':
                console.print(working_dir)
                continue
            if _stripped == 'clear':
                console.clear()
                continue

            # 자연어로 /cplan 트리거 감지 — handle_slash를 통해 harness_core로 라우팅
            if _is_cplan_intent(user_input):
                task = _extract_cplan_task(user_input)
                session_msgs, working_dir, undo_count = handle_slash(
                    f'/cplan {task}', session_msgs, working_dir, profile, undo_count,
                    run_agent=_run_agent_for_core,
                    run_agent_ephemeral=_run_agent_ephemeral,
                    ask_claude=_ask_claude_for_core,
                    confirm_execute=_confirm_execute_for_core,
                )
                continue

            snippets = get_context_snippets(user_input, working_dir, profile)
            _response_header()
            _ui.reset()
            _run_agent(user_input, context_snippets=snippets)
            _response_footer()

        except (KeyboardInterrupt, EOFError):
            console.print('\n  [dim]종료[/dim]')
            break

    for client in _mcp_clients.values():
        client.stop()


if __name__ == '__main__':
    main()
