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
import atexit
import os
import sys

from rich.live import Live
from rich.spinner import Spinner

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

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


# ── 입력 키바인딩 ────────────────────────────────────────────────
# Claude Code 느낌: Enter = 제출, 개행은 아래 바인딩 중 동작하는 걸 사용.
# multiline=True 의 prompt_toolkit 기본은 Enter=newline 이므로 `eager=True`
# 로 우리 바인딩이 우선하게 해서 override.
#
# 개행 키:
#  · Ctrl+J — 모든 터미널에서 동작하는 범용 개행 (가장 확실).
#  · Meta+Enter (Option+Enter → ESC Enter 시퀀스) — macOS Terminal.app 은
#    Preferences → Profiles → Keyboard "Use Option as Meta key" 체크 필요.
#    iTerm2 는 Profile → Keys → Left/Right Option Key → "Esc+".
#  · Shift+Enter — iTerm2 "Natural Text Editing" 등 일부에서만.
_INPUT_KB = KeyBindings()


@_INPUT_KB.add('enter', eager=True)
def _enter_submit(event):
    '''Enter = 제출. (개행은 Ctrl+J / Meta+Enter / Shift+Enter.)'''
    event.current_buffer.validate_and_handle()


@_INPUT_KB.add('c-j')
def _ctrl_j_newline(event):
    '''Ctrl+J = 개행 (가장 범용 — 터미널 설정 없이 모두 동작).'''
    event.current_buffer.insert_text('\n')


@_INPUT_KB.add(Keys.Escape, Keys.Enter, eager=True)
def _alt_enter_newline(event):
    '''Meta+Enter (Option+Enter) = 개행. 터미널이 Option→Meta 설정된 경우.'''
    event.current_buffer.insert_text('\n')


try:
    @_INPUT_KB.add('s-enter')
    def _shift_enter_newline(event):
        '''Shift+Enter = 개행 (iTerm2 Natural Text Editing 등에서만 동작).'''
        event.current_buffer.insert_text('\n')
except Exception:
    pass


# ── Claude Code 스타일: 확장 키보드 모드(CSI u) 활성화 ───────────
# Shift+Enter 를 별도 시퀀스(\x1b[13;2u)로 보내도록 터미널에 요청하고,
# prompt_toolkit 의 ANSI_SEQUENCES 에 그 시퀀스를 Alt+Enter 와 동일한
# 이벤트 튜플로 매핑해 기존 _alt_enter_newline 바인딩이 그대로 발화하게
# 한다. 지원 터미널: iTerm2 3.5+, kitty, foot, WezTerm 등.
# 미지원 터미널(macOS Terminal.app)은 escape 시퀀스를 무시하고 Ctrl+J /
# Alt+Enter fallback 으로 동작한다.
_csi_u_enabled = False


def _ensure_csi_u_mode() -> None:
    global _csi_u_enabled
    if _csi_u_enabled:
        return
    _csi_u_enabled = True

    try:
        from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
        # Shift+Enter (modifiers=2) · Ctrl+Enter (=5) · Ctrl+Shift+Enter (=6)
        # 주요 조합만 Alt+Enter 와 동일한 이벤트 시퀀스로 매핑 → 개행.
        for seq in ('\x1b[13;2u', '\x1b[13;5u', '\x1b[13;6u'):
            ANSI_SEQUENCES.setdefault(seq, (Keys.Escape, Keys.Enter))
    except Exception:
        pass

    try:
        sys.stdout.write('\x1b[>1u')  # 터미널에 CSI u 확장 키보드 활성화 요청
        sys.stdout.flush()
    except Exception:
        pass

    def _restore() -> None:
        try:
            sys.stdout.write('\x1b[<u')  # 종료 시 복원
            sys.stdout.flush()
        except Exception:
            pass

    atexit.register(_restore)


_BAR_WIDTH = 10  # ctx progress bar 셀 수


def _build_status_bar(session_msgs: list) -> HTML:
    '''prompt_toolkit bottom_toolbar.

    레이아웃 (역상 배경 제거, 레이블 생략, 공백 호흡):
        {model}      {mode}      {▰▰▱▱▱▱▱▱▱▱} {pct}%

    - 모델: cyan (정체성)
    - 모드: 위험도 색 — suggest=blue / auto-edit=green / full-auto=red
    - 진행바: dim(빈 셀) + ctx 색(채움 셀), 셀 수 _BAR_WIDTH
    - %: 80%↑ yellow, 95%↑ red — 압축 타이밍 신호
    '''
    used = sum(len(m.get('content') or '') for m in session_msgs) // 4
    total = config.CONTEXT_WINDOW
    pct = int(used / total * 100) if total else 0
    pct_clamped = min(pct, 100)

    if pct_clamped >= 95:
        ctx_color = 'ansired'
    elif pct_clamped >= 80:
        ctx_color = 'ansiyellow'
    else:
        ctx_color = 'ansigreen'

    filled = int(pct_clamped * _BAR_WIDTH / 100)
    bar_filled = '▰' * filled
    bar_empty = '▱' * (_BAR_WIDTH - filled)

    mode = config.APPROVAL_MODE
    mode_color = {
        'suggest':   'ansiblue',
        'auto-edit': 'ansigreen',
        'full-auto': 'ansired',
    }.get(mode, 'ansibrightblack')

    # 세그먼트는 공백 4칸으로 분리 — 점/파이프 구분자보다 깔끔.
    # pct 는 오른쪽 정렬 3칸으로 흔들림 없이 고정.
    return HTML(
        f'  <ansicyan>{config.MODEL}</ansicyan>'
        f'    <{mode_color}>{mode}</{mode_color}>'
        f'    <{ctx_color}>{bar_filled}</{ctx_color}><ansibrightblack>{bar_empty}</ansibrightblack>'
        f' <{ctx_color}>{pct:>3}%</{ctx_color}>'
    )


def get_input(turns: int, working_dir: str, session_msgs: list | None = None) -> str:
    _ensure_csi_u_mode()
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
        multiline=True,
        key_bindings=_INPUT_KB,
        prompt_continuation=lambda width, line_number, wrap_count: '',
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
