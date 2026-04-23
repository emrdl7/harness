#!/usr/bin/env python3
import sys
import os
import time
import difflib
import argparse
import re as _re
from datetime import datetime

from rich.prompt import Confirm
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.syntax import Syntax
from rich import box

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import HTML

import agent
import config
import profile as prof
import context
import harness_core
import session as sess
from session.logger import read_recent
from session.compactor import needs_compaction, compact
from tools.improve import list_backups, restore_backup, HARNESS_DIR
from tools.mcp import StdioMCPClient
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
)


# ── 슬래시 카탈로그 + 자동완성 — cli.render로 분리 (Phase 3.1-C) ─
from cli.render import (
    SLASH_COMMANDS,
    PT_STYLE,
    SlashCompleter,
)

slash_completer = SlashCompleter()


from cli.render import _short_dir  # noqa: E402  Phase 3.1-B 분리 — 호환 re-export


def get_input(turns: int, working_dir: str) -> str:
    short = _short_dir(working_dir)
    slash_completer.working_dir = working_dir  # arg 자동완성이 현재 dir 기준 동작
    return pt_prompt(
        HTML(f'<ansibrightblack>{short}</ansibrightblack> '
             f'<ansicyan><b>❯</b></ansicyan> '
             f'<ansibrightblack>[{turns}]</ansibrightblack> '),
        completer=slash_completer,
        style=PT_STYLE,
        complete_while_typing=True,
    )


# ── 스피너 — cli.render._Spinner로 분리 (Phase 3.1-B) ───────────
from cli.render import _Spinner, _SPINNER_FRAMES  # noqa: E402,F401  re-export

_spinner = _Spinner()
_token_buf: list[str] = []


def _flush_tokens():
    _spinner.stop()
    text = ''.join(_token_buf).strip()
    if text:
        console.print(f'\n[orange3]● {config.MODEL}[/orange3]')
        # 각 줄에 2칸 들여쓰기 적용
        indented = '\n'.join('  ' + l for l in text.splitlines())
        console.out(indented, highlight=False)
    _token_buf.clear()


# ── UI 상태 ────────────────────────────────────────────────────────
class _UIState:
    def __init__(self):
        self._active_tool: str | None = None
        self._tool_start_ts: float    = 0.0

    def reset(self):
        self._active_tool = None
        _token_buf.clear()


_ui = _UIState()


# ── 콜백 ──────────────────────────────────────────────────────────
def on_token(token: str):
    _token_buf.append(token)


def on_tool(name: str, args: dict, result):
    label, style, arg_fn = _tool_meta_for(name)
    arg_str = arg_fn(args)

    if result is None:
        _flush_tokens()
        _ui._active_tool    = name
        _ui._tool_start_ts  = time.time()
        console.print(f'[bold]●[/bold] [{style}]{label}[/{style}] [dim]{arg_str}[/dim]')
        _spinner.start()
    else:
        _spinner.stop()
        elapsed    = time.time() - _ui._tool_start_ts
        hint       = _tool_result_hint(name, result)
        elapsed_str = f' [dim]{elapsed:.1f}s[/dim]' if elapsed > 0.5 else ''
        if result.get('ok'):
            console.print(
                f'[dim]└ {hint}[/dim]{elapsed_str}'
            )
        else:
            console.print(
                f'[dim]└ [/dim][tool.fail]{hint}[/tool.fail]'
            )
        _spinner.start()


def confirm_write(path: str, content: str = None) -> bool:
    _flush_tokens()
    if content is not None:
        # diff 미리보기
        try:
            if os.path.exists(path):
                with open(path, encoding='utf-8', errors='replace') as f:
                    old_lines = f.readlines()
                label = path
            else:
                old_lines = []
                label = f'{path} (새 파일)'
            new_lines = [l if l.endswith('\n') else l + '\n' for l in content.splitlines()]
            diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=label, tofile=label, lineterm=''))
            if diff:
                for line in diff[:60]:
                    if line.startswith('+++') or line.startswith('---'):
                        console.print(f'  [dim]{line}[/dim]')
                    elif line.startswith('+'):
                        console.print(f'  [green]{line}[/green]')
                    elif line.startswith('-'):
                        console.print(f'  [red]{line}[/red]')
                    elif line.startswith('@@'):
                        console.print(f'  [cyan]{line}[/cyan]')
                    else:
                        console.print(f'  [dim]{line}[/dim]')
                if len(diff) > 60:
                    console.print(f'  [dim]... (이하 {len(diff)-60}줄 생략)[/dim]')
            else:
                console.print(f'  [dim]변경 없음[/dim]')
        except Exception:
            pass
    return Confirm.ask(f'[bold]●[/bold] [warn]Write[/warn] [bold]{path}[/bold]')


def confirm_bash(command: str) -> bool:
    _flush_tokens()
    return Confirm.ask(f'[bold]●[/bold] [bold red]Run[/bold red] [bold]{command[:100]}[/bold]')


# ── 미등록 툴 제안 ────────────────────────────────────────────────
_INSTALLABLE_TOOLS = {
    'search_web':  ('web.py', 'duckduckgo_search'),
    'fetch_page':  ('web.py', None),
    'search_code': ('search.py', None),
}

from cli.render import _infer_tool_purpose  # noqa: E402,F401  Phase 3.1-B 분리


def _suggest_unknown_tools(items: list[tuple[str, dict]]):
    if not items:
        return
    seen = set()
    for name, args in items:
        if name in seen:
            continue
        seen.add(name)

        info = _INSTALLABLE_TOOLS.get(name)
        if info:
            module_file, pkg = info
            pkg_note = f' [dim](pip install {pkg})[/dim]' if pkg else ''
            console.print(
                f'\n[bold]●[/bold] [warn]미등록 툴:[/warn] [bold]{name}[/bold]{pkg_note}\n'
                f'  [dim]tools/{module_file} 에 구현 후 tools/__init__.py에 등록하세요[/dim]'
            )
        else:
            purpose, args_str = _infer_tool_purpose(name, args)
            console.print(f'\n[bold]●[/bold] [warn]미등록 툴 감지:[/warn] [bold]{name}[/bold]')
            console.print(f'  추정 기능: {purpose}')
            console.print(f'  추가 방법: [dim]tools/{name}.py 구현 → tools/__init__.py 에 등록[/dim]')
            if args_str:
                console.print(f'  {args_str}')
            if Confirm.ask('  하네스에 추가할까요?', default=False):
                console.print(
                    f'  [tool.ok]✓[/tool.ok] /improve 를 실행하면 자동 구현을 시도합니다\n'
                    f'  [dim]또는 tools/{name}.py 를 직접 작성하세요[/dim]'
                )


# ── 응답 구분선 ────────────────────────────────────────────────────
_ctx_display: list = ['']  # main()이 _run_agent 전에 갱신


def _response_header(model_label: str | None = None):
    ctx = _ctx_display[0]
    suffix = f'  {ctx}' if ctx else ''
    console.print(f'\n[dim]{model_label or config.MODEL}[/dim]{suffix}')


def _response_footer():
    console.print()


# ── 유틸 ──────────────────────────────────────────────────────────
def do_index(working_dir: str):
    with Live(
        Spinner('dots', text='[dim]인덱싱 중...[/dim]'),
        console=console,
        refresh_per_second=10,
        transient=True,
    ):
        result = context.index_directory(working_dir)
    console.print(
        f'  [tool.ok]✓[/tool.ok] 인덱싱 완료  '
        f'[bold]{result["indexed"]}[/bold]개 청크  '
        f'[dim](건너뜀 {result["skipped"]}개)[/dim]\n'
    )


def get_context_snippets(query: str, working_dir: str, profile: dict) -> str:
    if not context.is_indexed(working_dir):
        return ''
    chunks = context.search(query, working_dir)
    if not chunks:
        return ''
    extra = []
    for cf in profile.get('context_files', []):
        fpath = os.path.join(working_dir, cf)
        if os.path.exists(fpath):
            try:
                with open(fpath, encoding='utf-8') as f:
                    extra.append(f'// {cf}\n{f.read()[:2000]}')
            except Exception:
                pass
    return context.format_context(chunks) + ('\n' + '\n'.join(extra) if extra else '')


def _auto_sync(working_dir: str):
    if not context.is_indexed(working_dir):
        py_count = sum(1 for _, _, fs in os.walk(working_dir) for f in fs if f.endswith('.py'))
        if py_count > 3:
            do_index(working_dir)
    else:
        result = context.sync_index(working_dir)
        changed = result['added'] + result['changed'] + result['removed']
        if changed:
            console.print(
                f'  [dim]sync[/dim]  '
                f'[tool.ok]+{result["added"]}[/tool.ok] '
                f'[warn]~{result["changed"]}[/warn] '
                f'[tool.fail]-{result["removed"]}[/tool.fail]\n'
            )


_BANNER_LINES = [
    r"   / /_  ____ ________  ___  __________",
    r"  / __ \/ __ `/ ___/ __ \/ _ \/ ___/ ___/",
    r" / / / / /_/ / /  / / / /  __(__  |__  )",
    r"/_/ /_/\__,_/_/  /_/ /_/\___/____/____/",
]

_JABWORKS = r"  ┬  ┌─┐┌┐  ┬ ┌┐┌┌─┐┬─┐┬┌─┌─┐"

# 위→아래 그라데이션: 짙은 파랑 → 하늘색
_GRAD = [
    '\x1b[38;2;41;98;163m',
    '\x1b[38;2;62;133;200m',
    '\x1b[38;2;88;165;225m',
    '\x1b[38;2;120;196;245m',
]
_B = '\x1b[1m'   # bold
_R = '\x1b[0m'   # reset
_D = '\x1b[2m'   # dim
_C = '\x1b[36m'  # cyan


def print_banner():
    console.out('', highlight=False)
    for i, line in enumerate(_BANNER_LINES):
        color = _GRAD[min(i, len(_GRAD) - 1)]
        console.out(f'{_B}{color}  {line}{_R}', highlight=False)

    # jabworks 태그 — 배너 오른쪽 끝에 정렬
    banner_width = max(len(l) for l in _BANNER_LINES) + 2
    tag = 'by jabworks'
    pad = max(0, banner_width - len(tag))
    console.out(f'{" " * pad}{_D}{tag}{_R}', highlight=False)
    console.out(
        f'\n  {_C}local AI coding agent{_R}  '
        f'{_D}·  {config.MODEL}{_R}\n',
        highlight=False,
    )


def print_welcome(working_dir: str):
    indexed = context.is_indexed(working_dir)
    idx_badge = '[tool.ok]indexed[/tool.ok]' if indexed else '[warn]not indexed[/warn]'
    claude_badge = (
        '[tool.ok]claude ✓[/tool.ok]' if claude_available()
        else '[dim]claude ✗[/dim]'
    )
    short = _short_dir(working_dir)

    console.print(
        f'  [bold cyan]{config.MODEL}[/bold cyan]'
        f'[dim]  ·  {short}  ·  [/dim]'
        f'{idx_badge}[dim]  ·  [/dim]{claude_badge}'
    )
    console.print(
        '  [dim]/ 명령어  ·  @claude 질문  ·  /help 도움말[/dim]\n'
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


# ── Claude CLI 호출 ───────────────────────────────────────────────
_CLAUDE_CTX_HEAD = 400
_CLAUDE_CTX_TAIL = 400


def _truncate_for_claude(content: str) -> str:
    '''CONCERNS.md §1.15 대응: head만 자르면 tool 결과(가장 중요한 tail)가
    날아갔음. head+tail을 유지하고 중간 생략을 명시 마커로 표시.'''
    max_chars = _CLAUDE_CTX_HEAD + _CLAUDE_CTX_TAIL
    if len(content) <= max_chars:
        return content
    omitted = len(content) - max_chars
    return (
        content[:_CLAUDE_CTX_HEAD]
        + f'\n…[중간 {omitted}자 생략]…\n'
        + content[-_CLAUDE_CTX_TAIL:]
    )


def _build_claude_context(session_msgs: list, max_turns: int = 6) -> str:
    '''session_msgs에서 최근 대화를 컨텍스트 블록으로 변환.
    에이전트 레이블에 모델명을 붙여 Claude가 로컬 모델 답변임을 인식하게 함.'''
    non_system = [m for m in session_msgs if m['role'] in ('user', 'assistant')]
    recent = non_system[-(max_turns * 2):]
    if not recent:
        return ''
    local_model = config.MODEL  # 예: qwen3-coder:30b
    lines = [f'아래는 현재 세션의 최근 대화 기록이다. 에이전트는 로컬 모델({local_model})이고 너(Claude)와 다른 모델임:\n']
    for m in recent:
        if m['role'] == 'user':
            role = '사용자'
        else:
            role = f'로컬모델({local_model})'
        content = (m.get('content') or '').strip()
        if content:
            lines.append(f'[{role}]: {_truncate_for_claude(content)}')
    lines.append('')
    return '\n'.join(lines)


def _run_claude_cli(query: str, session_msgs: list | None = None, working_dir: str | None = None, model: str | None = None) -> str:
    if not claude_available():
        console.print(
            '  [tool.fail]✗[/tool.fail] claude CLI를 찾을 수 없습니다\n'
            '  [dim]설치: https://claude.ai/code[/dim]'
        )
        return ''

    # 세션 컨텍스트를 query 앞에 붙여 Claude가 대화 흐름을 알 수 있게 함
    if session_msgs:
        ctx = _build_claude_context(session_msgs)
        full_query = f'{ctx}위 대화를 참고해서 다음 질문에 답해줘: {query}' if ctx else query
    else:
        full_query = query

    _token_buf.clear()
    _spinner.start()

    collected = []
    _first_token = [True]

    try:
        def _tok(line):
            if _first_token[0]:
                _first_token[0] = False
                _flush_tokens()  # 스피너 정지
                console.print('\n[bold blue]● Claude[/bold blue]')
            collected.append(line)
            console.print('  ' + line, end='', highlight=False, markup=False)
        claude_ask(full_query, on_token=_tok, cwd=working_dir, model=model)
    except RuntimeError as e:
        _spinner.stop()
        console.print(f'\n  [tool.fail]✗[/tool.fail] {e}\n')
        return ''
    except KeyboardInterrupt:
        _spinner.stop()
        console.print('\n  [dim]중단됨[/dim]\n')
        return ''

    if _first_token[0]:
        _flush_tokens()  # 토큰이 없었던 경우에도 스피너 정지

    console.print('\n')

    response = ''.join(collected).strip()

    if session_msgs is not None and response:
        session_msgs.append({'role': 'user', 'content': f'[Claude에게 질문]\n{query}'})
        session_msgs.append({'role': 'assistant', 'content': f'[Claude 답변]\n{response}'})

    return response


# ── /cloop: Claude ↔ harness 협업 루프 ───────────────────────────
_CLOOP_PLAN_TMPL = '''\
다음 작업을 분석하고 실행 계획을 작성해줘.
작업 디렉토리: {working_dir}
작업: {task}

형식:
1. 각 단계를 번호 목록으로
2. 어떤 파일을 읽고/쓸지 명시
3. 코드 변경이 필요하면 핵심 로직 포함
4. 주의사항/엣지케이스 언급

로컬 코딩 모델이 이 플랜만 보고 바로 실행할 수 있도록 구체적으로 작성해.
'''

_CLOOP_REVIEW_TMPL = '''\
로컬 모델이 작업을 실행했습니다. 결과를 검토하고 다음 중 하나로 답해줘:

[실행 결과]
{result_summary}

원래 작업: {task}

- 작업이 완료됐으면: 첫 줄에 [완료] 라고 쓰고 요약해줘
- 수정/추가 작업이 필요하면: 구체적인 보정 지시사항을 작성해줘 (로컬 모델이 바로 실행할 수 있게)
'''

_CLOOP_MAX_ROUNDS = 5


def _summarize_session_for_claude(msgs: list, last_n: int = 10) -> str:
    '''최근 메시지에서 툴 실행 결과를 요약.'''
    parts = []
    for m in msgs[-last_n:]:
        role = m.get('role', '')
        content = str(m.get('content', ''))[:500]
        if role == 'tool':
            parts.append(f'[툴 결과] {content}')
        elif role == 'assistant' and content:
            parts.append(f'[모델 응답] {content}')
    return '\n'.join(parts) or '(결과 없음)'


def do_claude_loop(task: str, session_msgs: list, working_dir: str, profile: dict) -> list:
    if not claude_available():
        console.print('  [tool.fail]✗[/tool.fail] claude CLI를 찾을 수 없습니다')
        return session_msgs

    snippets = get_context_snippets(task, working_dir, profile)

    for round_num in range(1, _CLOOP_MAX_ROUNDS + 1):
        # ── Claude: 계획 or 검토 ──────────────────────────────────
        if round_num == 1:
            prompt = _CLOOP_PLAN_TMPL.format(task=task, working_dir=working_dir)
            console.print(f'\n[bold blue]● Claude[/bold blue] [dim]({round_num}라운드) 플랜 작성 중...[/dim]')
        else:
            result_summary = _summarize_session_for_claude(session_msgs)
            prompt = _CLOOP_REVIEW_TMPL.format(task=task, result_summary=result_summary)
            console.print(f'\n[bold blue]● Claude[/bold blue] [dim]({round_num}라운드) 결과 검토 중...[/dim]')

        collected = []
        try:
            def _tok(line):
                collected.append(line)
                console.print(line, end='', highlight=False, markup=False)
            claude_ask(prompt, on_token=_tok, cwd=working_dir)
        except (RuntimeError, KeyboardInterrupt) as e:
            console.print(f'\n  [tool.fail]✗[/tool.fail] {e}')
            break

        claude_response = ''.join(collected).strip()
        console.print('\n')

        if not claude_response:
            break

        session_msgs.append({'role': 'user', 'content': f'[Claude {round_num}라운드]\n{claude_response}'})

        # 완료 신호 감지
        if '[완료]' in claude_response or '[DONE]' in claude_response.upper():
            console.print('  [tool.ok]✓[/tool.ok] [bold]Claude가 작업 완료를 확인했습니다[/bold]')
            break

        # ── harness: 실행 ─────────────────────────────────────────
        execute_prompt = (
            f'아래 지시사항을 실행해줘. 파일 읽기/쓰기가 필요하면 도구를 사용해.\n\n'
            f'{claude_response}\n\n원래 작업: {task}'
        )

        console.print(f'\n[dim]● {config.MODEL} ({round_num}라운드 실행)[/dim]')
        _ui.reset()

        _, session_msgs = agent.run(
            execute_prompt,
            session_messages=session_msgs,
            working_dir=working_dir,
            profile=profile,
            context_snippets=snippets,
            on_token=on_token,
            on_tool=on_tool,
            confirm_write=confirm_write if profile.get('confirm_writes', True) else None,
            confirm_bash=confirm_bash if profile.get('confirm_bash', True) else None,
            hooks=profile.get('hooks', {}),
        )
        _response_footer()

    else:
        console.print(f'  [warn]⚠[/warn] 최대 라운드({_CLOOP_MAX_ROUNDS})에 도달했습니다')

    return session_msgs


# ── 슬래시 핸들러 ─────────────────────────────────────────────────
# harness_core로 위임할 슬래시. /help는 _print_help의 풍성한 표를 유지하기 위해 제외.
_CORE_DELEGATED_SLASHES = {'/clear', '/undo', '/cd', '/init', '/save', '/resume', '/sessions', '/files', '/index', '/plan', '/cplan', '/improve', '/learn'}


from cli.render import (  # noqa: E402  Phase 3.1-C 분리 — 호환 re-export
    _render_core_notice,
    _render_sessions_table,
    _render_files_tree,
)


def handle_slash(cmd: str, session_msgs: list, working_dir: str, profile: dict, undo_count: int = 0,
                 run_agent=None, run_agent_ephemeral=None,
                 ask_claude=None, confirm_execute=None) -> tuple[list, str, int]:
    '''run_agent / run_agent_ephemeral / ask_claude / confirm_execute:
    main()의 nested 함수들을 DI로 받아 harness_core.SlashContext로 포장해 dispatch에 전달.'''
    parts = cmd.strip().split(maxsplit=1)
    name = parts[0]

    # 공통 핸들러는 harness_core에 위임 (점진 마이그레이션 화이트리스트)
    if name in _CORE_DELEGATED_SLASHES:
        core_state = harness_core.SlashState(
            messages=session_msgs,
            working_dir=working_dir,
            profile=profile,
            undo_count=undo_count,
        )
        core_ctx = harness_core.SlashContext(
            run_agent=run_agent,
            run_agent_ephemeral=run_agent_ephemeral,
            ask_claude=ask_claude,
            confirm_execute=confirm_execute,
        )
        result = harness_core.dispatch(cmd, core_state, core_ctx)
        if result.handled:
            # 추가 데이터 렌더 (notice로 표현 안 되는 것)
            if name == '/sessions':
                _render_sessions_table(result.data.get('sessions', []))
            elif name == '/files':
                _render_files_tree(result.data.get('tree', {}))
            elif name == '/index':
                console.print(
                    f'  [tool.ok]✓[/tool.ok] 인덱싱 완료  '
                    f'[bold]{result.data.get("indexed", 0)}[/bold]개 청크  '
                    f'[dim](건너뜀 {result.data.get("skipped", 0)}개)[/dim]\n'
                )
            elif name == '/improve':
                backup = result.data.get('backup', '')
                if backup:
                    console.print(f'  [tool.ok]✓[/tool.ok] 백업  [dim]{backup}[/dim]')
                for v in result.data.get('validation', []):
                    if v['ok']:
                        console.print(f'  [tool.ok]✓[/tool.ok] {v["file"]}')
                    else:
                        console.print(f'  [tool.fail]✗[/tool.fail] {v["file"]}  [dim]{v["error"]}[/dim]')
                if result.notice:
                    _render_core_notice(result.notice, result.level)
                console.print()
            elif result.notice:
                _render_core_notice(result.notice, result.level)
            return (result.state.messages, result.state.working_dir, result.state.undo_count)

    if name == '/compact':
        non_sys = [m for m in session_msgs if m['role'] != 'system']
        if len(non_sys) < 4:
            console.print('  [dim]압축할 대화가 충분하지 않습니다[/dim]')
        else:
            console.print('  [dim]세션 압축 중...[/dim]')
            new_msgs, dropped = compact(session_msgs)
            session_msgs = new_msgs
            console.print(f'  [tool.ok]✓[/tool.ok] 압축 완료 — 메시지 {dropped}개 요약됨')
        return session_msgs, working_dir, undo_count

    if name == '/cloop':
        query = parts[1] if len(parts) > 1 else ''
        if not query:
            console.print('  [warn]사용법:[/warn] /cloop <작업 내용>')
            return session_msgs, working_dir, undo_count
        session_msgs = do_claude_loop(query, session_msgs, working_dir, profile)
        return session_msgs, working_dir, undo_count

    if name == '/evolve':
        sub = parts[1] if len(parts) > 1 else ''

        if sub == 'proposals':
            # 제안서 목록 표시
            from evolution.proposer import load_pending, load_all
            pending = load_pending('pending')
            if not pending:
                console.print('  [dim]대기 중인 제안서가 없습니다[/dim]')
            else:
                t = Table(box=box.SIMPLE, show_header=True, border_style='dim')
                t.add_column('우선순위', no_wrap=True)
                t.add_column('타입')
                t.add_column('근거')
                t.add_column('증거', justify='right')
                t.add_column('상태')
                for p in pending:
                    color = 'red' if p['priority'] == 'high' else 'yellow'
                    evidence_count = len(p.get('evidence', []))
                    evidence_str = f'[cyan]{evidence_count}[/cyan]' if evidence_count >= 3 else f'[dim]{evidence_count}[/dim]'
                    t.add_row(
                        f'[{color}]{p["priority"]}[/{color}]',
                        p['type'],
                        p['rationale'][:60],
                        evidence_str,
                        p.get('status', 'pending'),
                    )
                console.print(t)
                console.print('  [dim]증거 수 = 해당 패턴이 관찰된 세션 수 (많을수록 신뢰도 높음)[/dim]')
            return session_msgs, working_dir, undo_count

        if sub == 'run':
            # 제안서 즉시 실행
            from evolution.executor import execute_pending
            console.print('  [dim]자율 개선 실행 중...[/dim]')
            results = execute_pending(force=True, console=console)
            if not results:
                console.print('  [dim]실행할 제안서 없음[/dim]')
            for r in results:
                icon = '[tool.ok]✓[/tool.ok]' if r['ok'] else '[tool.fail]✗[/tool.fail]'
                console.print(f'  {icon} {r["key"]}')
            return session_msgs, working_dir, undo_count

        if sub == 'changelog':
            from evolution.executor import load_changelog
            entries = load_changelog(15)
            if not entries:
                console.print('  [dim]변경 이력이 없습니다[/dim]')
            else:
                t = Table(box=box.SIMPLE, show_header=True, border_style='dim')
                t.add_column('시간', style='dim', no_wrap=True)
                t.add_column('키')
                t.add_column('결과', no_wrap=True)
                t.add_column('근거')
                t.add_column('파일')
                for e in entries:
                    status_str = '[tool.ok]적용[/tool.ok]' if e['status'] == 'applied' else '[tool.fail]실패[/tool.fail]'
                    files_str = ', '.join(e.get('changed_files', [])) or '-'
                    rationale = e.get('rationale', '') or e.get('error', '')
                    t.add_row(e['ts'][:16], e['key'][:30], status_str, rationale[:45], files_str[:40])
                console.print(t)
            return session_msgs, working_dir, undo_count

        # 기본: 진화 엔진 실행
        evolution.run(
            session_msgs=session_msgs,
            working_dir=working_dir,
            profile=profile,
            console=console,
            agent_run=agent.run,
            on_token=on_token,
            on_tool=on_tool,
            confirm_write=confirm_write,
            undo_count=undo_count,
        )
        return session_msgs, working_dir, undo_count

    if name == '/history':
        from evolution.history import recent as hist_recent, avg_score
        from evolution.scorer import grade
        entries = hist_recent(20)
        if not entries:
            console.print('  [dim]진화 이력이 없습니다[/dim]')
            return session_msgs, working_dir, undo_count
        t = Table(box=box.SIMPLE, show_header=True, border_style='dim')
        t.add_column('시간', style='dim', no_wrap=True)
        t.add_column('이벤트')
        t.add_column('품질', justify='right')
        for e in entries[-10:]:
            sc = e.get('score')
            if sc is not None:
                letter, color = grade(sc)
                score_str = f'[{color}]{letter} {sc:.2f}[/{color}]'
            else:
                score_str = '[dim]—[/dim]'
            t.add_row(e['ts'][:16], e.get('event', ''), score_str)
        avg = avg_score(10)
        console.print(t)
        console.print(f'  평균 품질 [bold]{avg:.2f}[/bold] (최근 10세션)\n')
        return session_msgs, working_dir, undo_count

    if name == '/restore':
        backups = list_backups()
        if not backups:
            console.print('  [dim]백업이 없습니다[/dim]')
            return session_msgs, working_dir, undo_count
        t = Table(box=box.SIMPLE, show_header=False)
        for i, b in enumerate(backups[:5]):
            t.add_row(f'[dim]{i}[/dim]', b)
        console.print(t)
        idx_str = parts[1] if len(parts) > 1 else '0'
        try:
            target = backups[int(idx_str)]
        except (ValueError, IndexError):
            target = backups[0]
        if Confirm.ask(f'  [warn]{target}[/warn] 으로 복원할까요?'):
            r = restore_backup(target)
            if r['ok']:
                console.print('  [tool.ok]✓[/tool.ok] 복원 완료 — 하네스를 재시작하세요')
            else:
                console.print(f'  [tool.fail]✗[/tool.fail] {r["error"]}')
        return session_msgs, working_dir, undo_count

    if name == '/commit':
        import subprocess as _sp
        msg = parts[1].strip() if len(parts) > 1 else ''
        if not msg:
            console.print('  [warn]사용법:[/warn] /commit <메시지>')
            return session_msgs, working_dir, undo_count
        # 변경 파일 확인
        status = _sp.run(['git', 'status', '--short'], cwd=working_dir, capture_output=True, text=True)
        if not status.stdout.strip():
            console.print('  [dim]커밋할 변경 사항이 없습니다[/dim]')
            return session_msgs, working_dir, undo_count
        # 변경 목록 표시
        for line in status.stdout.strip().splitlines():
            console.print(f'  [dim]{line}[/dim]')
        if not Confirm.ask('  위 파일을 커밋할까요?', default=True):
            return session_msgs, working_dir, undo_count
        add = _sp.run(['git', 'add', '-A'], cwd=working_dir, capture_output=True, text=True)
        commit = _sp.run(['git', 'commit', '-m', msg], cwd=working_dir, capture_output=True, text=True)
        if commit.returncode == 0:
            # 커밋 해시 추출
            first_line = commit.stdout.strip().splitlines()[0] if commit.stdout.strip() else ''
            console.print(f'  [tool.ok]✓[/tool.ok] {first_line}')
        else:
            console.print(f'  [tool.fail]✗[/tool.fail] {commit.stderr.strip()}')
        return session_msgs, working_dir, undo_count

    if name == '/push':
        import subprocess as _sp
        console.print('  [dim]git push...[/dim]')
        r = _sp.run(['git', 'push'], cwd=working_dir, capture_output=True, text=True)
        if r.returncode == 0:
            out = r.stdout.strip() or r.stderr.strip() or '완료'
            console.print(f'  [tool.ok]✓[/tool.ok] {out}')
        else:
            console.print(f'  [tool.fail]✗[/tool.fail] {r.stderr.strip()}')
        return session_msgs, working_dir, undo_count

    if name == '/pull':
        import subprocess as _sp
        console.print('  [dim]git pull...[/dim]')
        r = _sp.run(['git', 'pull'], cwd=working_dir, capture_output=True, text=True)
        if r.returncode == 0:
            out = r.stdout.strip() or '완료'
            console.print(f'  [tool.ok]✓[/tool.ok] {out}')
        else:
            console.print(f'  [tool.fail]✗[/tool.fail] {r.stderr.strip()}')
        return session_msgs, working_dir, undo_count

    if name == '/claude':
        query = parts[1] if len(parts) > 1 else ''
        if not query:
            console.print('  [warn]사용법:[/warn] /claude <질문>')
            return session_msgs, working_dir, undo_count
        _run_claude_cli(query, session_msgs=session_msgs, working_dir=working_dir, model=profile.get('claude_model') or None)
        return session_msgs, working_dir, undo_count

    if name == '/mode':
        mode = parts[1].strip() if len(parts) > 1 else ''
        valid = ('suggest', 'auto-edit', 'full-auto')
        if mode not in valid:
            console.print(f'  [warn]사용법:[/warn] /mode suggest | auto-edit | full-auto')
            console.print(f'  현재: [bold]{config.APPROVAL_MODE}[/bold]')
        else:
            config.APPROVAL_MODE = mode
            console.print(f'  [tool.ok]✓[/tool.ok] approval_mode → [bold]{mode}[/bold]')
        return session_msgs, working_dir, undo_count

    if name == '/help':
        _print_help()
        return session_msgs, working_dir, undo_count

    console.print(f'  [tool.fail]✗[/tool.fail] 알 수 없는 명령어: [bold]{name}[/bold]  '
                  f'[dim]/ 입력 후 Tab[/dim]')
    return session_msgs, working_dir, undo_count


# ── /files 트리 + /help — cli.render로 분리 (Phase 3.1-C) ────────
from cli.render import _DIR_ICON, _FILE_ICONS, _print_help  # noqa: E402,F401


# ── 메인 ──────────────────────────────────────────────────────────
def _start_mcp_servers(profile: dict) -> dict:
    '''profile의 mcp_servers 목록에서 클라이언트를 시작하고 반환.'''
    clients: dict[str, StdioMCPClient] = {}
    for srv in profile.get('mcp_servers') or []:
        name = srv.get('name', '')
        cmd = srv.get('command')
        if not name or not cmd:
            console.print(f'  [warn]⚠[/warn] MCP 서버 설정 오류: name/command 필수 — {srv}')
            continue
        if isinstance(cmd, str):
            cmd = cmd.split()
        env = srv.get('env') or {}
        client = StdioMCPClient(name, cmd, env)
        try:
            ok = client.start()
        except RuntimeError as e:
            console.print(f'  [tool.fail]✗[/tool.fail] MCP [{name}] 시작 실패: {e}')
            continue
        if ok:
            clients[name] = client
            tool_count = len(client.tools)
            console.print(f'  [tool.ok]✓[/tool.ok] MCP [{name}] 연결됨 — 툴 {tool_count}개')
        else:
            console.print(f'  [tool.fail]✗[/tool.fail] MCP [{name}] 초기화 실패')
    return clients


def _ctx_status(session_msgs: list) -> str:
    '''ctx 토큰 상태 문자열 반환. 예: "ctx: 8k/32k (25%)"'''
    used = sum(len(m.get('content') or '') for m in session_msgs) // 4
    total = config.CONTEXT_WINDOW
    pct = int(used / total * 100) if total else 0
    used_k = f'{used // 1000}k' if used >= 1000 else str(used)
    total_k = f'{total // 1000}k' if total >= 1000 else str(total)
    if pct >= 95:
        color = 'red'
    elif pct >= 80:
        color = 'yellow'
    else:
        color = 'dim'
    return f'[{color}]ctx: {used_k}/{total_k} ({pct}%)[/{color}]'


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
    _mcp_clients: dict[str, StdioMCPClient] = {}
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
            user_input = get_input(turns, working_dir).strip()

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
