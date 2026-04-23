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
    /* 남은 공간 차지 (1fr). 최소 5줄은 확보해 작은 터미널도 안정.
       border-bottom 으로 입력 영역과의 경계선 한 줄만 유지. */
    height: 1fr;
    min-height: 5;
    padding: 0 2;
    scrollbar-size: 1 1;
    background: transparent;
    border-bottom: solid #1a3a5a;
}

#status-bar {
    height: 1;
    background: transparent;
    color: #4a6a8a;
    padding: 0 3;
}

#input-container {
    /* label(1) + margin(1) + input-box(최대 6) + hints(최대 6) + padding(2)
       ≈ 16. 이 이상 커지지 않아 output 이 절대 짓눌리지 않음. */
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
    color: #5ab6ff;
    text-style: bold;
    padding: 0 2;
    margin-bottom: 1;
}

#input-box {
    /* 입력 6줄까지 표시. 그 이상은 TextArea 내부 스크롤. */
    height: auto;
    min-height: 1;
    max-height: 6;
    background: transparent;
    border: none;
    padding: 0 2;
    scrollbar-size: 0 0;
}

#input-box:focus {
    border: none;
    background: transparent;
}

#slash-hints {
    /* 기본 0 높이(없을 땐 공간 안 차지). / 입력 시 5~6줄 나타남. */
    height: auto;
    min-height: 0;
    max-height: 6;
    background: transparent;
    color: #4a6a8a;
    padding: 0 2;
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


# ── 스피너 프레임 ─────────────────────────────────────────────────
SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']


# ── 파일 확장자 → pygments lexer 이름 (rich.syntax 용) ────────────
_LEXER_BY_EXT = {
    '.py': 'python', '.pyi': 'python',
    '.js': 'javascript', '.mjs': 'javascript', '.jsx': 'jsx',
    '.ts': 'typescript', '.tsx': 'tsx',
    '.html': 'html', '.htm': 'html',
    '.css': 'css', '.scss': 'scss', '.sass': 'sass',
    '.json': 'json', '.jsonc': 'json',
    '.toml': 'toml', '.yaml': 'yaml', '.yml': 'yaml',
    '.md': 'markdown', '.markdown': 'markdown',
    '.sh': 'bash', '.bash': 'bash', '.zsh': 'bash',
    '.go': 'go', '.rs': 'rust', '.rb': 'ruby',
    '.sql': 'sql', '.xml': 'xml',
    '.c': 'c', '.h': 'c', '.cpp': 'cpp', '.hpp': 'cpp',
    '.java': 'java', '.kt': 'kotlin',
    '.swift': 'swift', '.dart': 'dart',
    '.lua': 'lua', '.php': 'php',
    '.dockerfile': 'dockerfile',
}


def _lexer_for_path(path: str) -> str:
    '''확장자에서 pygments lexer 이름 추출. 모르면 text.'''
    ext = os.path.splitext(path.lower())[1]
    return _LEXER_BY_EXT.get(ext, 'text')


def _render_diff_body(diff: list, max_lines: int = 60):
    '''unified_diff 결과를 Claude Code 스타일 Renderable 로 변환.

    - 추가 라인: 녹색 배경 + `+` 마커 + 라인 번호(new)
    - 삭제 라인: 붉은 배경 + `-` 마커 + 라인 번호(old)
    - 컨텍스트: dim + 양쪽 라인 번호 중 new 쪽 표시
    - @@ 헤더: cyan dim, 이후 라인 번호 재설정
    - 파일 헤더(---/+++) 는 Panel title 로 대체하므로 스킵

    반환: rich.console.Group. Panel 에 직접 넣으면 됨.
    '''
    import re
    from rich.console import Group
    from rich.text import Text

    ADD_BG = 'on #0a2a0a'
    DEL_BG = 'on #3a0f0f'
    CONTEXT_STYLE = 'dim'
    MARKER_ADD = 'bold green'
    MARKER_DEL = 'bold red'
    LN_STYLE = 'dim #4a6a8a'

    rendered: list = []
    old_ln = 0
    new_ln = 0
    count = 0

    for line in diff:
        if line.startswith('---') or line.startswith('+++'):
            continue
        if count >= max_lines:
            break
        if line.startswith('@@'):
            m = re.match(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
            if m:
                old_ln = int(m.group(1))
                new_ln = int(m.group(2))
            rendered.append(Text(line, style='dim cyan'))
            count += 1
            continue
        if line.startswith('+') and not line.startswith('+++'):
            content = line[1:]
            t = Text(no_wrap=True)
            t.append(f'{new_ln:>4} ', style=LN_STYLE)
            t.append('+ ', style=MARKER_ADD)
            t.append(content.ljust(160), style=ADD_BG)
            rendered.append(t)
            new_ln += 1
        elif line.startswith('-') and not line.startswith('---'):
            content = line[1:]
            t = Text(no_wrap=True)
            t.append(f'{old_ln:>4} ', style=LN_STYLE)
            t.append('- ', style=MARKER_DEL)
            t.append(content.ljust(160), style=DEL_BG)
            rendered.append(t)
            old_ln += 1
        else:
            # 컨텍스트 (앞에 공백 또는 없음)
            content = line[1:] if line.startswith(' ') else line
            t = Text(no_wrap=True)
            t.append(f'{new_ln:>4} ', style=LN_STYLE)
            t.append('  ', style='')
            t.append(content, style=CONTEXT_STYLE)
            rendered.append(t)
            old_ln += 1
            new_ln += 1
        count += 1

    return Group(*rendered)


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
    - Tab: 슬래시 자동완성 (단일 매칭이면 완성, 여러 개면 공통 prefix)
    '''
    BINDINGS = [
        Binding('enter', 'submit_input', 'Submit', show=False, priority=True),
        Binding('shift+enter', 'newline', 'Newline', show=False),
        Binding('ctrl+j', 'newline', 'Newline', show=False),
        Binding('tab', 'complete_slash', 'Complete', show=False, priority=True),
    ]

    def action_submit_input(self) -> None:
        text = self.text
        self.text = ''
        self.post_message(InputSubmitted(text))

    def action_newline(self) -> None:
        # 현재 커서 위치에 개행 삽입
        self.insert('\n')

    def action_complete_slash(self) -> None:
        '''Tab — 현재 라인이 `/word` 로 시작하면 매칭 슬래시로 완성.
        매칭 여러 개면 공통 prefix 까지 확장. 매칭 없으면 탭 무시.
        '''
        from cli.render import SLASH_COMMANDS
        txt = self.text
        if not txt.startswith('/'):
            return
        # 현재 입력 전체를 커맨드 prefix 로 간주 (공백 뒤 arg 는 제외)
        parts = txt.split(maxsplit=1)
        word = parts[0]
        # 매칭
        candidates = [c for c in SLASH_COMMANDS if c.startswith(word)]
        if not candidates:
            return
        if len(candidates) == 1:
            # 공백 추가해 arg 입력 유도
            completed = candidates[0] + ' '
            rest = parts[1] if len(parts) > 1 else ''
            self.text = completed + rest
        else:
            # 공통 prefix 계산
            prefix = os.path.commonprefix(candidates)
            if len(prefix) > len(word):
                rest = parts[1] if len(parts) > 1 else ''
                self.text = prefix + (' ' + rest if rest else '')


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

        # call_from_thread 는 "다른 스레드" 에서 메인 루프에 위임할 때만 유효.
        # on_mount / 이벤트 핸들러 등 이미 루프 스레드에서 호출되면 RuntimeError.
        # 그 경우 바로 실행. 앱 종료 중 이라면 rl 이 None 이라 noop.
        try:
            self.app.call_from_thread(_write)
        except RuntimeError:
            try:
                _write()
            except Exception:
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
        # 턴 시작 시 리셋되는 assistant 헤더 on-demand 출력 플래그
        self._assistant_header_printed = False
        # 툴 실행 시작 시각 — _on_tool_tui 에서 elapsed 계산
        self._tool_start_ts = 0.0
        # 미등록 툴 수집 — turn 끝에 _suggest_unknown_tools_tui 호출
        self._unknown_tools: list[tuple[str, dict]] = []
        # 스피너 — set_interval 타이머가 status-bar 앞에 회전 프레임을 찍음
        self._spinner_timer = None
        self._spinner_frame_idx = 0
        # 코드 블록 감지 — ```lang ... ``` 을 Syntax Panel 로 렌더
        self._code_fence_open = False
        self._code_lang = ''
        self._code_buf: list[str] = []

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
            # 슬래시 힌트는 입력창 바로 아래
            yield Static('', id='slash-hints')

    def on_mount(self):
        self._install_redirects()
        # 배너 — cli.setup.print_banner 는 console.out 으로 ANSI 그라데이션을
        # 찍는데, _install_redirects 가 console.file → _TUIStream 이라
        # Text.from_ansi 로 파싱되어 RichLog 에 그대로 흐른다.
        from cli.setup import print_banner
        try:
            print_banner()
        except Exception:
            # 배너 렌더 실패해도 본 UI 는 살아야 함
            pass
        self._print_welcome()
        self._maybe_resume()
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
        '''스레드 또는 메인 루프 어느 쪽에서 호출되든 RichLog 에 출력.'''
        def _write():
            for a in args:
                self._rl_write(a)
        try:
            self.call_from_thread(_write)
        except RuntimeError:
            # 이미 루프 스레드 — 직접 호출
            try:
                _write()
            except Exception:
                pass

    def _flush_stream(self):
        with self._stream_lock:
            remaining = self._stream_buf
            self._stream_buf = ''
        if remaining:
            # assistant 헤더가 아직이면 여기서라도 찍고 잔여 라인 flush
            if not self._assistant_header_printed:
                self._rl_write(Text.assemble(
                    ('● ', 'bold'),
                    (config.MODEL, 'bold orange3'),
                ))
                self._assistant_header_printed = True
            # 코드 펜스 안이면 버퍼에 쌓고, 밖이면 평문
            if self._code_fence_open:
                self._code_buf.append(remaining)
            else:
                self._rl_write(Text('  ' + remaining))
        # 코드 펜스 미종료 상태로 스트림 끝났으면 버퍼 내용이라도 Panel 로 렌더
        if self._code_fence_open:
            self._flush_code_block()

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
            if self._agent_running:
                frame = SPINNER_FRAMES[self._spinner_frame_idx % len(SPINNER_FRAMES)]
                prefix = f'[cyan]{frame}[/cyan] 처리 중  ·  '
            else:
                prefix = ''
            self.query_one('#status-bar', Static).update(
                f' {prefix}{config.MODEL}  ·  ctx {pct}%  ·  mode {mode}  ·  {claude}'
            )
        except Exception:
            pass

    def _spinner_tick(self):
        '''set_interval 콜백 — status-bar 의 회전 프레임 진행.'''
        self._spinner_frame_idx += 1
        self._update_status()

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
    @on(TextArea.Changed, '#input-box')
    def on_input_changed(self, event):
        '''TextArea 내용이 바뀔 때마다 슬래시 힌트 갱신.'''
        self._update_slash_hints(event.text_area.text)

    def _update_slash_hints(self, text: str):
        '''`/` 로 시작하면 매칭 슬래시 목록을 #slash-hints 에 표시.
        아니면 빈 문자열. 최대 8줄.'''
        from cli.render import SLASH_COMMANDS
        try:
            hints = self.query_one('#slash-hints', Static)
        except Exception:
            return
        if not text.startswith('/'):
            hints.update('')
            return
        word = text.split(maxsplit=1)[0]
        matches = [(c, d) for c, d in SLASH_COMMANDS.items() if c.startswith(word)]
        if not matches:
            hints.update('[dim]일치하는 명령 없음[/dim]')
            return
        # 최대 5줄 — 청색 계열 cmd + dim 설명
        lines = []
        for cmd, desc in matches[:5]:
            short_desc = desc.split('  ex)')[0]
            lines.append(f'[bold #5ab6ff]{cmd:<10}[/bold #5ab6ff] [#4a6a8a]{short_desc}[/#4a6a8a]')
        if len(matches) > 5:
            lines.append(f'[#3a5a7a]... 외 {len(matches) - 5}개 (Tab 으로 완성)[/#3a5a7a]')
        hints.update('\n'.join(lines))

    @on(InputSubmitted)
    def handle_input(self, event: InputSubmitted):
        text = event.text.strip()
        # _InputArea.action_submit_input 이 이미 text 를 비움 + 슬래시 힌트 클리어
        try:
            self.query_one('#slash-hints', Static).update('')
        except Exception:
            pass
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
            # 스피너 타이머 start/stop — status-bar 회전 프레임
            if running:
                self._spinner_frame_idx = 0
                if self._spinner_timer is None:
                    self._spinner_timer = self.set_interval(0.1, self._spinner_tick)
            else:
                if self._spinner_timer is not None:
                    try:
                        self._spinner_timer.stop()
                    except Exception:
                        pass
                    self._spinner_timer = None
            # TextArea 에는 placeholder 가 없어 prompt-label 을 힌트용으로 전환
            self._set_prompt_hint('처리 중...' if running else None)
            if not running:
                self.call_after_refresh(self._focus_input)
            self._refresh_prompt()
            self._update_status()
        try:
            self.call_from_thread(_upd)
        except RuntimeError:
            try:
                _upd()
            except Exception:
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
        self._assistant_header_printed = False
        self._unknown_tools.clear()
        self._code_fence_open = False
        self._code_lang = ''
        self._code_buf.clear()
        self._output(Text())
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
                on_unknown_tool=self._on_unknown_tool_tui,
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
        self._suggest_unknown_tools_tui()
        self._output(Text())
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
        self._assistant_header_printed = False
        self._unknown_tools.clear()
        self._code_fence_open = False
        self._code_lang = ''
        self._code_buf.clear()
        self._output(Text())
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
                on_unknown_tool=self._on_unknown_tool_tui,
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
        self._suggest_unknown_tools_tui()
        self._output(Text())

    def _run_agent_ephemeral(self, user_input, *, system_prompt, working_dir, profile):
        '''/improve, /learn 임시 세션.'''
        session = [{'role': 'system', 'content': system_prompt}]
        self._output(Text())
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
        self._output(Text.assemble(('\n● Claude', 'bold blue'), ('\n', '')))

        def _tok(line):
            collected.append(line)
            self._output(Text(line))
        try:
            _ask(prompt, on_token=_tok)
        except Exception as e:
            self._output(Text(f'  ✗ {e}\n', style='bold red'))
            return ''
        self._output(Text())
        return ''.join(collected).strip()

    def _confirm_execute_for_core(self, plan_text, task):
        '''/cplan phase 2 — 사용자 확인.'''
        return self._ask_yes_no('위 플랜으로 로컬 모델이 실행할까요?', default=True)

    # ── TUI 콜백 ──────────────────────────────────────────────────
    def _on_token_tui(self, token: str):
        '''토큰을 버퍼에 모으고 줄바꿈을 만날 때마다 RichLog 에 append.

        ```lang ... ``` 코드 블록을 감지해 블록이 끝나면 Syntax Panel 로 렌더.
        평문 라인은 그대로 2칸 들여쓰기. 첫 라인 직전에 `● 모델명` 헤더.
        '''
        def _write():
            with self._stream_lock:
                self._stream_buf += token
                if '\n' not in self._stream_buf:
                    return
                lines = self._stream_buf.split('\n')
                complete = lines[:-1]
                self._stream_buf = lines[-1]
            if not self._assistant_header_printed:
                self._rl_write(Text.assemble(
                    ('● ', 'bold'),
                    (config.MODEL, 'bold orange3'),
                ))
                self._assistant_header_printed = True
            for line in complete:
                self._handle_assistant_line(line)
        try:
            self.call_from_thread(_write)
        except RuntimeError:
            try:
                _write()
            except Exception:
                pass

    def _handle_assistant_line(self, line: str):
        '''assistant 응답 한 라인 처리 — 코드 펜스 상태머신.'''
        stripped = line.strip()
        is_fence = stripped.startswith('```') or stripped.startswith('~~~')
        if self._code_fence_open:
            if is_fence:
                # 블록 종료 → Syntax Panel 로 한 번에 렌더
                self._flush_code_block()
            else:
                self._code_buf.append(line)
        else:
            if is_fence:
                self._code_fence_open = True
                # ```html 또는 ``` 뒤 언어 추출
                self._code_lang = stripped.lstrip('`~').strip() or 'text'
                self._code_buf = []
            else:
                self._rl_write(Text('  ' + line))

    def _flush_code_block(self):
        '''코드 펜스 종료 시 버퍼 내용을 Syntax Panel 로 렌더.'''
        if not self._code_buf:
            self._code_fence_open = False
            self._code_lang = ''
            return
        from rich.syntax import Syntax
        from rich.panel import Panel
        code_text = '\n'.join(self._code_buf)
        try:
            body = Syntax(code_text, self._code_lang or 'text',
                          theme='ansi_dark', line_numbers=False,
                          word_wrap=False, background_color='default')
        except Exception:
            # 알 수 없는 lexer → 평문
            body = Syntax(code_text, 'text', theme='ansi_dark',
                          line_numbers=False, word_wrap=False,
                          background_color='default')
        title = f'[#5ab6ff]{self._code_lang}[/#5ab6ff]' if self._code_lang != 'text' else None
        self._rl_write(Panel(body, title=title, border_style='#1a3a5a', padding=(0, 1)))
        self._code_fence_open = False
        self._code_lang = ''
        self._code_buf = []

    def _on_tool_tui(self, name: str, args: dict, result):
        import time as _time
        from cli.render import _tool_meta_for, _tool_result_hint
        label, style, arg_fn = _tool_meta_for(name)
        arg_str = arg_fn(args)
        if result is None:
            self._tool_start_ts = _time.time()
            self._output(Text.assemble(
                ('\n  ● ', 'bold'),
                (label, style),
                ('  ', ''),
                (arg_str, 'dim'),
                ('\n', ''),
            ))
        else:
            elapsed = _time.time() - self._tool_start_ts
            elapsed_str = f' · {elapsed:.1f}s' if elapsed > 0.5 else ''
            hint = _tool_result_hint(name, result)
            if result.get('ok'):
                self._output(Text.assemble(
                    ('  ⎿  ', 'dim'),
                    ('✓ ', 'green'),
                    (hint, 'dim'),
                    (elapsed_str, 'dim'),
                    ('\n', ''),
                ))
            else:
                self._output(Text.assemble(
                    ('  ⎿  ', 'dim'),
                    ('✗ ', 'bold red'),
                    (hint, 'bold red'),
                    (elapsed_str, 'dim'),
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
        '''Claude Code 스타일 diff 미리보기 — Panel 안에 Syntax(diff) 렌더.

        pygments `diff` lexer 가 +/-/@@ 를 각각 green/red/cyan 으로 자동 하이라이트.
        새 파일은 diff 대신 내용 자체를 확장자 기반 syntax 로 그대로 보여줌.
        '''
        if content is not None:
            try:
                from rich.syntax import Syntax
                from rich.panel import Panel
                existing = os.path.exists(path)
                if existing:
                    with open(path, encoding='utf-8', errors='replace') as f:
                        old_lines = f.readlines()
                    title = f'[bold #5ab6ff]{path}[/bold #5ab6ff]'
                else:
                    old_lines = []
                    title = f'[bold #5ab6ff]{path}[/bold #5ab6ff] [dim](새 파일)[/dim]'

                if existing:
                    # 기존 파일 수정 → unified diff 를 Claude Code 스타일로 렌더
                    import difflib as _dl
                    new_lines = [l if l.endswith('\n') else l + '\n' for l in content.splitlines()]
                    diff = list(_dl.unified_diff(
                        old_lines, new_lines,
                        fromfile=path, tofile=path, lineterm='',
                    ))
                    if not diff:
                        self._output(Panel(
                            '[dim](변경 없음)[/dim]',
                            title=title, border_style='#1a3a5a', padding=(0, 1),
                        ))
                    else:
                        body = _render_diff_body(diff, max_lines=60)
                        extra = sum(1 for d in diff
                                    if not d.startswith('---') and not d.startswith('+++'))
                        subtitle = (f'[dim]... 외 {extra - 60}줄[/dim]'
                                    if extra > 60 else None)
                        self._output(Panel(body, title=title, subtitle=subtitle,
                                            border_style='#1a3a5a', padding=(0, 1)))
                else:
                    # 새 파일 → 확장자 기반 syntax 그대로
                    lexer = _lexer_for_path(path)
                    shown_content = '\n'.join(content.splitlines()[:60])
                    body = Syntax(shown_content, lexer, theme='ansi_dark',
                                  line_numbers=True, word_wrap=False, background_color='default')
                    total_lines = len(content.splitlines())
                    subtitle = (f'[dim]... 외 {total_lines - 60}줄[/dim]'
                                if total_lines > 60 else None)
                    self._output(Panel(body, title=title, subtitle=subtitle,
                                        border_style='#1a3a5a', padding=(0, 1)))
            except Exception:
                pass
        return self._ask_yes_no(f'Write {path}', default=False)

    def _confirm_bash(self, command: str) -> bool:
        return self._ask_yes_no(f'Run {command[:80]}', default=False)

    # ── 미등록 툴 ─────────────────────────────────────────────────
    def _on_unknown_tool_tui(self, name: str, args: dict = None):
        if not any(n == name for n, _ in self._unknown_tools):
            self._unknown_tools.append((name, args or {}))

    def _suggest_unknown_tools_tui(self):
        if not self._unknown_tools:
            return
        from cli.callbacks import _INSTALLABLE_TOOLS
        from cli.render import _infer_tool_purpose
        for name, args in self._unknown_tools:
            info = _INSTALLABLE_TOOLS.get(name)
            if info:
                module_file, pkg = info
                pkg_note = f'  (pip install {pkg})' if pkg else ''
                self._output(Text.assemble(
                    ('\n  ● ', 'bold'),
                    ('미등록 툴: ', 'yellow'),
                    (name, 'bold'),
                    (pkg_note, 'dim'),
                    ('\n    ', ''),
                    (f'tools/{module_file} 에 구현 후 tools/__init__.py 에 등록', 'dim'),
                    ('\n', ''),
                ))
            else:
                purpose, args_str = _infer_tool_purpose(name, args)
                self._output(Text.assemble(
                    ('\n  ● ', 'bold'),
                    ('미등록 툴 감지: ', 'yellow'),
                    (name, 'bold'),
                    ('\n    추정: ', ''),
                    (purpose, 'dim'),
                    ('\n    추가: ', ''),
                    (f'tools/{name}.py 구현 → tools/__init__.py 등록', 'dim'),
                    ('\n', ''),
                ))
        self._unknown_tools.clear()

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
