'''Claude Code 스타일 long-running inline REPL.

`Application(full_screen=False) + patch_stdout()` 조합.

- `full_screen=False` — alternate screen 사용 안 함. 터미널 scrollback 그대로.
- Application 이 REPL 내내 계속 running — 하단 layout (입력창 · 구분선 · 상태바)
  이 agent 실행 중에도 항상 live.
- `patch_stdout(raw=True)` — stdout 쓰기를 가로채 live 영역을 위로 밀고 새 줄을
  scrollback 에 flush. 결과적으로 출력은 쌓이고 입력창은 하단 고정.

구조:
  (scrollback — agent 출력이 쌓임)
  ─────────────────────────────────   top_rule
  ❯ 입력                               input_area (TextArea, multiline)
  ─────────────────────────────────   bot_rule
  path · model · turn · mode · ctx     status_win
'''
import asyncio
from typing import Awaitable, Callable

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import HTML, to_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Float, FloatContainer, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.widgets import TextArea

from cli.render import PT_STYLE, console
from cli.setup import _build_status_bar, _ensure_csi_u_mode, slash_completer


# 상태바 스피너 프레임 — brail dots. Application 내부 렌더로 회전하므로
# ANSI escape 직접 쓰기 없이도 live 영역과 충돌 없이 자연스럽게 돈다.
_SPIN_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']


def run_app(
    working_dir_getter: Callable[[], str],
    state_getter: Callable[[], tuple[list, int]],
    handle_turn: Callable[[str], Awaitable[bool]],
) -> None:
    '''REPL 진입점. handle_turn 이 False 반환하면 종료.

    Args:
        working_dir_getter: 현재 working_dir 반환 (cd 후 변경 반영 위해 getter)
        state_getter: (session_msgs, turns) 반환 — status bar 렌더용
        handle_turn: async fn. 입력 한 턴 처리 후 True(계속) / False(종료) 반환
    '''
    _ensure_csi_u_mode()

    _running: dict = {'task': None}
    _spin: dict = {'i': 0}

    # 입력 영역: 높이는 오로지 개행 수로만 결정. 폭 변경 시 늘어나지 않음.
    # - wrap_lines=False: 긴 한 줄이 soft-wrap 되지 않아 폭이 줄어도 높이
    #   증가 없음 (잘리는 부분은 가로 스크롤로 보임).
    # - height=Dimension(min=1, max=10): 1줄 시작, 개행으로 최대 10줄.
    input_area = TextArea(
        multiline=True,
        prompt=HTML('<prompt>❯ </prompt>'),
        completer=slash_completer,
        complete_while_typing=True,
        wrap_lines=False,
        scrollbar=False,
        height=Dimension(min=1, max=10),
        style='class:input',
    )

    top_rule = Window(height=1, char='─', style='class:frame')
    bot_rule = Window(height=1, char='─', style='class:frame')

    def _status_ft():
        msgs, turns = state_getter()
        bar_ft = to_formatted_text(
            _build_status_bar(msgs, working_dir_getter(), turns)
        )
        # 진행 중인 턴이 있으면 상태바 맨 앞에 spinner 프레임.
        # refresh_interval 로 자동 invalidate → 프레임 회전.
        running = _running['task'] is not None and not _running['task'].done()
        if running:
            frame = _SPIN_FRAMES[_spin['i'] % len(_SPIN_FRAMES)]
            _spin['i'] += 1
            spin_ft = to_formatted_text(HTML(f' <ansicyan>{frame}</ansicyan>'))
            return spin_ft + bar_ft
        return bar_ft

    status_win = Window(
        content=FormattedTextControl(text=_status_ft),
        height=1,
        style='class:status-bar',
    )

    kb = KeyBindings()

    @kb.add('enter', eager=True)
    def _submit(event):
        # 이전 턴 진행 중이면 새 입력 접수 안 함 (race 방지)
        if _running['task'] and not _running['task'].done():
            return
        text = input_area.text
        if not text.strip():
            return
        input_area.buffer.reset()
        # cd 가 일어난 경우 자동완성 기준 디렉토리 갱신
        slash_completer.working_dir = working_dir_getter()

        # echo 사용자 입력을 scrollback 에
        for i, line in enumerate(text.split('\n')):
            prefix = '[prompt]❯[/prompt] ' if i == 0 else '  '
            console.print(f'{prefix}{line}')

        async def _run():
            try:
                cont = await handle_turn(text)
                if cont is False:
                    event.app.exit()
            except asyncio.CancelledError:
                console.print('[dim]— 중단됨 —[/dim]')
            except Exception as e:
                import traceback
                console.print(
                    f'[bold red]에러: {type(e).__name__}: {e}[/bold red]'
                )
                console.print(f'[dim]{traceback.format_exc()}[/dim]')
            finally:
                _running['task'] = None

        _running['task'] = asyncio.ensure_future(_run())

    @kb.add('c-j')
    def _nl_ctrl_j(event):
        input_area.buffer.insert_text('\n')

    @kb.add(Keys.Escape, Keys.Enter, eager=True)
    def _nl_alt_enter(event):
        input_area.buffer.insert_text('\n')

    @kb.add('c-c')
    def _interrupt(event):
        # 진행 중 턴이 있으면 취소, 없으면 입력 버퍼만 리셋
        t = _running['task']
        if t and not t.done():
            t.cancel()
        else:
            input_area.buffer.reset()

    @kb.add('c-d')
    def _eof(event):
        if not input_area.text and _running['task'] is None:
            event.app.exit()

    # FloatContainer 로 입력창 위에 자동완성 popup (CompletionsMenu) 을 띄운다.
    # xcursor/ycursor=True 로 커서 위치 근처에 popup 이 뜨고, complete_while_typing
    # 을 켜뒀으므로 `/` 입력 즉시 슬래시 카탈로그 드롭다운이 보인다.
    root = FloatContainer(
        content=HSplit([top_rule, input_area, bot_rule, status_win]),
        floats=[
            Float(
                xcursor=True,
                ycursor=True,
                content=CompletionsMenu(max_height=8, scroll_offset=1),
            ),
        ],
    )
    layout = Layout(root, focused_element=input_area)

    app = Application(
        layout=layout,
        key_bindings=kb,
        style=PT_STYLE,
        full_screen=False,
        mouse_support=False,
        erase_when_done=True,
        # spinner 프레임 회전 + resize 후 stale line 완화용 주기 리드로.
        refresh_interval=0.1,
    )

    # SIGWINCH 에서 렌더러 내부 state 를 강제로 지워 stale 라인 누적 방지.
    # prompt_toolkit inline(full_screen=False) 은 terminal 폭이 바뀌면 이전
    # 렌더의 soft-wrap 라인 수를 못 맞춰 cursor-up 범위가 부정확해진다.
    # erase() 로 전체 지우고 다음 tick 에 깨끗이 다시 그린다.
    import signal as _signal

    def _on_winch(*_a, **_kw):
        try:
            if app.is_running:
                app.renderer.erase()
                app.invalidate()
        except Exception:
            pass

    try:
        _prev_winch = _signal.getsignal(_signal.SIGWINCH)
    except (AttributeError, ValueError):
        _prev_winch = None

    def _chained_winch(signum, frame):
        _on_winch()
        if callable(_prev_winch):
            try:
                _prev_winch(signum, frame)
            except Exception:
                pass

    try:
        _signal.signal(_signal.SIGWINCH, _chained_winch)
    except (AttributeError, ValueError, OSError):
        # 메인 스레드 아니거나 플랫폼(win32)이 SIGWINCH 미지원인 경우 무시
        pass

    try:
        with patch_stdout(raw=True):
            app.run()
    finally:
        if _prev_winch is not None:
            try:
                _signal.signal(_signal.SIGWINCH, _prev_winch)
            except (AttributeError, ValueError, OSError):
                pass
