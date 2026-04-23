'''CLI 부팅·세팅 헬퍼 — main.py에서 분리(Phase 3.1-E).

여기에 모은 것:
- print_banner / print_welcome — 시작 배너 + 환영 메시지
- get_input + slash_completer — prompt_toolkit 입력 프롬프트
- do_index / _auto_sync / get_context_snippets — 인덱싱/컨텍스트 스니펫
- _start_mcp_servers — profile.mcp_servers 부팅
- _ctx_status — 세션 토큰 사용률 문자열

main.py는 호환을 위해 이 모듈의 심볼을 re-export한다 (tests/test_handle_slash.py
가 main.get_context_snippets 를 monkeypatch 하는 등의 의존이 있음).
'''
import os

from rich.live import Live
from rich.spinner import Spinner

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import HTML

import config
import context
from tools.mcp import StdioMCPClient
from tools.claude_cli import is_available as claude_available

from cli.render import (
    console,
    PT_STYLE,
    SlashCompleter,
    _short_dir,
)


# ── 슬래시 자동완성 싱글톤 ──────────────────────────────────────
slash_completer = SlashCompleter()


def _build_status_bar(session_msgs: list) -> HTML:
    '''prompt_toolkit bottom_toolbar — model · ctx% · approval_mode.

    색상 의미:
    - ctx: 80%↑ yellow, 95%↑ red
    - mode: suggest=blue(읽기만), auto-edit=green(안전 기본), full-auto=red(위험)
    '''
    used = sum(len(m.get('content') or '') for m in session_msgs) // 4
    total = config.CONTEXT_WINDOW
    pct = int(used / total * 100) if total else 0

    if pct >= 95:
        ctx_color = 'ansired'
    elif pct >= 80:
        ctx_color = 'ansiyellow'
    else:
        ctx_color = 'ansigreen'

    mode = config.APPROVAL_MODE
    mode_color = {
        'suggest':   'ansiblue',
        'auto-edit': 'ansigreen',
        'full-auto': 'ansired',
    }.get(mode, 'ansibrightblack')

    sep = '<ansibrightblack>  ·  </ansibrightblack>'
    return HTML(
        f'  <ansibrightblack>model</ansibrightblack> <ansicyan>{config.MODEL}</ansicyan>'
        f'{sep}<ansibrightblack>ctx</ansibrightblack> <{ctx_color}>{pct}%</{ctx_color}>'
        f'{sep}<ansibrightblack>mode</ansibrightblack> <{mode_color}>{mode}</{mode_color}>'
    )


def get_input(turns: int, working_dir: str, session_msgs: list | None = None) -> str:
    short = _short_dir(working_dir)
    slash_completer.working_dir = working_dir  # arg 자동완성이 현재 dir 기준 동작
    toolbar = _build_status_bar(session_msgs) if session_msgs is not None else None
    return pt_prompt(
        HTML(f'<ansibrightblack>{short}</ansibrightblack> '
             f'<ansicyan><b>❯</b></ansicyan> '
             f'<ansibrightblack>[{turns}]</ansibrightblack> '),
        completer=slash_completer,
        style=PT_STYLE,
        complete_while_typing=True,
        bottom_toolbar=toolbar,
    )


# ── 인덱싱 ────────────────────────────────────────────────────────
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


# ── 배너 / 환영 ───────────────────────────────────────────────────
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


# ── MCP 서버 부팅 ─────────────────────────────────────────────────
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


# ── 컨텍스트 상태 ─────────────────────────────────────────────────
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
