'''Textual 기반 TUI — `harness --tui` 진입점.

REPL(main.py)과 같은 cli.* 기반 위에서 돈다. HarnessApp 이 agent.run /
handle_slash / _run_claude_cli 를 그대로 호출하되, 출력·입력·확인 경로만
TUI 위젯으로 돌린다. 슬래시 분기 중복 없이 로직을 공유.

전환 메커니즘 (TUI 진입 시):
- cli.render.console.file  → _TUIStream   (stdout 대신 RichLog)
- cli.callbacks.on_token    → app._on_token_tui
- cli.callbacks.on_tool     → app._on_tool_tui
- cli.callbacks.confirm_write → app._confirm_write
- cli.callbacks.confirm_bash  → app._confirm_bash
- rich.prompt.Confirm.ask   → _tui_confirm   (모든 Confirm.ask 가로채기)
종료 시 원상복구.

알려진 MVP 한계:
- cli.slash 내부 import가 `from cli.callbacks import on_token` 고정 바인딩
  이라 /evolve, /commit 등 일부 슬래시의 console 출력이 RichLog에 뜨지
  않을 수 있음. 주요 경로(agent/claude/_handle_slash 직접 호출)는 정상.
  이 간극은 T1b에서 holder 패턴으로 풀 예정.
'''
import os
import sys
import threading

from textual.app import App, ComposeResult
from textual.widgets import RichLog, TextArea, Static
from textual.containers import Vertical
from textual.binding import Binding
from textual.message import Message
from textual import on

from rich.rule import Rule
from rich.text import Text
from rich.panel import Panel
from rich import box
import rich.prompt

import agent
import config
import profile as prof
import session as sess

from cli import render as _render
from cli import callbacks as _cb
from cli import slash as _slash
from cli.claude import _run_claude_cli, do_claude_loop
from cli.setup import (
    _auto_sync,
    get_context_snippets,
    _start_mcp_servers,
    _ctx_status,
)
from cli.intent import (
    _is_push_intent,
    _is_commit_intent,
    _is_pull_intent,
    _extract_commit_msg,
    _is_cplan_intent,
    _extract_cplan_task,
)
from tools.claude_cli import is_available as claude_available
from tools import register_mcp_tools


# ── CSS ───────────────────────────────────────────────────────────
# 모든 영역 배경을 transparent 로 두어 터미널 기본 배경이 그대로 비치게 함.
# scrollbar 색은 대비용 최소 dim 값만 유지.
CSS = '''
Screen {
    background: transparent;
    layout: vertical;
}

#output {
    height: 1fr;
    padding: 0 2;
    scrollbar-size: 1 1;
    background: transparent;
}

#status-bar {
    height: 1;
    background: transparent;
    color: #555555;
    padding: 0 3;
}

#input-container {
    height: auto;
    min-height: 4;
    max-height: 16;
    background: transparent;
    layout: vertical;
    padding: 1 1 1 1;
}

#prompt-label {
    height: 1;
    background: transparent;
    color: #00aaff;
    text-style: bold;
    padding: 0 2;
    margin-bottom: 1;
}

#input-box {
    height: auto;
    min-height: 1;
    max-height: 12;
    background: transparent;
    border: none;
    padding: 0 2;
    scrollbar-size: 0 0;
}

#input-box:focus {
    border: none;
    background: transparent;
}

/* TextArea 내부 레이어도 투명 — cursor-line 강조/gutter 구분 모두 제거. */
TextArea#input-box > .text-area--cursor-line {
    background: transparent;
}

TextArea#input-box > .text-area--gutter {
    background: transparent;
}

TextArea#input-box > .text-area--cursor-gutter {
    background: transparent;
}
'''


# ── 입력 이벤트 + TextArea 커스텀 ─────────────────────────────────
class InputSubmitted(Message):
    '''_InputArea 가 Enter 로 submit 될 때 발송.'''
    def __init__(self, text: str):
        self.text = text
        super().__init__()


class _InputArea(TextArea):
    '''Textual Input 은 CJK wide char 커서 위치 계산 버그가 있음.
    TextArea 는 렌더 파이프라인이 달라 한글/CJK 정상 처리.

    바인딩:
    - Enter: submit (기본 newline 동작 override)
    - Shift+Enter: 줄바꿈 (multi-line 입력)
    - Ctrl+J: 줄바꿈 (OS 환경에 따라 Shift+Enter 가 막힐 때 대안)
    '''
    BINDINGS = [
        Binding('enter', 'submit_input', 'Submit', show=False, priority=True),
        Binding('shift+enter', 'newline', 'Newline', show=False),
        Binding('ctrl+j', 'newline', 'Newline', show=False),
    ]

    def action_submit_input(self) -> None:
        text = self.text
        self.text = ''
        self.post_message(InputSubmitted(text))

    def action_newline(self) -> None:
        # 현재 커서 위치에 개행 삽입
        self.insert('\n')


# ── TUI 스트림 — rich Console.file 을 가로채 RichLog로 흘림 ───────
class _TUIStream:
    '''Rich Console 이 file.write(str) 로 ANSI 포함 문자열을 한 번에 flush.
    여기서 받아 Text.from_ansi 로 파싱해 RichLog 에 넘긴다.

    thread-safe 를 위해 call_from_thread 로 메인 루프에 위임.
    '''
    def __init__(self, app, rich_log_getter):
        self.app = app
        self._get_rl = rich_log_getter
        self._buf = ''

    def write(self, s):
        if not s:
            return
        self._buf += s
        # Rich Console 은 한 번의 print 당 하나의 write 로 전체 출력 flush.
        # 줄바꿈이 포함되면 화면에 찍을 타이밍으로 판단.
        if '\n' in self._buf or len(self._buf) > 4096:
            self._flush()

    def flush(self):
        self._flush()

    def _flush(self):
        if not self._buf:
            return
        payload = self._buf
        self._buf = ''

        def _write():
            rl = self._get_rl()
            if rl is None:
                return
            try:
                at_bottom = rl.scroll_y >= max(0, rl.max_scroll_y - 3)
            except Exception:
                at_bottom = True
            rl.write(Text.from_ansi(payload.rstrip('\n')), scroll_end=False)
            if at_bottom:
                rl.scroll_end(animate=False)

        try:
            self.app.call_from_thread(_write)
        except RuntimeError:
            # 앱 종료 진행 중 — 조용히 버림
            pass


# ── Textual App ───────────────────────────────────────────────────
class HarnessApp(App):
    CSS = CSS
    BINDINGS = [
        Binding('ctrl+d', 'request_quit', '종료', show=False),
        Binding('ctrl+l', 'clear_log', '화면 지우기', show=False),
    ]

    def __init__(self, working_dir: str, profile: dict, args):
        super().__init__()
        self.working_dir = working_dir
        self.profile = profile
        self.args = args
        self.session_msgs: list = []
        self.undo_count: int = 0
        self._mcp_clients: dict = {}
        self._agent_running = False
        # confirm 다이얼로그 공용 state (write / bash / Confirm.ask 공통)
        self._confirm_event: threading.Event | None = None
        self._confirm_result: bool = False
        self._awaiting_confirm = False
        # 스트리밍 중인 미완성 라인 (assistant 토큰)
        self._stream_buf = ''
        self._stream_lock = threading.Lock()

        # TUI 모드 전환용 원본 백업 (exit 시 복원)
        self._orig_cb = {}
        self._orig_file = None
        self._orig_confirm_ask = None

    # ── 초기 세션 resume ──────────────────────────────────────────
    def _maybe_resume(self):
        if getattr(self.args, 'resume', False):
            data = sess.load_latest(self.working_dir)
            if data:
                self.session_msgs = data['messages']
                self.working_dir = data.get('working_dir', self.working_dir)
                turns = len([m for m in self.session_msgs if m['role'] == 'user'])
                self._rl_write(Text(f'  이전 세션 재개 ({turns}턴)\n', style='dim'))

    # ── compose ────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        yield RichLog(id='output', highlight=False, markup=True, wrap=True)
        yield Static('', id='status-bar')
        with Vertical(id='input-container'):
            yield Static(self._prompt_label(), id='prompt-label')
            yield _InputArea(id='input-box', show_line_numbers=False, soft_wrap=True)

    def on_mount(self):
        self._install_redirects()
        self._maybe_resume()
        self._print_welcome()
        self._update_status()
        # MCP 서버 부팅 (blocking — UI 뜨기 전 마무리)
        if self.profile.get('mcp_servers'):
            self._mcp_clients = _start_mcp_servers(self.profile)
            if self._mcp_clients:
                registered = register_mcp_tools(self._mcp_clients)
                if registered:
                    self._rl_write(Text(f'  MCP 툴 등록: {len(registered)}개\n', style='dim'))
        if self.profile.get('auto_index'):
            threading.Thread(target=self._auto_sync_bg, daemon=True).start()
        self.call_after_refresh(self._focus_input)

    def on_unmount(self):
        self._uninstall_redirects()
        for client in self._mcp_clients.values():
            try:
                client.stop()
            except Exception:
                pass

    # ── Rich 리디렉션 설치 / 해제 ─────────────────────────────────
    def _install_redirects(self):
        '''cli.render.console.file 교체 + cli.callbacks 콜백 교체 +
        rich.prompt.Confirm.ask monkey-patch.'''
        self._orig_file = _render.console.file
        stream = _TUIStream(self, lambda: self._safe_rl())
        _render.console.file = stream
        # Textual 화면과 겹치지 않도록 Console 이 terminal 감지 못하게 강제
        _render.console._force_terminal = True

        # callbacks 교체 (get_attr 동작하는 심볼만)
        self._orig_cb['on_token'] = _cb.on_token
        self._orig_cb['on_tool'] = _cb.on_tool
        self._orig_cb['confirm_write'] = _cb.confirm_write
        self._orig_cb['confirm_bash'] = _cb.confirm_bash
        self._orig_cb['_flush_tokens'] = _cb._flush_tokens
        _cb.on_token = self._on_token_tui
        _cb.on_tool = self._on_tool_tui
        _cb.confirm_write = self._confirm_write
        _cb.confirm_bash = self._confirm_bash
        _cb._flush_tokens = lambda: None  # TUI는 spinner 사용 안 함

        # Confirm.ask monkey-patch — 모든 Confirm.ask 호출이 TUI 다이얼로그로
        self._orig_confirm_ask = rich.prompt.Confirm.ask

        def _tui_ask(cls, prompt='', *, default=False, **kwargs):
            # Rich Text 또는 markup 을 평문으로 압축
            try:
                from rich.console import Console as _C
                import io
                buf = io.StringIO()
                _C(file=buf, force_terminal=False).print(prompt, end='')
                plain = buf.getvalue().strip() or '계속할까요?'
            except Exception:
                plain = str(prompt) if prompt else '계속할까요?'
            return self._ask_yes_no(plain, default=default)
        rich.prompt.Confirm.ask = classmethod(_tui_ask)

    def _uninstall_redirects(self):
        if self._orig_file is not None:
            _render.console.file = self._orig_file
        for k, v in self._orig_cb.items():
            setattr(_cb, k, v)
        if self._orig_confirm_ask is not None:
            rich.prompt.Confirm.ask = self._orig_confirm_ask

    # ── RichLog 헬퍼 ──────────────────────────────────────────────
    def _safe_rl(self):
        try:
            return self.query_one('#output', RichLog)
        except Exception:
            return None

    def _rl_write(self, content):
        rl = self._safe_rl()
        if rl is None:
            return
        try:
            at_bottom = rl.scroll_y >= max(0, rl.max_scroll_y - 3)
        except Exception:
            at_bottom = True
        rl.write(content, scroll_end=False)
        if at_bottom:
            rl.scroll_end(animate=False)

    def _output(self, *args):
        '''스레드에서 호출되는 출력. 메인 루프로 위임.'''
        def _write():
            for a in args:
                self._rl_write(a)
        try:
            self.call_from_thread(_write)
        except RuntimeError:
            pass

    def _flush_stream(self):
        with self._stream_lock:
            remaining = self._stream_buf
            self._stream_buf = ''
        if remaining:
            self._rl_write(Text(remaining))

    # ── 상태 ─────────────────────────────────────────────────────
    def _prompt_label(self) -> str:
        short = self._short_dir(self.working_dir)
        turns = len([m for m in self.session_msgs if m['role'] == 'user'])
        return f' {short} [{turns}] ❯ '

    def _update_status(self):
        try:
            used = sum(len(m.get('content') or '') for m in self.session_msgs) // 4
            total = config.CONTEXT_WINDOW
            pct = int(used / total * 100) if total else 0
            mode = config.APPROVAL_MODE
            claude = 'claude ✓' if claude_available() else 'claude ✗'
            self.query_one('#status-bar', Static).update(
                f' {config.MODEL}  ·  ctx {pct}%  ·  mode {mode}  ·  {claude}'
            )
        except Exception:
            pass

    def _refresh_prompt(self):
        try:
            self.query_one('#prompt-label', Static).update(self._prompt_label())
        except Exception:
            pass

    @staticmethod
    def _short_dir(path: str) -> str:
        home = os.path.expanduser('~')
        if path.startswith(home):
            path = '~' + path[len(home):]
        parts = path.split(os.sep)
        return os.sep.join(['…'] + parts[-2:]) if len(parts) > 3 else path

    def _focus_input(self):
        try:
            self.query_one('#input-box', _InputArea).focus()
        except Exception:
            pass

    # ── 시작 화면 / auto sync ─────────────────────────────────────
    def _print_welcome(self):
        idx_str = ('[green]indexed[/green]' if self._is_indexed()
                   else '[yellow]not indexed[/yellow]')
        claude_str = ('[green]claude ✓[/green]' if claude_available()
                      else '[dim]claude ✗[/dim]')
        self._rl_write(Panel(
            Text.assemble(
                (config.MODEL, 'bold cyan'),
                ('  ·  ', 'dim'),
                (self._short_dir(self.working_dir), 'dim white'),
                '\n',
                Text.from_markup(f'{idx_str}  {claude_str}'),
            ),
            box=box.ROUNDED,
            border_style='dim cyan',
            padding=(0, 2),
        ))
        self._rl_write(Text('  / 명령어  ·  @claude 질문  ·  /help 도움말\n', style='dim'))

    def _is_indexed(self) -> bool:
        try:
            import context as _ctx
            return _ctx.is_indexed(self.working_dir)
        except Exception:
            return False

    def _auto_sync_bg(self):
        try:
            _auto_sync(self.working_dir)
        except Exception as e:
            self._output(Text(f'  auto-sync 오류: {e}\n', style='yellow'))
        self.call_from_thread(self._update_status)

    # ── 입력 처리 ─────────────────────────────────────────────────
    @on(InputSubmitted)
    def handle_input(self, event: InputSubmitted):
        text = event.text.strip()
        # _InputArea.action_submit_input 이 이미 text 를 비움
        if not text:
            return

        # 확인 다이얼로그 대기 중이면 y/n 파싱 후 이벤트 set
        if self._awaiting_confirm:
            self._confirm_result = text.lower() in ('y', 'yes', 'ㅛ', '1', 'true')
            self._awaiting_confirm = False
            if self._confirm_event:
                self._confirm_event.set()
            return

        if self._agent_running:
            self._rl_write(Text('  ⚠  에이전트 실행 중입니다\n', style='yellow'))
            return

        # 에코
        turns = len([m for m in self.session_msgs if m['role'] == 'user'])
        self._rl_write(Text(f'\n❯ [{turns}] {text}', style='bold cyan'))

        # @claude 분기
        if text.startswith('@claude '):
            query = text[8:].strip()
            threading.Thread(
                target=self._run_claude_thread,
                args=(query,),
                daemon=True,
            ).start()
            return

        # /quit
        if text in ('/quit', '/exit', '/q'):
            self.action_request_quit()
            return

        # 슬래시
        if text.startswith('/'):
            threading.Thread(
                target=self._run_slash_thread,
                args=(text,),
                daemon=True,
            ).start()
            return

        # 자연어 git 의도
        if _is_push_intent(text):
            msg = _extract_commit_msg(text)
            if msg or _is_commit_intent(text):
                cmd = f'/commit {msg}' if msg else '/commit'
                threading.Thread(target=self._run_slash_thread, args=(cmd,), daemon=True).start()
            threading.Thread(target=self._run_slash_thread, args=('/push',), daemon=True).start()
            return
        if _is_pull_intent(text):
            threading.Thread(target=self._run_slash_thread, args=('/pull',), daemon=True).start()
            return
        if _is_commit_intent(text):
            msg = _extract_commit_msg(text)
            cmd = f'/commit {msg}' if msg else '/commit'
            threading.Thread(target=self._run_slash_thread, args=(cmd,), daemon=True).start()
            return

        # 자연어 cplan
        if _is_cplan_intent(text):
            task = _extract_cplan_task(text)
            threading.Thread(target=self._run_slash_thread, args=(f'/cplan {task}',), daemon=True).start()
            return

        # 기본: agent
        threading.Thread(target=self._run_agent_thread, args=(text,), daemon=True).start()

    # ── agent 실행 ───────────────────────────────────────────────
    def _set_running(self, running: bool):
        def _upd():
            self._agent_running = running
            try:
                inp = self.query_one('#input-box', _InputArea)
                inp.disabled = running
            except Exception:
                pass
            # TextArea 에는 placeholder 가 없어 prompt-label 을 힌트용으로 전환
            self._set_prompt_hint('처리 중...' if running else None)
            if not running:
                self.call_after_refresh(self._focus_input)
            self._refresh_prompt()
            self._update_status()
        try:
            self.call_from_thread(_upd)
        except RuntimeError:
            pass

    def _set_prompt_hint(self, hint: str | None):
        '''prompt-label 영역에 임시 힌트 표시. None 이면 기본 디렉토리 라벨.'''
        try:
            if hint is None:
                self.query_one('#prompt-label', Static).update(self._prompt_label())
            else:
                self.query_one('#prompt-label', Static).update(f' {hint}')
        except Exception:
            pass

    def _run_agent_thread(self, user_input: str, plan_mode: bool = False):
        self._set_running(True)
        self._output(Rule(style='dim'), Text())
        try:
            snippets = get_context_snippets(user_input, self.working_dir, self.profile)
            _, self.session_msgs = agent.run(
                user_input,
                session_messages=self.session_msgs,
                working_dir=self.working_dir,
                profile=self.profile,
                context_snippets=snippets,
                plan_mode=plan_mode,
                on_token=self._on_token_tui,
                on_tool=self._on_tool_tui,
                on_thought=self._on_thought_tui,
                on_thought_end=self._on_thought_end_tui,
                confirm_write=self._confirm_write if self.profile.get('confirm_writes', True) else None,
                confirm_bash=self._confirm_bash if self.profile.get('confirm_bash', True) else None,
                hooks=self.profile.get('hooks', {}),
            )
        except Exception as e:
            self._output(Text(f'\n  ✗ 오류: {e}\n', style='bold red'))
        try:
            self.call_from_thread(self._flush_stream)
        except RuntimeError:
            pass
        self._output(Text(), Rule(style='dim'), Text())
        self._set_running(False)

    def _run_claude_thread(self, query: str):
        self._set_running(True)
        try:
            _run_claude_cli(
                query,
                session_msgs=self.session_msgs,
                working_dir=self.working_dir,
                model=self.profile.get('claude_model') or None,
            )
        except Exception as e:
            self._output(Text(f'\n  ✗ {e}\n', style='bold red'))
        self._set_running(False)

    def _run_slash_thread(self, cmd: str):
        self._set_running(True)
        try:
            self.session_msgs, self.working_dir, self.undo_count = _slash.handle_slash(
                cmd,
                self.session_msgs,
                self.working_dir,
                self.profile,
                self.undo_count,
                run_agent=self._run_agent_for_core,
                run_agent_ephemeral=self._run_agent_ephemeral,
                ask_claude=self._ask_claude_for_core,
                confirm_execute=self._confirm_execute_for_core,
            )
            if cmd.startswith('/cd'):
                self.profile = prof.load(self.working_dir)
        except Exception as e:
            self._output(Text(f'\n  ✗ 슬래시 오류: {e}\n', style='bold red'))
        self._set_running(False)

    # ── handle_slash DI 콜백들 ────────────────────────────────────
    def _run_agent_for_core(self, user_input, *, plan_mode=False, context_snippets=''):
        '''harness_core.dispatch → /plan / /cplan 실행 시 에이전트 호출.'''
        self._output(Rule(style='dim'), Text())
        try:
            _, self.session_msgs = agent.run(
                user_input,
                session_messages=self.session_msgs,
                working_dir=self.working_dir,
                profile=self.profile,
                context_snippets=context_snippets,
                plan_mode=plan_mode,
                on_token=self._on_token_tui,
                on_tool=self._on_tool_tui,
                on_thought=self._on_thought_tui,
                on_thought_end=self._on_thought_end_tui,
                confirm_write=self._confirm_write if self.profile.get('confirm_writes', True) else None,
                confirm_bash=self._confirm_bash if self.profile.get('confirm_bash', True) else None,
                hooks=self.profile.get('hooks', {}),
            )
        except Exception as e:
            self._output(Text(f'\n  ✗ 오류: {e}\n', style='bold red'))
        try:
            self.call_from_thread(self._flush_stream)
        except RuntimeError:
            pass
        self._output(Text())

    def _run_agent_ephemeral(self, user_input, *, system_prompt, working_dir, profile):
        '''/improve, /learn 임시 세션.'''
        session = [{'role': 'system', 'content': system_prompt}]
        self._output(Rule(style='dim'), Text())
        try:
            agent.run(
                user_input,
                session_messages=session,
                working_dir=working_dir,
                profile=profile,
                on_token=self._on_token_tui,
                on_tool=self._on_tool_tui,
                on_thought=self._on_thought_tui,
                on_thought_end=self._on_thought_end_tui,
                confirm_write=self._confirm_write if profile.get('confirm_writes', True) else None,
                confirm_bash=self._confirm_bash if profile.get('confirm_bash', True) else None,
                hooks=profile.get('hooks', {}),
            )
        except Exception as e:
            self._output(Text(f'\n  ✗ 오류: {e}\n', style='bold red'))
        try:
            self.call_from_thread(self._flush_stream)
        except RuntimeError:
            pass

    def _ask_claude_for_core(self, prompt):
        '''/cplan phase 1 — Claude 플랜 수집 (스트리밍).'''
        from tools.claude_cli import ask as _ask
        collected = []
        self._output(Rule('[bold blue]Claude[/bold blue]', style='blue dim', align='left'))

        def _tok(line):
            collected.append(line)
            self._output(Text(line))
        try:
            _ask(prompt, on_token=_tok)
        except Exception as e:
            self._output(Text(f'  ✗ {e}\n', style='bold red'))
            return ''
        self._output(Rule(style='dim'))
        return ''.join(collected).strip()

    def _confirm_execute_for_core(self, plan_text, task):
        '''/cplan phase 2 — 사용자 확인.'''
        return self._ask_yes_no('위 플랜으로 로컬 모델이 실행할까요?', default=True)

    # ── TUI 콜백 ──────────────────────────────────────────────────
    def _on_token_tui(self, token: str):
        '''토큰을 버퍼에 모으고 줄바꿈을 만날 때마다 RichLog 에 append.

        이전 버전은 _stream_buf 를 별도 Static(#stream-line, 하단) 에 갱신
        했는데 줄바꿈 시 완성 라인이 RichLog(상단)로 "순간이동"하는 시각
        점프가 발생. RichLog 에만 라인 단위로 쓰면 연속된 흐름이 된다.
        '''
        def _write():
            with self._stream_lock:
                self._stream_buf += token
                if '\n' not in self._stream_buf:
                    return
                lines = self._stream_buf.split('\n')
                complete = lines[:-1]
                self._stream_buf = lines[-1]
            for line in complete:
                self._rl_write(Text(line))
        try:
            self.call_from_thread(_write)
        except RuntimeError:
            pass

    def _on_tool_tui(self, name: str, args: dict, result):
        from cli.render import _tool_meta_for, _tool_result_hint
        label, style, arg_fn = _tool_meta_for(name)
        arg_str = arg_fn(args)
        if result is None:
            self._output(Text.assemble(
                ('\n  ● ', 'bold'),
                (label, style),
                ('  ', ''),
                (arg_str, 'dim'),
                ('\n', ''),
            ))
        else:
            hint = _tool_result_hint(name, result)
            if result.get('ok'):
                self._output(Text.assemble(
                    ('  ⎿  ', 'dim'),
                    ('✓ ', 'green'),
                    (hint, 'dim'),
                    ('\n', ''),
                ))
            else:
                self._output(Text.assemble(
                    ('  ⎿  ', 'dim'),
                    ('✗ ', 'bold red'),
                    (hint, 'bold red'),
                    ('\n', ''),
                ))

    def _on_thought_tui(self, token: str):
        # thinking 은 화면에 안 찍고 세션에만 보관 (agent.py 가 저장).
        # MVP: 나중에 실시간 dim italic 스트리밍 추가 여지.
        pass

    def _on_thought_end_tui(self, text: str, duration: float, tokens: int):
        self._output(Text.assemble(
            ('  ▸ ', 'dim'),
            (f'{duration:.1f}초 동안 생각함 · {tokens} 토큰  ', 'dim'),
            ('/think 로 펼치기', 'dim italic'),
            ('\n', ''),
        ))

    # ── 확인 다이얼로그 (write / bash / Confirm.ask 공용) ────────
    def _ask_yes_no(self, prompt: str, *, default: bool = False) -> bool:
        '''스레드에서 호출. 입력창에 프롬프트를 띄우고 submit 대기.'''
        event = threading.Event()
        self._confirm_event = event
        self._confirm_result = default

        def _show():
            self._awaiting_confirm = True
            self._rl_write(Text.assemble(
                ('\n  ', ''),
                (prompt, 'bold'),
                (f'  → y/n (기본 {"y" if default else "n"})', 'dim'),
                ('\n', ''),
            ))
            self._set_prompt_hint(f'{prompt} (y/n)')
            try:
                inp = self.query_one('#input-box', _InputArea)
                inp.disabled = False
                self.call_after_refresh(self._focus_input)
            except Exception:
                pass
        try:
            self.call_from_thread(_show)
        except RuntimeError:
            return default
        event.wait(timeout=120)
        return self._confirm_result

    def _confirm_write(self, path: str, content: str = None) -> bool:
        # diff 미리보기는 MVP에서 생략 (향후 dialog로). 현재는 y/n만.
        return self._ask_yes_no(f'Write {path}', default=False)

    def _confirm_bash(self, command: str) -> bool:
        return self._ask_yes_no(f'Run {command[:80]}', default=False)

    # ── 액션 ──────────────────────────────────────────────────────
    def action_request_quit(self):
        # 세션 자동 저장 없음 — 원하면 /save 사전 호출
        self.exit()

    def action_clear_log(self):
        rl = self._safe_rl()
        if rl is not None:
            rl.clear()


# ── 진입점 ────────────────────────────────────────────────────────
def run_tui(working_dir: str, profile: dict, args) -> None:
    app = HarnessApp(working_dir, profile, args)
    app.run()
