#!/usr/bin/env python3
import sys
import os
import time
from datetime import datetime

from rich.console import Console
from rich.prompt import Confirm
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.tree import Tree
from rich.theme import Theme
from rich.markdown import Markdown
from rich.text import Text
from rich import box

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style as PtStyle
from prompt_toolkit.formatted_text import HTML

import agent
import config
import profile as prof
import context
import session as sess
from session.logger import read_recent
from session.analyzer import summarize_session, build_learn_prompt
from session.compactor import needs_compaction, compact
from tools.improve import backup_sources, validate_python, read_sources, list_backups, restore_backup, HARNESS_DIR
from tools.mcp import StdioMCPClient
from tools import register_mcp_tools
import evolution
from tools.claude_cli import ask as claude_ask, is_available as claude_available

THEME = Theme({
    'tool.read':    'cyan',
    'tool.write':   'yellow',
    'tool.run':     'magenta',
    'tool.git':     'green',
    'tool.ok':      'green',
    'tool.fail':    'bold red',
    'tool.hint':    'dim white',
    'response':     'white',
    'prompt':       'bold cyan',
    'cmd':          'bold magenta',
    'info':         'dim white',
    'warn':         'yellow',
    'claude.label': 'bold blue',
})
console = Console(theme=THEME, highlight=False)

# ── 도구 메타데이터 ────────────────────────────────────────────────
_TOOL_META = {
    'read_file':     ('Read',    'tool.read',  lambda a: a.get('path', '')),
    'write_file':    ('Write',   'tool.write', lambda a: a.get('path', '')),
    'list_files':    ('Glob',    'tool.read',  lambda a: a.get('pattern', '')),
    'run_command':   ('Run',     'tool.run',   lambda a: a.get('command', '')[:70]),
    'run_python':    ('Python',  'tool.run',   lambda a: (a.get('code', '').split('\n')[0])[:70]),
    'git_status':    ('Git',     'tool.git',   lambda _: 'status'),
    'git_diff':      ('Git',     'tool.git',   lambda a: 'diff' + (' --staged' if a.get('staged') else '')),
    'git_log':       ('Git',     'tool.git',   lambda a: f'log -{a.get("n", 10)}'),
    'git_diff_full': ('Git',     'tool.git',   lambda _: 'diff HEAD'),
    'search_web':    ('Search',  'cyan',       lambda a: a.get('query', '')[:70]),
    'fetch_page':    ('Fetch',   'cyan',       lambda a: a.get('url', '')[:70]),
}


def _tool_meta_for(name: str) -> tuple:
    if name in _TOOL_META:
        return _TOOL_META[name]
    if name.startswith('mcp__'):
        parts = name.split('__', 2)
        server = parts[1] if len(parts) > 1 else 'mcp'
        tool = parts[2] if len(parts) > 2 else name
        return (f'MCP:{server}', 'cyan', lambda a: tool)
    return (name, 'dim white', lambda _: '')


def _tool_result_hint(name: str, result: dict) -> str:
    if not result.get('ok'):
        err = result.get('error') or result.get('stderr') or ''
        return err.strip()[:80]
    if name == 'read_file':
        lines = result.get('content', '').count('\n') + 1
        return f'{lines}줄'
    if name == 'write_file':
        return '저장됨'
    if name == 'list_files':
        return f'{len(result.get("files", []))}개 파일'
    if name in ('run_command', 'run_python'):
        out = (result.get('stdout') or result.get('stderr') or '').strip()
        first = out.split('\n')[0][:60] if out else ''
        rc = result.get('returncode', 0)
        return f'{first}' if first else f'exit {rc}'
    if name.startswith('git_'):
        out = (result.get('output') or result.get('stdout') or '').strip()
        return out.split('\n')[0][:60] if out else 'ok'
    return 'ok'


# ── 슬래시 명령어 정의 ─────────────────────────────────────────────
SLASH_COMMANDS = {
    '/clear':    '대화 초기화',
    '/undo':     '마지막 질문·응답 취소',
    '/plan':     '로컬 모델이 플랜 작성 후 실행  ex) /plan 인증 모듈 리팩터링',
    '/cplan':    'Claude가 플랜 작성 → 로컬 모델이 실행  ex) /cplan 인증 모듈 리팩터링',
    '/index':    '코드베이스 인덱싱',
    '/improve':  '하네스 자기 분석 및 개선',
    '/learn':    '세션 분석 후 HARNESS.md 즉시 갱신',
    '/evolve':          '진화 엔진 즉시 실행  ex) /evolve proposals / /evolve run / /evolve changelog',
    '/history':  '진화 이력 및 품질 트렌드 확인',
    '/restore':  '이전 백업으로 롤백',
    '/cd':       '작업 디렉토리 변경  ex) /cd ~/myproject',
    '/files':    '현재 디렉토리 파일 트리',
    '/save':     '현재 세션 저장',
    '/resume':   '마지막 세션 불러오기',
    '/sessions': '저장된 세션 목록',
    '/init':     '.harness.toml 생성',
    '/claude':   'Claude CLI에 질문 (세션에 기록됨)  ex) /claude 이 함수 설명해줘',
    '/help':     '도움말',
    '/quit':     '종료',
}

PT_STYLE = PtStyle.from_dict({
    'prompt':                               'ansicyan bold',
    'completion-menu.completion':           'bg:#1a1a2e #aaaaaa',
    'completion-menu.completion.current':   'bg:#0f3460 #ffffff bold',
    'completion-menu.meta.completion':      'bg:#1a1a2e #555555',
    'completion-menu.meta.completion.current': 'bg:#0f3460 #aaccff',
})


class SlashCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith('/'):
            return
        word = text.split()[0] if text.split() else '/'
        for cmd, desc in SLASH_COMMANDS.items():
            if cmd.startswith(word):
                yield Completion(
                    cmd[len(word):],
                    start_position=0,
                    display=cmd,
                    display_meta=desc.split('  ex)')[0],
                )


slash_completer = SlashCompleter()


def _short_dir(path: str) -> str:
    home = os.path.expanduser('~')
    if path.startswith(home):
        path = '~' + path[len(home):]
    parts = path.split(os.sep)
    if len(parts) > 3:
        return os.sep.join(['…'] + parts[-2:])
    return path


def get_input(turns: int, working_dir: str) -> str:
    short = _short_dir(working_dir)
    return pt_prompt(
        HTML(f'<ansibrightblack>{short}</ansibrightblack> '
             f'<ansicyan><b>❯</b></ansicyan> '
             f'<ansibrightblack>[{turns}]</ansibrightblack> '),
        completer=slash_completer,
        style=PT_STYLE,
        complete_while_typing=True,
    )


# ── 스피너 ────────────────────────────────────────────────────────
import threading

_SPINNER_FRAMES = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']

class _Spinner:
    def __init__(self):
        self._stop  = threading.Event()
        self._thread = None
        self.active  = False

    def start(self):
        if self.active:
            return
        self.active = True
        self._stop.clear()
        sys.stdout.write(f'\x1b[36m⠋\x1b[0m\n')
        sys.stdout.flush()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        i = 1
        while not self._stop.wait(0.08):
            frame = _SPINNER_FRAMES[i % len(_SPINNER_FRAMES)]
            sys.stdout.write(f'\x1b[1A\r\x1b[K\x1b[36m{frame}\x1b[0m\n')
            sys.stdout.flush()
            i += 1

    def stop(self):
        if not self.active:
            return
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.3)
        sys.stdout.write('\x1b[1A\r\x1b[K')
        sys.stdout.flush()
        self.active = False


_spinner = _Spinner()
_token_buf: list[str] = []


def _flush_tokens():
    _spinner.stop()
    text = ''.join(_token_buf).strip()
    if text:
        console.print(f'\n[orange3]● {_BANNER_MODEL}[/orange3]')
        console.out(text, highlight=False)
    _token_buf.clear()


# ── UI 상태 ────────────────────────────────────────────────────────
class _UIState:
    def __init__(self):
        self._active_tool: str | None = None
        self._tool_start_ts: float    = 0.0

    def reset(self):
        self._active_tool = None
        _token_buf.clear()


_ui = _UIState()


# ── 콜백 ──────────────────────────────────────────────────────────
def on_token(token: str):
    _token_buf.append(token)


def on_tool(name: str, args: dict, result):
    label, style, arg_fn = _tool_meta_for(name)
    arg_str = arg_fn(args)

    if result is None:
        _flush_tokens()
        _ui._active_tool    = name
        _ui._tool_start_ts  = time.time()
        console.print(f'[bold]●[/bold] [{style}]{label}[/{style}] [dim]{arg_str}[/dim]')
        _spinner.start()
    else:
        _spinner.stop()
        elapsed    = time.time() - _ui._tool_start_ts
        hint       = _tool_result_hint(name, result)
        elapsed_str = f' [dim]{elapsed:.1f}s[/dim]' if elapsed > 0.5 else ''
        if result.get('ok'):
            console.print(
                f'[dim]└ {hint}[/dim]{elapsed_str}'
            )
        else:
            console.print(
                f'[dim]└ [/dim][tool.fail]{hint}[/tool.fail]'
            )
        _spinner.start()


def confirm_write(path: str) -> bool:
    _flush_tokens()
    return Confirm.ask(f'  [warn]Write[/warn] [bold]{path}[/bold]')


def confirm_bash(command: str) -> bool:
    _flush_tokens()
    return Confirm.ask(f'  [bold red]Run[/bold red] [bold]{command[:100]}[/bold]')


# ── 미등록 툴 제안 ────────────────────────────────────────────────
_INSTALLABLE_TOOLS = {
    'search_web':  ('web.py', 'duckduckgo_search'),
    'fetch_page':  ('web.py', None),
    'search_code': ('search.py', None),
}

def _suggest_unknown_tools(names: list[str]):
    if not names:
        return
    for name in names:
        info = _INSTALLABLE_TOOLS.get(name)
        if info:
            module_file, pkg = info
            pkg_note = f'  [dim](pip install {pkg})[/dim]' if pkg else ''
            console.print(
                f'\n  [warn]⚠[/warn]  모델이 [bold]{name}[/bold] 툴을 호출했지만 '
                f'등록되지 않았습니다{pkg_note}\n'
                f'  [dim]tools/{module_file} 에 구현 후 tools/__init__.py에 등록하세요[/dim]'
            )
        else:
            if Confirm.ask(
                f'\n  [warn]⚠[/warn]  모델이 [bold]{name}[/bold] 툴을 호출했습니다 '
                f'(미등록). 하네스에 추가할까요?',
                default=False,
            ):
                console.print(
                    f'  [dim]tools/{name}.py 파일을 만들고 tools/__init__.py에 등록하세요\n'
                    f'  /improve 를 실행하면 자동으로 구현을 시도합니다[/dim]'
                )


# ── 응답 구분선 ────────────────────────────────────────────────────
def _response_header(model_label: str = 'qwen2.5-coder'):
    console.print(f'\n[dim]{model_label}[/dim]')


def _response_footer():
    console.print()


# ── 유틸 ──────────────────────────────────────────────────────────
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
        f'{_D}·  qwen2.5-coder:32b{_R}\n',
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
        f'  [bold cyan]qwen2.5-coder:32b[/bold cyan]'
        f'[dim]  ·  {short}  ·  [/dim]'
        f'{idx_badge}[dim]  ·  [/dim]{claude_badge}'
    )
    console.print(
        '  [dim]/ 명령어  ·  @claude 질문  ·  /help 도움말[/dim]\n'
    )


# ── /improve ──────────────────────────────────────────────────────
IMPROVE_SYSTEM = '''당신은 이 하네스 시스템의 자기 개선 전문가입니다.
다음 단계로 개선을 수행하세요:

1. 실패 로그를 분석해 반복되는 문제 패턴을 파악하세요
2. 소스 코드를 읽어 해당 문제의 근본 원인을 찾으세요
3. 구체적인 개선안을 코드로 작성하고 write_file로 적용하세요

수정 가능한 파일 (HARNESS_DIR 기준):
- config.py, agent.py
- tools/__init__.py, tools/fs.py, tools/shell.py, tools/git.py
- context/indexer.py, context/retriever.py

주의사항:
- 파일 전체를 교체할 때만 write_file을 사용하세요
- 수정 후 반드시 run_command("python3 -m py_compile <파일>")로 검증하세요
- 검증 실패 시 원래대로 복구하세요
- 작업이 끝나면 어떤 파일을 왜 수정했는지 요약하세요
'''


def do_improve(session_msgs: list, working_dir: str, profile: dict) -> list:
    console.print('[dim]최근 실패 로그 수집 중...[/dim]')
    logs = read_recent(days=7)
    sources = read_sources()

    console.print('[dim]백업 생성 중...[/dim]')
    backup_path = backup_sources()
    console.print(f'  [tool.ok]✓[/tool.ok] 백업  [dim]{backup_path}[/dim]\n')

    improve_input = f'''최근 실패 로그:
{logs}

---
하네스 소스 코드:
{sources[:12000]}

위 로그와 소스를 분석해 개선이 필요한 부분을 찾고 수정하세요.
수정 후 각 파일을 py_compile로 검증하세요.'''

    improve_session = [{'role': 'system', 'content': IMPROVE_SYSTEM + f'\nHARNESS_DIR: {HARNESS_DIR}'}]

    console.print('[bold cyan]── 자기 개선[/bold cyan]')
    _ui.reset()

    _, improve_session = agent.run(
        improve_input,
        session_messages=improve_session,
        working_dir=HARNESS_DIR,
        profile=profile,
        on_token=on_token,
        on_tool=on_tool,
        confirm_write=confirm_write,
    )

    _response_footer()

    console.print('[dim]수정 파일 검증 중...[/dim]')
    all_ok = True
    for rel in ['config.py', 'agent.py', 'tools/__init__.py', 'tools/fs.py', 'tools/shell.py']:
        fpath = os.path.join(HARNESS_DIR, rel)
        if os.path.exists(fpath):
            r = validate_python(fpath)
            if r['ok']:
                console.print(f'  [tool.ok]✓[/tool.ok] {rel}')
            else:
                console.print(f'  [tool.fail]✗[/tool.fail] {rel}  [dim]{r["error"]}[/dim]')
                all_ok = False

    if not all_ok:
        console.print('\n[warn]문법 오류 발견 — /restore 로 롤백 가능[/warn]')
    else:
        console.print('\n  [tool.ok]✓[/tool.ok] 모든 파일 검증 통과')

    return session_msgs


# ── /learn ────────────────────────────────────────────────────────
LEARN_SYSTEM = '''당신은 하네스의 자기학습 에이전트입니다.
세션 분석 결과를 바탕으로 HARNESS.md 파일을 개선하세요.

규칙:
- 기존 내용을 먼저 read_file로 확인 후 수정
- 중복 내용 추가 금지
- 마크다운 형식 유지
- 변경이 없으면 파일을 건드리지 말 것
- 완료 후 어떤 내용을 추가/수정했는지 한 줄 요약
'''


def do_learn(session_msgs: list, working_dir: str, profile: dict) -> list:
    if not session_msgs or len([m for m in session_msgs if m['role'] == 'user']) == 0:
        console.print('[dim]학습할 세션 내용이 없습니다[/dim]')
        return session_msgs

    console.print('[dim]세션 분석 중...[/dim]')
    summary = summarize_session(session_msgs)
    global_doc = profile.get('global_doc', '')
    project_doc = profile.get('project_doc', '')
    learn_prompt = build_learn_prompt(summary, global_doc, project_doc, working_dir)
    learn_session = [{'role': 'system', 'content': LEARN_SYSTEM}]

    console.print('[bold cyan]── 세션 학습[/bold cyan]')
    _ui.reset()

    _, learn_session = agent.run(
        learn_prompt,
        session_messages=learn_session,
        working_dir=working_dir,
        profile={},
        on_token=on_token,
        on_tool=on_tool,
        confirm_write=confirm_write,
    )

    _response_footer()
    console.print('  [tool.ok]✓[/tool.ok] HARNESS.md 갱신 완료\n')
    return session_msgs


# ── 자연어 /cplan 의도 감지 ───────────────────────────────────────
_CPLAN_TRIGGERS = [
    '클로드로 계획', '클로드가 계획', '클로드로 플랜', '클로드가 플랜',
    '클로드한테 계획', '클로드한테 플랜', '클로드가 설계', '클로드로 설계',
    'claude로 계획', 'claude가 계획', 'claude로 플랜', 'claude가 플랜',
    '클로드가 짜줘', '클로드로 짜줘', '클로드가 작성', '클로드가 먼저',
]


def _is_cplan_intent(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in _CPLAN_TRIGGERS)


def _extract_cplan_task(text: str) -> str:
    lower = text.lower()
    for t in _CPLAN_TRIGGERS:
        idx = lower.find(t)
        if idx != -1:
            after = text[idx + len(t):].strip(' ,.:;줘')
            if after:
                return after
    return text


# ── Claude CLI 호출 ───────────────────────────────────────────────
def _run_claude_cli(query: str, session_msgs: list | None = None) -> str:
    if not claude_available():
        console.print(
            '  [tool.fail]✗[/tool.fail] claude CLI를 찾을 수 없습니다\n'
            '  [dim]설치: https://claude.ai/code[/dim]'
        )
        return ''

    console.print('\n[bold blue]● Claude[/bold blue]')

    collected = []
    try:
        def _tok(line):
            collected.append(line)
            console.print(line, end='', highlight=False, markup=False)
        claude_ask(query, on_token=_tok)
    except RuntimeError as e:
        console.print(f'\n  [tool.fail]✗[/tool.fail] {e}\n')
        return ''
    except KeyboardInterrupt:
        console.print('\n  [dim]중단됨[/dim]\n')
        return ''

    console.print('\n')

    response = ''.join(collected).strip()

    if session_msgs is not None and response:
        session_msgs.append({'role': 'user', 'content': f'[Claude에게 질문]\n{query}'})
        session_msgs.append({'role': 'assistant', 'content': f'[Claude 답변]\n{response}'})

    return response


# ── /cplan: Claude 플랜 → 로컬 실행 ──────────────────────────────
CPLAN_PROMPT_TMPL = '''\
다음 작업에 대한 실행 계획을 작성해줘.
작업 디렉토리: {working_dir}

작업: {task}

아래 형식으로 단계별 플랜을 작성해:
1. 각 단계를 번호 목록으로
2. 어떤 파일을 읽고/쓸지 명시
3. 코드 변경이 필요하면 핵심 로직도 포함
4. 주의사항/엣지케이스 언급

실행 가능한 구체적인 플랜이어야 해. 로컬 코딩 모델이 이 플랜만 보고 바로 실행할 수 있도록.
'''


def do_cplan(task: str, session_msgs: list, working_dir: str, profile: dict) -> list:
    if not claude_available():
        console.print(
            '  [tool.fail]✗[/tool.fail] claude CLI를 찾을 수 없습니다\n'
            '  [dim]설치: https://claude.ai/code[/dim]'
        )
        return session_msgs

    prompt = CPLAN_PROMPT_TMPL.format(task=task, working_dir=working_dir)

    console.print('\n[bold blue]● Claude[/bold blue] [dim]플랜 작성 중...[/dim]')

    collected = []
    try:
        def _tok(line):
            collected.append(line)
            console.print(line, end='', highlight=False, markup=False)
        claude_ask(prompt, on_token=_tok)
    except (RuntimeError, KeyboardInterrupt) as e:
        console.print(f'\n  [tool.fail]✗[/tool.fail] {e}')
        return session_msgs

    plan_text = ''.join(collected).strip()
    console.print('\n')

    if not plan_text:
        console.print('  [tool.fail]✗[/tool.fail] 플랜을 받지 못했습니다')
        return session_msgs

    session_msgs.append({'role': 'user', 'content': f'[Claude 플랜 작성 요청]\n{task}'})
    session_msgs.append({'role': 'assistant', 'content': f'[Claude 작성 플랜]\n{plan_text}'})

    console.print()
    if not Confirm.ask('  위 플랜으로 [bold]로컬 모델이 실행[/bold]할까요?', default=True):
        console.print('  [dim]실행 취소 — 플랜은 세션에 기록되었습니다[/dim]')
        return session_msgs

    execute_prompt = (
        f'위에서 Claude가 작성한 플랜을 그대로 실행해줘.\n'
        f'각 단계를 순서대로 처리하고, 파일 읽기/쓰기가 필요하면 도구를 사용해.\n\n'
        f'작업: {task}'
    )

    snippets = get_context_snippets(task, working_dir, profile)
    _response_header()
    _ui.reset()

    _, session_msgs = agent.run(
        execute_prompt,
        session_messages=session_msgs,
        working_dir=working_dir,
        profile=profile,
        context_snippets=snippets,
        on_token=on_token,
        on_tool=on_tool,
        confirm_write=confirm_write if profile.get('confirm_writes', True) else None,
        confirm_bash=confirm_bash if profile.get('confirm_bash', True) else None,
        hooks=profile.get('hooks', {}),
    )

    _response_footer()
    return session_msgs


# ── 슬래시 핸들러 ─────────────────────────────────────────────────
def handle_slash(cmd: str, session_msgs: list, working_dir: str, profile: dict, undo_count: int = 0) -> tuple[list, str, int]:
    parts = cmd.strip().split(maxsplit=1)
    name = parts[0]

    if name == '/clear':
        console.print('  [dim]대화 초기화[/dim]')
        return [], working_dir, undo_count

    if name == '/undo':
        non_system = [m for m in session_msgs if m['role'] != 'system']
        if len(non_system) >= 2:
            system = [m for m in session_msgs if m['role'] == 'system']
            session_msgs = system + non_system[:-2]
            undo_count += 1
            console.print('  [dim]마지막 교환 취소됨[/dim]')
        else:
            console.print('  [dim]취소할 내용이 없습니다[/dim]')
        return session_msgs, working_dir, undo_count

    if name == '/plan':
        query = parts[1] if len(parts) > 1 else ''
        if not query:
            console.print('  [warn]사용법:[/warn] /plan <작업 내용>')
            return session_msgs, working_dir, undo_count
        snippets = get_context_snippets(query, working_dir, profile)
        _response_header()
        _ui.reset()
        _run_agent(query, plan_mode=True, context_snippets=snippets)
        _response_footer()
        return session_msgs, working_dir, undo_count

    if name == '/cplan':
        query = parts[1] if len(parts) > 1 else ''
        if not query:
            console.print('  [warn]사용법:[/warn] /cplan <작업 내용>')
            return session_msgs, working_dir, undo_count
        session_msgs = do_cplan(query, session_msgs, working_dir, profile)
        return session_msgs, working_dir, undo_count

    if name == '/index':
        do_index(working_dir)
        return session_msgs, working_dir, undo_count

    if name == '/improve':
        session_msgs = do_improve(session_msgs, working_dir, profile)
        console.print()
        return session_msgs, working_dir, undo_count

    if name == '/learn':
        session_msgs = do_learn(session_msgs, working_dir, profile)
        return session_msgs, working_dir, undo_count

    if name == '/evolve':
        sub = parts[1] if len(parts) > 1 else ''

        if sub == 'proposals':
            # 제안서 목록 표시
            from evolution.proposer import load_pending, load_all
            pending = load_pending('pending')
            if not pending:
                console.print('  [dim]대기 중인 제안서가 없습니다[/dim]')
            else:
                t = Table(box=box.SIMPLE, show_header=True, border_style='dim')
                t.add_column('우선순위', no_wrap=True)
                t.add_column('타입')
                t.add_column('근거')
                t.add_column('상태')
                for p in pending:
                    color = 'red' if p['priority'] == 'high' else 'yellow'
                    t.add_row(
                        f'[{color}]{p["priority"]}[/{color}]',
                        p['type'],
                        p['rationale'][:60],
                        p.get('status', 'pending'),
                    )
                console.print(t)
            return session_msgs, working_dir, undo_count

        if sub == 'run':
            # 제안서 즉시 실행
            from evolution.executor import execute_pending
            console.print('  [dim]자율 개선 실행 중...[/dim]')
            results = execute_pending(force=True, console=console)
            if not results:
                console.print('  [dim]실행할 제안서 없음[/dim]')
            for r in results:
                icon = '[tool.ok]✓[/tool.ok]' if r['ok'] else '[tool.fail]✗[/tool.fail]'
                console.print(f'  {icon} {r["key"]}')
            return session_msgs, working_dir, undo_count

        if sub == 'changelog':
            from evolution.executor import load_changelog
            entries = load_changelog(15)
            if not entries:
                console.print('  [dim]변경 이력이 없습니다[/dim]')
            else:
                t = Table(box=box.SIMPLE, show_header=True, border_style='dim')
                t.add_column('시간', style='dim', no_wrap=True)
                t.add_column('키')
                t.add_column('결과')
                t.add_column('파일')
                for e in entries:
                    status_str = '[tool.ok]적용[/tool.ok]' if e['status'] == 'applied' else '[tool.fail]실패[/tool.fail]'
                    files_str = ', '.join(e.get('changed_files', [])) or '-'
                    t.add_row(e['ts'][:16], e['key'][:30], status_str, files_str[:40])
                console.print(t)
            return session_msgs, working_dir, undo_count

        # 기본: 진화 엔진 실행
        evolution.run(
            session_msgs=session_msgs,
            working_dir=working_dir,
            profile=profile,
            console=console,
            agent_run=agent.run,
            on_token=on_token,
            on_tool=on_tool,
            confirm_write=confirm_write,
            undo_count=undo_count,
        )
        return session_msgs, working_dir, undo_count

    if name == '/history':
        from evolution.history import recent as hist_recent, avg_score
        from evolution.scorer import grade
        entries = hist_recent(20)
        if not entries:
            console.print('  [dim]진화 이력이 없습니다[/dim]')
            return session_msgs, working_dir, undo_count
        t = Table(box=box.SIMPLE, show_header=True, border_style='dim')
        t.add_column('시간', style='dim', no_wrap=True)
        t.add_column('이벤트')
        t.add_column('품질', justify='right')
        for e in entries[-10:]:
            sc = e.get('score')
            if sc is not None:
                letter, color = grade(sc)
                score_str = f'[{color}]{letter} {sc:.2f}[/{color}]'
            else:
                score_str = '[dim]—[/dim]'
            t.add_row(e['ts'][:16], e.get('event', ''), score_str)
        avg = avg_score(10)
        console.print(t)
        console.print(f'  평균 품질 [bold]{avg:.2f}[/bold] (최근 10세션)\n')
        return session_msgs, working_dir, undo_count

    if name == '/restore':
        backups = list_backups()
        if not backups:
            console.print('  [dim]백업이 없습니다[/dim]')
            return session_msgs, working_dir, undo_count
        t = Table(box=box.SIMPLE, show_header=False)
        for i, b in enumerate(backups[:5]):
            t.add_row(f'[dim]{i}[/dim]', b)
        console.print(t)
        idx_str = parts[1] if len(parts) > 1 else '0'
        try:
            target = backups[int(idx_str)]
        except (ValueError, IndexError):
            target = backups[0]
        if Confirm.ask(f'  [warn]{target}[/warn] 으로 복원할까요?'):
            r = restore_backup(target)
            if r['ok']:
                console.print('  [tool.ok]✓[/tool.ok] 복원 완료 — 하네스를 재시작하세요')
            else:
                console.print(f'  [tool.fail]✗[/tool.fail] {r["error"]}')
        return session_msgs, working_dir, undo_count

    if name == '/cd':
        if len(parts) < 2:
            console.print('  [warn]사용법:[/warn] /cd <경로>')
            return session_msgs, working_dir, undo_count
        new_dir = os.path.expanduser(parts[1])
        if os.path.isdir(new_dir):
            working_dir = os.path.abspath(new_dir)
            console.print(f'  [dim]→[/dim] {_short_dir(working_dir)}')
            return [], working_dir, undo_count
        else:
            console.print(f'  [tool.fail]✗[/tool.fail] 존재하지 않는 경로: {new_dir}')
        return session_msgs, working_dir, undo_count

    if name == '/files':
        _print_file_tree(working_dir)
        return session_msgs, working_dir, undo_count

    if name == '/save':
        filename = sess.save(session_msgs, working_dir)
        console.print(f'  [tool.ok]✓[/tool.ok] [dim]{filename}[/dim]')
        return session_msgs, working_dir, undo_count

    if name == '/resume':
        filename = parts[1] if len(parts) > 1 else None
        data = sess.load(filename) if filename else sess.load_latest(working_dir)
        if not data:
            console.print('  [dim]불러올 세션이 없습니다[/dim]')
            return session_msgs, working_dir, undo_count
        loaded = data['messages']
        turns = len([m for m in loaded if m['role'] == 'user'])
        console.print(f'  [tool.ok]✓[/tool.ok] 세션 복원  [dim]{turns}턴[/dim]')
        return loaded, data.get('working_dir', working_dir), undo_count

    if name == '/sessions':
        sessions = sess.list_sessions()
        if not sessions:
            console.print('  [dim]저장된 세션이 없습니다[/dim]')
            return session_msgs, working_dir, undo_count
        t = Table(box=box.SIMPLE, show_header=True, border_style='dim')
        t.add_column('파일', style='dim')
        t.add_column('디렉토리')
        t.add_column('턴', justify='right', style='dim')
        t.add_column('첫 질문', style='white')
        for s in sessions[:10]:
            t.add_row(s['filename'], s['working_dir'], str(s['turns']), s['preview'])
        console.print(t)
        return session_msgs, working_dir, undo_count

    if name == '/init':
        path = prof.create_template(working_dir)
        console.print(f'  [tool.ok]✓[/tool.ok] [dim]{path}[/dim]')
        return session_msgs, working_dir, undo_count

    if name == '/claude':
        query = parts[1] if len(parts) > 1 else ''
        if not query:
            console.print('  [warn]사용법:[/warn] /claude <질문>')
            return session_msgs, working_dir, undo_count
        _run_claude_cli(query, session_msgs=session_msgs)
        return session_msgs, working_dir, undo_count

    if name == '/help':
        _print_help()
        return session_msgs, working_dir, undo_count

    console.print(f'  [tool.fail]✗[/tool.fail] 알 수 없는 명령어: [bold]{name}[/bold]  '
                  f'[dim]/ 입력 후 Tab[/dim]')
    return session_msgs, working_dir, undo_count


# ── /files 트리 ───────────────────────────────────────────────────
_IGNORE = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'dist', 'build', '.next'}
_DIR_ICON = '📁'
_FILE_ICONS = {
    '.py': '🐍', '.js': '📜', '.ts': '📘', '.tsx': '📘', '.jsx': '📜',
    '.md': '📝', '.json': '📋', '.toml': '⚙', '.yaml': '⚙', '.yml': '⚙',
    '.sh': '⚡', '.go': '🐹', '.rs': '🦀', '.sql': '🗃',
}


def _print_file_tree(working_dir: str, max_depth: int = 3):
    root_name = os.path.basename(working_dir) or working_dir
    tree = Tree(f'[bold cyan]{root_name}[/bold cyan]', guide_style='dim')

    def _add(node, path: str, depth: int):
        if depth > max_depth:
            return
        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            return
        dirs = [e for e in entries if os.path.isdir(os.path.join(path, e)) and e not in _IGNORE]
        files = [e for e in entries if os.path.isfile(os.path.join(path, e))]
        for d in dirs:
            branch = node.add(f'[bold]{_DIR_ICON} {d}[/bold]')
            _add(branch, os.path.join(path, d), depth + 1)
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            icon = _FILE_ICONS.get(ext, '  ')
            node.add(f'[dim]{icon}[/dim] {f}')

    _add(tree, working_dir, 1)
    console.print(tree)
    console.print()


# ── /help ─────────────────────────────────────────────────────────
def _print_help():
    sections = {
        '대화': ['/clear', '/undo'],
        '실행': ['/plan', '/cplan'],
        '인덱스': ['/index'],
        '진화': ['/improve', '/learn', '/evolve', '/history', '/restore'],
        '파일': ['/cd', '/files'],
        '세션': ['/save', '/resume', '/sessions', '/init'],
        'Claude': ['/claude'],
        '기타': ['/help', '/quit'],
    }
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2), border_style='dim')
    t.add_column('섹션', style='dim', no_wrap=True)
    t.add_column('명령어', style='bold magenta', no_wrap=True)
    t.add_column('설명', style='white')
    for section, cmds in sections.items():
        first = True
        for cmd in cmds:
            desc = SLASH_COMMANDS.get(cmd, '').split('  ex)')[0]
            t.add_row(section if first else '', cmd, desc)
            first = False
    console.print('[bold]명령어[/bold]')
    console.print(t)
    console.print(
        '  [dim]@claude <질문>[/dim] — Claude에게 직접 질문 (세션에 기록)\n'
        '  [dim]@claude [/dim] 로 시작하는 입력은 슬래시 없이도 동작합니다\n'
    )


# ── 메인 ──────────────────────────────────────────────────────────
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


def main():
    working_dir = os.path.abspath(os.environ.get('HARNESS_CWD') or os.getcwd())
    profile = prof.load(working_dir)
    config.runtime_override(profile)
    session_msgs: list = []
    undo_count: int = 0

    print_banner()
    print_welcome(working_dir)

    # MCP 서버 초기화
    _mcp_clients: dict[str, StdioMCPClient] = {}
    if profile.get('mcp_servers'):
        _mcp_clients = _start_mcp_servers(profile)
        if _mcp_clients:
            registered = register_mcp_tools(_mcp_clients)
            if registered:
                console.print(f'  [dim]MCP 툴 등록: {len(registered)}개[/dim]\n')

    if profile.get('auto_index'):
        _auto_sync(working_dir)

    # proposer용 툴 통계 수집 래퍼 (_effective_on_tool로 분리해 스코프 충돌 방지)
    if profile.get('auto_evolve', False):
        from evolution.proposer import record_tool_call as _record_tool_call

        def _effective_on_tool(name: str, args: dict, result):
            on_tool(name, args, result)
            if result is not None:
                _tool_call_sequence.append(name)
                _record_tool_call(name, bool(result.get('ok')))
    else:
        _effective_on_tool = on_tool


    # 파이프 입력
    if not sys.stdin.isatty():
        pipe_input = sys.stdin.read().strip()
        try:
            sys.stdin = open('/dev/tty')
        except Exception:
            pass
        if pipe_input:
            console.print(f'  [dim]파이프 입력 ({len(pipe_input)}자)[/dim]\n')
            snippets = get_context_snippets(pipe_input, working_dir, profile)
            _response_header()
            _ui.reset()
            _, session_msgs = agent.run(
                pipe_input,
                session_messages=session_msgs,
                working_dir=working_dir,
                profile=profile,
                context_snippets=snippets,
                on_token=on_token,
                on_tool=_effective_on_tool,
                confirm_write=confirm_write if profile.get('confirm_writes', True) else None,
                confirm_bash=confirm_bash if profile.get('confirm_bash', True) else None,
                hooks=profile.get('hooks', {}),
            )
            _response_footer()

    # 미등록 툴 + 툴 시퀀스 수집 — proposer용
    _unknown_tools: list[str] = []
    _all_unknown_tools: list[str] = []  # 세션 전체 누적
    _tool_call_sequence: list[str] = []  # 세션 전체 툴 호출 순서

    def _on_unknown_tool(name: str):
        if name not in _unknown_tools:
            _unknown_tools.append(name)
        if name not in _all_unknown_tools:
            _all_unknown_tools.append(name)

    def _run_agent(user_input, *, plan_mode=False, context_snippets=''):
        nonlocal session_msgs
        _unknown_tools.clear()
        _token_buf.clear()
        _spinner.start()

        if needs_compaction(session_msgs):
            console.print('  [dim]세션 압축 중...[/dim]')
            new_msgs, dropped = compact(session_msgs)
            session_msgs = new_msgs
            console.print(f'  [dim]압축 완료 (메시지 {dropped}개 요약)[/dim]')

        _, session_msgs = agent.run(
            user_input,
            session_messages=session_msgs,
            working_dir=working_dir,
            profile=profile,
            context_snippets=context_snippets,
            plan_mode=plan_mode,
            on_token=on_token,
            on_tool=_effective_on_tool,
            confirm_write=confirm_write if profile.get('confirm_writes', True) else None,
            confirm_bash=confirm_bash if profile.get('confirm_bash', True) else None,
            hooks=profile.get('hooks', {}),
            on_unknown_tool=_on_unknown_tool,
        )
        _flush_tokens()
        _suggest_unknown_tools(_unknown_tools)

    while True:
        try:
            turns = len([m for m in session_msgs if m['role'] == 'user'])
            user_input = get_input(turns, working_dir).strip()

            if not user_input:
                continue

            # @claude 프리픽스 — Claude CLI 질문 (세션에 기록)
            if user_input.startswith('@claude '):
                _run_claude_cli(user_input[8:].strip(), session_msgs=session_msgs)
                continue

            if user_input.startswith('/'):
                if user_input in ('/quit', '/exit', '/q'):
                    evolution.run(
                        session_msgs=session_msgs,
                        working_dir=working_dir,
                        profile=profile,
                        console=console,
                        agent_run=agent.run,
                        on_token=on_token,
                        on_tool=_effective_on_tool,
                        confirm_write=lambda p: True,
                        undo_count=undo_count,
                        unknown_tools=_all_unknown_tools,
                        tool_call_sequence=_tool_call_sequence,
                    )
                    if session_msgs and Confirm.ask('  세션을 저장할까요?', default=False):
                        fn = sess.save(session_msgs, working_dir)
                        console.print(f'  [dim]저장됨: {fn}[/dim]')
                    console.print('  [dim]종료[/dim]')
                    break
                session_msgs, working_dir, undo_count = handle_slash(
                    user_input, session_msgs, working_dir, profile, undo_count
                )
                if user_input.startswith('/cd'):
                    profile = prof.load(working_dir)
                continue

            # 자연어로 /cplan 트리거 감지
            if _is_cplan_intent(user_input):
                task = _extract_cplan_task(user_input)
                session_msgs = do_cplan(task, session_msgs, working_dir, profile)
                continue

            snippets = get_context_snippets(user_input, working_dir, profile)
            _response_header()
            _ui.reset()
            _run_agent(user_input, context_snippets=snippets)
            _response_footer()

        except (KeyboardInterrupt, EOFError):
            console.print('\n  [dim]종료[/dim]')
            break

    for client in _mcp_clients.values():
        client.stop()


if __name__ == '__main__':
    main()
