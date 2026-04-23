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
from cli.setup import _build_status_bar, slash_completer


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
    # CSI u 확장 키보드 모드는 쓰지 않는다.
    # 활성화 시 터미널이 `\x1b[27u` 같은 미매핑 시퀀스를 보내면 prompt_toolkit
    # 이 해석 못 해 `[27u` 가 literal 로 입력창에 들어가는 버그가 있어 제거.
    # Shift+Enter 는 Ctrl+J (모든 터미널에서 동작) 로 대체 유도.

    _running: dict = {'task': None}
    _spin: dict = {'i': 0}

    # 입력 영역: content-based height, 1~10줄.
    input_area = TextArea(
        multiline=True,
        prompt=HTML('<prompt>❯ </prompt>'),
        completer=slash_completer,
        complete_while_typing=True,
        wrap_lines=False,
        scrollbar=False,
        style='class:input',
    )

    # 입력창 높이를 동적 callable 로 교체.
    # Dimension(min=1, max=10) 의 preferred 기본값은 max(10) 이라 TextArea 가
    # 초기부터 10줄을 차지해 화면 상단에 큰 빈 공간을 만드는 문제가 있다.
    # content 의 `\n` 개수에 맞춰 preferred 를 계산하면 빈 입력은 1줄, 개행
    # 여럿이면 그만큼 (최대 10) 만 차지.
    def _input_height():
        lines = input_area.buffer.text.count('\n') + 1
        return Dimension(min=1, max=10, preferred=max(1, min(lines, 10)))

    input_area.window.height = _input_height

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

    @kb.add('c-l')
    def _redraw(event):
        '''수동 전체 redraw — resize 후 레이아웃 깨짐 복구용 safety net.'''
        _on_winch()

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

    # Resize 누적 방지.
    #
    # polling 은 호출되지만 sys.__stdout__.write 경로도 효과 없음이 관찰됨.
    # 최저 레벨 os.write(fd=1) 로 직접 kernel write syscall → 어떤 Python
    # buffering/patch 도 우회. 응답 byte 수로 실제 송출 확인 가능.
    import os as _os

    def _on_winch():
        try:
            if not app.is_running:
                return
            wrote = -1
            try:
                wrote = _os.write(1, b'\x1b[2J\x1b[H')
            except Exception:
                pass
            # 진단 marker — 실제 kernel 로 몇 byte 쓰였는지 확인
            try:
                console.print(f'[dim red]▸ resize (wrote {wrote}B)[/dim red]')
            except Exception:
                pass
            try:
                app.renderer.reset()
            except Exception:
                try:
                    app.renderer._last_screen = None
                except Exception:
                    pass
            app.invalidate()
        except Exception:
            pass

    def _pre_run():
        '''app.run 시작 후 호출 — asyncio background task 로 terminal size
        변경을 100ms 주기로 polling. signal 기반보다 확실.'''
        import shutil as _shutil
        import asyncio as _asyncio

        _size_state = {'size': _shutil.get_terminal_size()}

        async def _watch_size():
            while True:
                try:
                    cur = _shutil.get_terminal_size()
                    if cur != _size_state['size']:
                        _size_state['size'] = cur
                        _on_winch()
                except Exception:
                    pass
                await _asyncio.sleep(0.1)

        try:
            app.create_background_task(_watch_size())
        except Exception:
            try:
                _asyncio.ensure_future(_watch_size())
            except Exception:
                pass

    with patch_stdout(raw=True):
        app.run(pre_run=_pre_run)
