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
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.widgets import TextArea

from cli.render import PT_STYLE, console
from cli.setup import _build_status_bar, _ensure_csi_u_mode, slash_completer


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

    input_area = TextArea(
        multiline=True,
        prompt=HTML('<prompt>❯ </prompt>'),
        completer=slash_completer,
        complete_while_typing=True,
        wrap_lines=True,
        scrollbar=False,
        style='class:input',
    )

    top_rule = Window(height=1, char='─', style='class:frame')
    bot_rule = Window(height=1, char='─', style='class:frame')

    def _status_ft():
        msgs, turns = state_getter()
        return to_formatted_text(
            _build_status_bar(msgs, working_dir_getter(), turns)
        )

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
    )

    with patch_stdout(raw=True):
        app.run()
