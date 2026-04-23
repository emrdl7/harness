'''Claude Code 스타일 long-running REPL — Rich.Live 기반.

왜 Rich.Live 인가:
  · prompt_toolkit Application(full_screen=False) 의 renderer 는 wrap 인식
    못해 resize 시 cursor-up 계산이 어긋나 stale 라인이 누적 (upstream
    버그). ED2/ED3 로 scrollback 깎는 건 사용자 원하는 동작 아님.
  · Rich.Live 는 terminal width 를 측정해 정확한 line count 기반으로
    live region 을 erase 후 재그림. Claude Code (Ink + log-update) 와 동일
    구조. Resize 시 누적 없이 scrollback 도 유지.

구조:
  (scrollback — console.print 로 쌓인 agent 출력)
  ─────────────────────────  ← Live region 내부의 bot_rule
  ~/harness  model  turn N  mode  ctx%   ← status bar

  (입력 대기 중에만 추가로)
  ─────────────────────────  top_rule (pt_prompt 호출 전에 console.print)
  ❯ 입력                      pt_prompt 가 그린 입력창

흐름:
  1. Live active (bot_rule + status) — agent 실행 중/대기 중 계속 하단 고정
  2. 입력 준비: Live.stop → top_rule console.print → pt_prompt 호출
  3. Enter 제출 → pt_prompt 리턴 → Live.start
  4. handle_turn(text) → agent 출력은 console.print 로 scrollback 에 append.
     Rich.Live 가 자동으로 region 을 위로 밀고 새 출력 아래에 재배치.
  5. 루프.
'''
import threading
import time
from typing import Callable

from rich.console import Group
from rich.live import Live
from rich.text import Text

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

import config
from cli import render as _render_mod
from cli.render import PT_STYLE, console, _short_dir
from cli.setup import slash_completer


_SPIN_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
_BAR_WIDTH = 10


def _rich_status_line(msgs, wd, turns, spin_frame=''):
    used = sum(len(m.get('content') or '') for m in msgs) // 4
    total = config.CONTEXT_WINDOW
    pct = int(used / total * 100) if total else 0
    pct_clamped = min(pct, 100)
    filled = int(pct_clamped * _BAR_WIDTH / 100)
    bar = '▰' * filled + '▱' * (_BAR_WIDTH - filled)

    mode = config.APPROVAL_MODE
    mode_color = {
        'suggest':   'blue',
        'auto-edit': 'green',
        'full-auto': 'red',
    }.get(mode, 'bright_black')
    ctx_color = (
        'red' if pct_clamped >= 95
        else 'yellow' if pct_clamped >= 80
        else 'green'
    )
    short = _short_dir(wd)

    t = Text(no_wrap=True, overflow='ellipsis')
    if spin_frame:
        t.append(f' {spin_frame}', style='cyan')
    t.append(f'  {short}', style='bright_black')
    t.append(f'    {config.MODEL}', style='cyan')
    t.append(f'    turn {turns}', style='bright_black')
    t.append(f'    {mode}', style=mode_color)
    t.append(f'    {bar}', style=ctx_color)
    t.append(f' {pct:>3}%', style=ctx_color)
    return t


def _bottom_region(msgs, wd, turns, spin_frame=''):
    '''Live region — bot_rule + status line.'''
    w = console.width
    return Group(
        Text('─' * w, style='dim'),
        _rich_status_line(msgs, wd, turns, spin_frame),
    )


def _make_pt_kb() -> KeyBindings:
    '''pt_prompt 키바인딩 — Enter=제출, Ctrl+J / Alt+Enter=개행.'''
    kb = KeyBindings()

    @kb.add('enter', eager=True)
    def _submit(event):
        event.current_buffer.validate_and_handle()

    @kb.add('c-j')
    def _nl_ctrl_j(event):
        event.current_buffer.insert_text('\n')

    @kb.add(Keys.Escape, Keys.Enter, eager=True)
    def _nl_alt_enter(event):
        event.current_buffer.insert_text('\n')

    return kb


_PT_KB = _make_pt_kb()


def run_app(
    working_dir_getter: Callable[[], str],
    state_getter: Callable[[], 'tuple[list, int]'],
    handle_turn: Callable[[str], bool],
) -> None:
    '''Rich.Live 기반 REPL.

    handle_turn(text: str) -> bool: True 면 REPL 계속, False 면 종료.
    '''
    spin_state = {'i': 0, 'spinning': False, 'stop_thread': False}

    def _render():
        msgs, turns = state_getter()
        frame = ''
        if spin_state['spinning']:
            frame = _SPIN_FRAMES[spin_state['i'] % len(_SPIN_FRAMES)]
        return _bottom_region(msgs, working_dir_getter(), turns, frame)

    # Rich.Live 는 `refresh_per_second` 기반 자동 갱신 + renderable 변화 시
    # 즉시 재그림. 자동 갱신으로 spinner 프레임 회전이 이루어지도록.
    live_console = console.target if hasattr(console, 'target') else console

    # 백그라운드 spinner tick — spinning=True 인 동안만 index 증가.
    # Live.refresh_per_second 가 tick 과 맞물려 프레임 회전 표시.
    def _spin_tick():
        while not spin_state['stop_thread']:
            if spin_state['spinning']:
                spin_state['i'] += 1
            time.sleep(0.1)

    tick_thread = threading.Thread(target=_spin_tick, daemon=True)
    tick_thread.start()

    # 기존 cli.render._Spinner (stdout 에 ANSI escape 직접) 는 Rich.Live
    # region 을 덮어 매 프레임 새 줄이 찍히는 현상을 유발하므로 비활성화.
    _render_mod._spinner_disabled = True

    try:
        with Live(
            _render(),
            console=live_console,
            refresh_per_second=10,
            transient=False,
            screen=False,
            get_renderable=_render,
            auto_refresh=True,
        ) as live:
            while True:
                # 입력 단계: Live 가 자기 region 을 그대로 유지한 채 pt_prompt
                # 를 그 "위" scrollback 에 그림 (한 턴 끝난 시점이라 Live
                # region 이 마지막 출력 바로 아래에 있음). pt_prompt 는
                # 자기 출력을 sys.stdout 에 쓰는데 Live 가 아래에 있어
                # 겹침이 생길 수 있음. 그래서 입력 직전 Live.stop, 끝나면
                # Live.start 로 재개.
                live.stop()

                # cd 반영
                slash_completer.working_dir = working_dir_getter()

                try:
                    # top_rule 을 입력 위에 scrollback 에 찍음
                    w = console.width
                    console.print(Text('─' * w, style='dim'))
                    text = pt_prompt(
                        HTML('<prompt>❯ </prompt>'),
                        completer=slash_completer,
                        style=PT_STYLE,
                        complete_while_typing=True,
                        multiline=True,
                        key_bindings=_PT_KB,
                        prompt_continuation=lambda w, ln, wc: '  ',
                    )
                except (KeyboardInterrupt, EOFError):
                    console.print('[dim]종료[/dim]')
                    break

                live.start()

                text = (text or '').strip()
                if not text:
                    continue

                # handle_turn 실행 — agent 출력은 전부 console.print 경유라
                # Rich.Live 가 자동으로 region 을 위로 밀고 scrollback 에 append.
                spin_state['spinning'] = True
                try:
                    cont = handle_turn(text)
                except (KeyboardInterrupt, EOFError):
                    cont = True
                    console.print('[dim]— 중단됨 —[/dim]')
                except Exception as e:
                    import traceback
                    console.print(
                        f'[bold red]에러: {type(e).__name__}: {e}[/bold red]'
                    )
                    console.print(f'[dim]{traceback.format_exc()}[/dim]')
                    cont = True
                finally:
                    spin_state['spinning'] = False

                if cont is False:
                    break
    finally:
        spin_state['stop_thread'] = True
        _render_mod._spinner_disabled = False
