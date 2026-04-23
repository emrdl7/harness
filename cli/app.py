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

    # SIGWINCH 에서 stale 라인 제거.
    #
    # 구현 핵심:
    # 1) asyncio loop.add_signal_handler 로 등록 — signal.signal 은
    #    prompt_toolkit 의 asyncio 경로에 덮여 호출 안 되는 이슈 회피.
    #    app.run 시작 후 (pre_run 훅에서) 설치해 prompt_toolkit 의 기본
    #    SIGWINCH 핸들러를 의도적으로 override.
    # 2) escape 직접 쏘기 — cursor_up(넉넉히) → cursor_backward → erase_down.
    #    이전 render 의 live 영역 + stale 누적분을 한 번에 제거.
    # 3) renderer 내부 _last_screen = None 으로 초기화 → prompt_toolkit 이
    #    "처음 그리는 것" 처럼 행동해 잘못된 cursor-up 계산 없이 새로 그림.
    # 4) CPR 요청 + invalidate — next render 가 정확한 절대 좌표에서 시작.
    import signal as _signal

    # cursor up 량 — live 영역 충분히 커버 + resize 누적분까지 여유있게.
    # scrollback 을 조금 건드릴 수 있지만 빈 줄이 될 뿐 원본 텍스트는
    # scrollback buffer 에 보존되어 위로 스크롤 시 복구.
    _WINCH_CLEAR_ROWS = 30

    def _on_winch():
        try:
            if not app.is_running:
                return
            out = app.output
            out.cursor_up(_WINCH_CLEAR_ROWS)
            out.cursor_backward(10_000)
            out.erase_down()
            out.flush()
            # renderer internal state 초기화 → 다음 render 가 cursor-up 없이
            # 현재 위치에서 처음부터 그림
            try:
                app.renderer._last_screen = None
            except Exception:
                pass
            app.renderer.request_absolute_cursor_position()
            app.invalidate()
        except Exception:
            pass

    def _pre_run():
        '''Application 이 돌기 시작한 후 실행 — asyncio loop 에 SIGWINCH
        핸들러를 등록해 prompt_toolkit 의 기본 핸들러를 override.'''
        try:
            import asyncio as _asyncio
            loop = _asyncio.get_event_loop()
            loop.add_signal_handler(_signal.SIGWINCH, _on_winch)
        except (NotImplementedError, ValueError, RuntimeError, AttributeError):
            # Windows / non-main thread 등은 SIGWINCH 미지원 — 스킵
            pass

    with patch_stdout(raw=True):
        app.run(pre_run=_pre_run)
