#!/usr/bin/env python3
'''Textual 기반 분리 입력창 UI'''
import os
import sys
import time
import threading

from textual.app import App, ComposeResult
from textual.widgets import RichLog, Input, Static
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual import on

from rich.rule import Rule
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.prompt import Confirm
from rich import box

import agent
import profile as prof
import context
import session as sess
from session.logger import read_recent
from session.analyzer import summarize_session, build_learn_prompt
from tools.improve import backup_sources, validate_python, read_sources, list_backups, restore_backup, HARNESS_DIR
import evolution
from tools.claude_cli import ask as claude_ask, is_available as claude_available

# ── CSS ───────────────────────────────────────────────────────────
CSS = '''
Screen {
    background: #0d0d0d;
    layout: vertical;
}

#output {
    height: 1fr;
    padding: 0 2;
    scrollbar-size: 1 1;
    scrollbar-color: #333333 #0d0d0d;
    background: #0d0d0d;
}

#stream-line {
    height: auto;
    min-height: 0;
    padding: 0 2;
    background: #0d0d0d;
    color: #e0e0e0;
}

#status-bar {
    height: 1;
    background: #111111;
    color: #555555;
    padding: 0 2;
}

#input-container {
    height: 6;
    background: #111111;
    border-top: solid #1e3a5f;
    layout: vertical;
}

#prompt-label {
    height: 2;
    background: #111111;
    color: #00aaff;
    text-style: bold;
    padding: 1 2 0 2;
}

#input-box {
    height: 2;
    background: transparent;
    border: none;
    padding: 0 2 1 2;
    color: #e0e0e0;
}

#input-box:focus {
    border: none;
    background: transparent;
}
'''

# ── 도구 메타 ─────────────────────────────────────────────────────
_TOOL_META = {
    'read_file':     ('Read',    '#00aaff', lambda a: a.get('path', '')),
    'write_file':    ('Write',   '#ffaa00', lambda a: a.get('path', '')),
    'list_files':    ('Glob',    '#00aaff', lambda a: a.get('pattern', '')),
    'run_command':   ('Run',     '#cc44ff', lambda a: a.get('command', '')[:70]),
    'run_python':    ('Python',  '#cc44ff', lambda a: a.get('code', '').split('\n')[0][:70]),
    'git_status':    ('Git',     '#00cc44', lambda _: 'status'),
    'git_diff':      ('Git',     '#00cc44', lambda a: 'diff' + (' --staged' if a.get('staged') else '')),
    'git_log':       ('Git',     '#00cc44', lambda a: f'log -{a.get("n", 10)}'),
    'git_diff_full': ('Git',     '#00cc44', lambda _: 'diff HEAD'),
    'search_web':    ('Search',  '#00cccc', lambda a: a.get('query', '')[:70]),
    'fetch_page':    ('Fetch',   '#00cccc', lambda a: a.get('url', '')[:70]),
}


def _tool_result_hint(name: str, result: dict) -> str:
    if not result.get('ok'):
        err = result.get('error') or result.get('stderr') or ''
        return err.strip()[:80]
    if name == 'read_file':
        return f'{result.get("content", "").count(chr(10)) + 1}줄'
    if name == 'write_file':
        return '저장됨'
    if name == 'list_files':
        return f'{len(result.get("files", []))}개'
    if name in ('run_command', 'run_python'):
        out = (result.get('stdout') or result.get('stderr') or '').strip()
        return out.split('\n')[0][:60] if out else f'exit {result.get("returncode", 0)}'
    if name.startswith('git_'):
        out = (result.get('output') or result.get('stdout') or '').strip()
        return out.split('\n')[0][:60] if out else 'ok'
    return 'ok'


# ── 슬래시 명령어 ─────────────────────────────────────────────────
SLASH_COMMANDS = {
    '/clear':    '대화 초기화',
    '/undo':     '마지막 질문·응답 취소',
    '/plan':     '로컬 모델 플랜 후 실행',
    '/cplan':    'Claude 플랜 → 로컬 실행',
    '/index':    '코드베이스 인덱싱',
    '/improve':  '하네스 자기 개선',
    '/learn':    '세션 → HARNESS.md 갱신',
    '/evolve':   '진화 엔진 실행',
    '/history':  '진화 이력',
    '/restore':  '백업 롤백',
    '/cd':       '디렉토리 변경',
    '/files':    '파일 트리',
    '/save':     '세션 저장',
    '/resume':   '세션 불러오기',
    '/sessions': '세션 목록',
    '/init':     '.harness.toml 생성',
    '/claude':   'Claude CLI 질문',
    '/help':     '도움말',
    '/quit':     '종료',
}

_IGNORE_DIRS = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'dist', 'build', '.next'}
_FILE_ICONS = {
    '.py': '🐍', '.js': '📜', '.ts': '📘', '.tsx': '📘',
    '.md': '📝', '.json': '📋', '.toml': '⚙', '.sh': '⚡',
    '.go': '🐹', '.rs': '🦀',
}
_CPLAN_TRIGGERS = [
    '클로드로 계획', '클로드가 계획', '클로드로 플랜', '클로드가 플랜',
    '클로드한테 계획', '클로드한테 플랜', '클로드가 설계', '클로드로 설계',
    'claude로 계획', 'claude가 계획', 'claude로 플랜', 'claude가 플랜',
    '클로드가 짜줘', '클로드로 짜줘', '클로드가 작성', '클로드가 먼저',
]

_INSTALLABLE_TOOLS = {
    'search_web': ('web.py', 'duckduckgo_search'),
    'fetch_page': ('web.py', None),
}

CPLAN_PROMPT_TMPL = '''\
다음 작업에 대한 실행 계획을 작성해줘.
작업 디렉토리: {working_dir}
작업: {task}

단계별 플랜 (번호 목록, 파일 명시, 핵심 로직 포함, 주의사항 언급):
로컬 코딩 모델이 이 플랜만 보고 바로 실행할 수 있도록.
'''

IMPROVE_SYSTEM = '''당신은 이 하네스 시스템의 자기 개선 전문가입니다.
실패 로그를 분석해 소스 코드를 개선하세요.
수정 후 py_compile로 검증하세요.'''

LEARN_SYSTEM = '''당신은 하네스의 자기학습 에이전트입니다.
세션 분석 결과를 바탕으로 HARNESS.md 파일을 개선하세요.
기존 내용 확인 후 중복 없이 수정하세요.'''


# ── Textual App ───────────────────────────────────────────────────
class HarnessApp(App):
    CSS = CSS
    BINDINGS = [
        Binding('ctrl+d', 'request_quit', '종료', show=False),
    ]

    def __init__(self):
        super().__init__()
        self.working_dir = os.getcwd()
        self.profile = prof.load(self.working_dir)
        self.session_msgs: list = []
        self.undo_count: int = 0
        self._agent_running = False
        self._confirm_event: threading.Event | None = None
        self._confirm_result: bool = False
        self._awaiting_confirm = False
        self._confirm_path = ''
        self._stream_buf = ''   # 현재 스트리밍 중인 미완성 줄
        self._stream_lock = threading.Lock()

    def compose(self) -> ComposeResult:
        yield RichLog(id='output', highlight=False, markup=True, wrap=True)
        yield Static('', id='stream-line')
        yield Static('', id='status-bar')
        with Vertical(id='input-container'):
            yield Static(self._prompt_label(), id='prompt-label')
            yield Input(placeholder='입력... (/ 명령어, @claude 질문)', id='input-box')

    def on_mount(self):
        self._update_status()
        self._print_welcome()
        if self.profile.get('auto_index'):
            threading.Thread(target=self._auto_sync, daemon=True).start()
        self.call_after_refresh(self._focus_input)

    def _focus_input(self):
        try:
            self.query_one('#input-box', Input).focus()
        except Exception:
            pass

    # ── 로깅 헬퍼 ─────────────────────────────────────────────────
    def _rl_write(self, content):
        try:
            rl = self.query_one('#output', RichLog)
            try:
                at_bottom = rl.scroll_y >= max(0, rl.max_scroll_y - 3)
            except Exception:
                at_bottom = True
            rl.write(content, scroll_end=False)
            if at_bottom:
                rl.scroll_end(animate=False)
        except Exception:
            pass

    def output(self, *args):
        def _write():
            for a in args:
                self._rl_write(a)
        self.call_from_thread(_write)

    def output_direct(self, *args):
        for a in args:
            self._rl_write(a)

    def _flush_stream(self):
        with self._stream_lock:
            remaining = self._stream_buf
            self._stream_buf = ''
        if remaining:
            self._rl_write(Text(remaining))
        self.query_one('#stream-line', Static).update('')

    # ── 상태 ──────────────────────────────────────────────────────
    def _prompt_label(self) -> str:
        short = self._short_dir(self.working_dir)
        turns = len([m for m in self.session_msgs if m['role'] == 'user'])
        return f' {short} [{turns}] ❯ '

    def _update_status(self):
        indexed = context.is_indexed(self.working_dir)
        idx = 'indexed' if indexed else 'not indexed'
        claude = 'claude ✓' if claude_available() else 'claude ✗'
        short = self._short_dir(self.working_dir)
        self.query_one('#status-bar', Static).update(
            f' {short}  ·  {idx}  ·  {claude}  ·  qwen2.5-coder:32b'
        )

    def _refresh_prompt(self):
        self.query_one('#prompt-label', Static).update(self._prompt_label())

    @staticmethod
    def _short_dir(path: str) -> str:
        home = os.path.expanduser('~')
        if path.startswith(home):
            path = '~' + path[len(home):]
        parts = path.split(os.sep)
        return os.sep.join(['…'] + parts[-2:]) if len(parts) > 3 else path

    # ── 시작 화면 ─────────────────────────────────────────────────
    def _print_welcome(self):
        indexed = context.is_indexed(self.working_dir)
        idx_str = '[green]indexed[/green]' if indexed else '[yellow]not indexed[/yellow]'
        claude_str = '[green]claude ✓[/green]' if claude_available() else '[dim]claude ✗[/dim]'
        self.output_direct(Panel(
            Text.assemble(
                ('qwen2.5-coder:32b', 'bold cyan'),
                ('  ·  ', 'dim'),
                (self._short_dir(self.working_dir), 'dim white'),
                '\n',
                Text.from_markup(f'{idx_str}  {claude_str}'),
            ),
            box=box.ROUNDED,
            border_style='dim cyan',
            padding=(0, 2),
        ))
        self.output_direct(Text('  / 명령어  ·  @claude 질문  ·  /help 도움말\n', style='dim'))

    # ── 입력 처리 ─────────────────────────────────────────────────
    @on(Input.Submitted, '#input-box')
    def handle_input(self, event: Input.Submitted):
        text = event.value.strip()
        inp = self.query_one('#input-box', Input)
        inp.value = ''

        if not text:
            return

        # 확인 대기 중일 때 (write_file confirm)
        if self._awaiting_confirm:
            self._confirm_result = text.lower() in ('y', 'yes', 'ㅛ')
            self._awaiting_confirm = False
            if self._confirm_event:
                self._confirm_event.set()
            return

        if self._agent_running:
            self.output_direct(Text('  ⚠  에이전트 실행 중입니다\n', style='yellow'))
            return

        # 에코
        turns = len([m for m in self.session_msgs if m['role'] == 'user'])
        self.output_direct(Text(f'\n❯ [{turns}] {text}', style='bold cyan'))

        if text.startswith('@claude '):
            threading.Thread(
                target=self._run_claude_cli,
                args=(text[8:].strip(),),
                kwargs={'add_to_session': True},
                daemon=True,
            ).start()
            return

        if text.startswith('/'):
            cmd = text.split()[0]
            if cmd in ('/quit', '/exit', '/q'):
                self.action_request_quit()
                return
            threading.Thread(
                target=self._handle_slash_thread,
                args=(text,),
                daemon=True,
            ).start()
            return

        if self._is_cplan_intent(text):
            task = self._extract_cplan_task(text)
            threading.Thread(target=self._do_cplan, args=(task,), daemon=True).start()
            return

        threading.Thread(target=self._run_agent_thread, args=(text,), daemon=True).start()

    # ── 에이전트 스레드 ───────────────────────────────────────────
    def _set_running(self, running: bool):
        def _upd():
            self._agent_running = running
            inp = self.query_one('#input-box', Input)
            if running:
                inp.placeholder = '처리 중...'
                inp.disabled = True
            else:
                inp.placeholder = '입력... (/ 명령어, @claude 질문, Ctrl+C 종료)'
                inp.disabled = False
                self.call_after_refresh(self._focus_input)
            self._refresh_prompt()
            self._update_status()
        self.call_from_thread(_upd)

    def _run_agent_thread(self, user_input: str, plan_mode: bool = False):
        self._set_running(True)
        unknown_tools: list[str] = []

        self.output(Rule(style='dim'))
        self.output(Text())

        snippets = self._get_snippets(user_input)

        try:
            _, self.session_msgs = agent.run(
                user_input,
                session_messages=self.session_msgs,
                working_dir=self.working_dir,
                profile=self.profile,
                context_snippets=snippets,
                plan_mode=plan_mode,
                on_token=self._on_token,
                on_tool=self._on_tool,
                confirm_write=self._confirm_write,
                on_unknown_tool=lambda n: unknown_tools.append(n) if n not in unknown_tools else None,
            )
        except Exception as e:
            self.output(Text(f'\n  ✗ 오류: {e}', style='bold red'))

        self.call_from_thread(self._flush_stream)
        self.output(Text())
        self.output(Rule(style='dim'))
        self.output(Text())

        for name in unknown_tools:
            self._suggest_tool(name)

        self._set_running(False)

    def _on_token(self, token: str):
        def _write():
            with self._stream_lock:
                self._stream_buf += token
                buf = self._stream_buf
            if '\n' in buf:
                lines = buf.split('\n')
                for line in lines[:-1]:
                    self._rl_write(Text(line))
                with self._stream_lock:
                    self._stream_buf = lines[-1]
                buf = lines[-1]
            self.query_one('#stream-line', Static).update(Text(buf))
        self.call_from_thread(_write)

    def _on_tool(self, name: str, args: dict, result):
        meta = _TOOL_META.get(name)
        label, color, arg_fn = meta if meta else (name, 'dim', lambda a: '')
        arg_str = arg_fn(args)

        if result is None:
            self.output(Text.assemble(
                ('\n  ● ', 'bold'),
                (label, color),
                ('  ', ''),
                (arg_str, 'dim'),
            ))
        else:
            hint = _tool_result_hint(name, result)
            if result.get('ok'):
                self.output(Text.assemble(
                    ('  ⎿  ', 'dim'),
                    ('✓  ', 'green'),
                    (hint, 'dim'),
                    ('\n', ''),
                ))
            else:
                self.output(Text.assemble(
                    ('  ⎿  ', 'dim'),
                    ('✗  ', 'bold red'),
                    (hint, 'dim'),
                    ('\n', ''),
                ))

    def _confirm_write(self, path: str) -> bool:
        event = threading.Event()
        self._confirm_event = event
        self._confirm_result = False

        def _show():
            self._awaiting_confirm = True
            rl = self.query_one('#output', RichLog)
            rl.write(Text.assemble(
                ('\n  ', ''),
                ('Write', 'bold yellow'),
                (f'  {path}', 'bold'),
                ('  → y/n', 'dim'),
                ('\n', ''),
            ))
            inp = self.query_one('#input-box', Input)
            inp.placeholder = f'Write {path}? (y/n)'
            inp.disabled = False
            self.call_after_refresh(self._focus_input)
        self.call_from_thread(_show)

        event.wait(timeout=60)
        return self._confirm_result

    def _suggest_tool(self, name: str):
        info = _INSTALLABLE_TOOLS.get(name)
        if info:
            _, pkg = info
            pkg_note = f'  pip install {pkg}' if pkg else ''
            self.output(Text.assemble(
                ('  ⚠  ', 'yellow'),
                (f'{name}', 'bold'),
                (' 툴 미등록', 'yellow'),
                (pkg_note, 'dim'),
                ('\n', ''),
            ))
        else:
            self.output(Text.assemble(
                ('  ⚠  ', 'yellow'),
                (f'{name}', 'bold'),
                (' 툴 미등록 — /improve 로 자동 구현 시도 가능\n', 'dim'),
            ))

    # ── Claude CLI ────────────────────────────────────────────────
    def _run_claude_cli(self, query: str, add_to_session: bool = False):
        self._set_running(True)
        self.output(Rule('[bold blue]Claude[/bold blue]', style='blue dim', align='left'))
        self.output(Text())

        collected = []
        try:
            def _tok(line):
                collected.append(line)
                self.output(Text(line))
            claude_ask(query, on_token=_tok)
        except Exception as e:
            self.output(Text(f'  ✗ {e}', style='bold red'))

        self.output(Text())
        self.output(Rule(style='dim'))
        self.output(Text())

        if add_to_session and collected:
            response = ''.join(collected).strip()
            self.session_msgs.append({'role': 'user', 'content': f'[Claude에게 질문]\n{query}'})
            self.session_msgs.append({'role': 'assistant', 'content': f'[Claude 답변]\n{response}'})

        self._set_running(False)

    # ── /cplan ────────────────────────────────────────────────────
    def _do_cplan(self, task: str):
        if not claude_available():
            self.output(Text('  ✗ claude CLI 없음\n', style='bold red'))
            return
        self._set_running(True)
        prompt = CPLAN_PROMPT_TMPL.format(task=task, working_dir=self.working_dir)

        self.output(Rule('[bold blue]Claude[/bold blue] [dim]플랜 작성[/dim]', style='blue dim', align='left'))
        self.output(Text())

        collected = []
        try:
            def _tok(line):
                collected.append(line)
                self.output(Text(line))
            claude_ask(prompt, on_token=_tok)
        except Exception as e:
            self.output(Text(f'  ✗ {e}', style='bold red'))
            self._set_running(False)
            return

        plan_text = ''.join(collected).strip()
        self.output(Text())
        self.output(Rule(style='dim'))

        if not plan_text:
            self._set_running(False)
            return

        self.session_msgs.append({'role': 'user', 'content': f'[Claude 플랜 요청]\n{task}'})
        self.session_msgs.append({'role': 'assistant', 'content': f'[Claude 플랜]\n{plan_text}'})

        # 실행 확인 (confirm_write와 같은 패턴 사용)
        event = threading.Event()
        self._confirm_event = event
        self._confirm_result = False

        def _ask():
            self._awaiting_confirm = True
            rl = self.query_one('#output', RichLog)
            rl.write(Text('\n  위 플랜으로 로컬 모델이 실행할까요? (y/n)\n', style='bold'))
            inp = self.query_one('#input-box', Input)
            inp.placeholder = '실행할까요? (y/n)'
            inp.disabled = False
            self.call_after_refresh(self._focus_input)
        self.call_from_thread(_ask)
        event.wait(timeout=60)

        if self._confirm_result:
            execute_prompt = (
                f'위에서 Claude가 작성한 플랜을 그대로 실행해줘.\n'
                f'각 단계를 순서대로 처리하고 도구를 사용해.\n\n작업: {task}'
            )
            self._run_agent_thread(execute_prompt)
        else:
            self.output(Text('  실행 취소됨\n', style='dim'))
            self._set_running(False)

    # ── 슬래시 명령어 스레드 ──────────────────────────────────────
    def _handle_slash_thread(self, cmd: str):
        parts = cmd.strip().split(maxsplit=1)
        name = parts[0]

        if name == '/clear':
            self.session_msgs = []
            self.output(Text('  대화 초기화\n', style='dim'))

        elif name == '/undo':
            non_sys = [m for m in self.session_msgs if m['role'] != 'system']
            if len(non_sys) >= 2:
                sys_msgs = [m for m in self.session_msgs if m['role'] == 'system']
                self.session_msgs = sys_msgs + non_sys[:-2]
                self.undo_count += 1
                self.output(Text('  마지막 교환 취소됨\n', style='dim'))
            else:
                self.output(Text('  취소할 내용 없음\n', style='dim'))

        elif name == '/plan':
            query = parts[1] if len(parts) > 1 else ''
            if not query:
                self.output(Text('  사용법: /plan <작업>\n', style='yellow'))
            else:
                self._run_agent_thread(query, plan_mode=True)
                return

        elif name == '/cplan':
            query = parts[1] if len(parts) > 1 else ''
            if not query:
                self.output(Text('  사용법: /cplan <작업>\n', style='yellow'))
            else:
                self._do_cplan(query)
                return

        elif name == '/index':
            self._set_running(True)
            self.output(Text('  인덱싱 중...\n', style='dim'))
            result = context.index_directory(self.working_dir)
            self.output(Text(
                f'  ✓ {result["indexed"]}개 청크 (건너뜀 {result["skipped"]}개)\n',
                style='green',
            ))
            self._set_running(False)
            return

        elif name == '/improve':
            self._set_running(True)
            logs = read_recent(days=7)
            sources = read_sources()
            backup_path = backup_sources()
            self.output(Text(f'  ✓ 백업: {backup_path}\n', style='dim'))
            improve_input = f'실패 로그:\n{logs}\n\n소스:\n{sources[:12000]}\n\n개선하세요.'
            improve_session = [{'role': 'system', 'content': IMPROVE_SYSTEM}]
            _, _ = agent.run(
                improve_input,
                session_messages=improve_session,
                working_dir=HARNESS_DIR,
                profile=self.profile,
                on_token=self._on_token,
                on_tool=self._on_tool,
                confirm_write=self._confirm_write,
            )
            self.output(Text('  ✓ 개선 완료\n', style='green'))
            self._set_running(False)
            return

        elif name == '/learn':
            self._set_running(True)
            if not self.session_msgs:
                self.output(Text('  학습할 내용 없음\n', style='dim'))
                self._set_running(False)
                return
            summary = summarize_session(self.session_msgs)
            learn_prompt = build_learn_prompt(
                summary,
                self.profile.get('global_doc', ''),
                self.profile.get('project_doc', ''),
                self.working_dir,
            )
            learn_session = [{'role': 'system', 'content': LEARN_SYSTEM}]
            _, _ = agent.run(
                learn_prompt,
                session_messages=learn_session,
                working_dir=self.working_dir,
                profile={},
                on_token=self._on_token,
                on_tool=self._on_tool,
                confirm_write=self._confirm_write,
            )
            self.output(Text('  ✓ HARNESS.md 갱신\n', style='green'))
            self._set_running(False)
            return

        elif name == '/evolve':
            self._set_running(True)
            evolution.run(
                session_msgs=self.session_msgs,
                working_dir=self.working_dir,
                profile=self.profile,
                console=None,
                agent_run=lambda *a, **kw: agent.run(*a, **{
                    **kw,
                    'on_token': self._on_token,
                    'on_tool': self._on_tool,
                    'confirm_write': self._confirm_write,
                }),
                on_token=self._on_token,
                on_tool=self._on_tool,
                confirm_write=self._confirm_write,
                undo_count=self.undo_count,
            )
            self._set_running(False)
            return

        elif name == '/history':
            from evolution.history import recent as hist_recent, avg_score
            from evolution.scorer import grade
            entries = hist_recent(20)
            if not entries:
                self.output(Text('  진화 이력 없음\n', style='dim'))
            else:
                t = Table(box=box.SIMPLE, show_header=True, border_style='dim')
                t.add_column('시간', style='dim', no_wrap=True)
                t.add_column('이벤트')
                t.add_column('품질', justify='right')
                for e in entries[-10:]:
                    sc = e.get('score')
                    score_str = f'{grade(sc)[0]} {sc:.2f}' if sc is not None else '—'
                    t.add_row(e['ts'][:16], e.get('event', ''), score_str)
                self.output(t)
                self.output(Text(f'  평균 {avg_score(10):.2f}\n', style='dim'))

        elif name == '/restore':
            backups = list_backups()
            if not backups:
                self.output(Text('  백업 없음\n', style='dim'))
            else:
                for i, b in enumerate(backups[:5]):
                    self.output(Text(f'  [{i}] {b}', style='dim'))
                # 간단히 0번 복원 (confirm 생략 — 슬래시 명령 단순화)
                idx_str = parts[1] if len(parts) > 1 else '0'
                try:
                    target = backups[int(idx_str)]
                except (ValueError, IndexError):
                    target = backups[0]
                r = restore_backup(target)
                if r['ok']:
                    self.output(Text('  ✓ 복원 완료 — 재시작 필요\n', style='green'))
                else:
                    self.output(Text(f'  ✗ {r["error"]}\n', style='bold red'))

        elif name == '/cd':
            if len(parts) < 2:
                self.output(Text('  사용법: /cd <경로>\n', style='yellow'))
            else:
                new_dir = os.path.expanduser(parts[1])
                if os.path.isdir(new_dir):
                    self.working_dir = os.path.abspath(new_dir)
                    self.profile = prof.load(self.working_dir)
                    self.session_msgs = []
                    self.output(Text(f'  → {self._short_dir(self.working_dir)}\n', style='dim'))
                    def _upd():
                        self._update_status()
                        self._refresh_prompt()
                    self.call_from_thread(_upd)
                else:
                    self.output(Text(f'  ✗ 없는 경로: {new_dir}\n', style='bold red'))

        elif name == '/files':
            self._print_tree()

        elif name == '/save':
            filename = sess.save(self.session_msgs, self.working_dir)
            self.output(Text(f'  ✓ {filename}\n', style='green'))

        elif name == '/resume':
            filename = parts[1] if len(parts) > 1 else None
            data = sess.load(filename) if filename else sess.load_latest(self.working_dir)
            if not data:
                self.output(Text('  불러올 세션 없음\n', style='dim'))
            else:
                self.session_msgs = data['messages']
                self.working_dir = data.get('working_dir', self.working_dir)
                turns = len([m for m in self.session_msgs if m['role'] == 'user'])
                self.output(Text(f'  ✓ {turns}턴 복원\n', style='green'))

        elif name == '/sessions':
            sessions = sess.list_sessions()
            if not sessions:
                self.output(Text('  저장된 세션 없음\n', style='dim'))
            else:
                t = Table(box=box.SIMPLE, show_header=True, border_style='dim')
                t.add_column('파일', style='dim')
                t.add_column('디렉토리')
                t.add_column('턴', justify='right', style='dim')
                t.add_column('첫 질문')
                for s in sessions[:10]:
                    t.add_row(s['filename'], s['working_dir'], str(s['turns']), s['preview'])
                self.output(t)

        elif name == '/init':
            path = prof.create_template(self.working_dir)
            self.output(Text(f'  ✓ {path}\n', style='green'))

        elif name == '/claude':
            query = parts[1] if len(parts) > 1 else ''
            if not query:
                self.output(Text('  사용법: /claude <질문>\n', style='yellow'))
            else:
                self._run_claude_cli(query, add_to_session=True)
                return

        elif name == '/help':
            self._print_help()

        else:
            self.output(Text(f'  ✗ 알 수 없는 명령어: {name}\n', style='bold red'))

        def _upd():
            self._refresh_prompt()
            self._update_status()
        self.call_from_thread(_upd)

    # ── /files 트리 ───────────────────────────────────────────────
    def _print_tree(self, max_depth: int = 3):
        root_name = os.path.basename(self.working_dir) or self.working_dir
        tree = Tree(f'[bold cyan]{root_name}[/bold cyan]', guide_style='dim')

        def _add(node, path, depth):
            if depth > max_depth:
                return
            try:
                entries = sorted(os.listdir(path))
            except PermissionError:
                return
            for e in entries:
                fp = os.path.join(path, e)
                if os.path.isdir(fp):
                    if e not in _IGNORE_DIRS:
                        branch = node.add(f'[bold]📁 {e}[/bold]')
                        _add(branch, fp, depth + 1)
                else:
                    ext = os.path.splitext(e)[1].lower()
                    icon = _FILE_ICONS.get(ext, '  ')
                    node.add(f'[dim]{icon}[/dim] {e}')

        _add(tree, self.working_dir, 1)
        self.output(tree)
        self.output(Text())

    # ── /help ─────────────────────────────────────────────────────
    def _print_help(self):
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2), border_style='dim')
        t.add_column('명령어', style='bold magenta', no_wrap=True)
        t.add_column('설명', style='white')
        for cmd, desc in SLASH_COMMANDS.items():
            t.add_row(cmd, desc.split('  ex)')[0])
        self.output(Panel(t, title='[bold]명령어[/bold]', border_style='dim'))
        self.output(Text('  @claude <질문>  — 세션에 기록되는 Claude 질문\n', style='dim'))

    # ── 유틸 ──────────────────────────────────────────────────────
    def _get_snippets(self, query: str) -> str:
        if not context.is_indexed(self.working_dir):
            return ''
        chunks = context.search(query, self.working_dir)
        if not chunks:
            return ''
        extra = []
        for cf in self.profile.get('context_files', []):
            fpath = os.path.join(self.working_dir, cf)
            if os.path.exists(fpath):
                try:
                    with open(fpath, encoding='utf-8') as f:
                        extra.append(f'// {cf}\n{f.read()[:2000]}')
                except Exception:
                    pass
        return context.format_context(chunks) + ('\n' + '\n'.join(extra) if extra else '')

    def _auto_sync(self):
        if not context.is_indexed(self.working_dir):
            py_count = sum(
                1 for _, _, fs in os.walk(self.working_dir)
                for f in fs if f.endswith('.py')
            )
            if py_count > 3:
                result = context.index_directory(self.working_dir)
                self.output(Text(
                    f'  ✓ 인덱싱 완료  {result["indexed"]}개 청크\n',
                    style='green',
                ))
        else:
            result = context.sync_index(self.working_dir)
            changed = result['added'] + result['changed'] + result['removed']
            if changed:
                self.output(Text(
                    f'  sync  +{result["added"]} ~{result["changed"]} -{result["removed"]}\n',
                    style='dim',
                ))
        self.call_from_thread(self._update_status)

    @staticmethod
    def _is_cplan_intent(text: str) -> bool:
        lower = text.lower()
        return any(t in lower for t in _CPLAN_TRIGGERS)

    @staticmethod
    def _extract_cplan_task(text: str) -> str:
        lower = text.lower()
        for t in _CPLAN_TRIGGERS:
            idx = lower.find(t)
            if idx != -1:
                after = text[idx + len(t):].strip(' ,.:;줘')
                if after:
                    return after
        return text

    def action_request_quit(self):
        # 종료 시 자동 진화 + 세션 저장 물어볼 수도 있지만 일단 바로 종료
        self.exit()


def main():
    app = HarnessApp()
    app.run()


if __name__ == '__main__':
    main()
