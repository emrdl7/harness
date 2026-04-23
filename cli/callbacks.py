'''UI 콜백 + 상태 — main.py에서 분리(Phase 3.1-F-1).

REPL 레이어의 가변 상태(spinner, token buffer, UIState, ctx_display)와 이를
참조하는 콜백들을 한 모듈로 모은다. agent.run(on_token=..., on_tool=...)에
전달되는 콜백은 전부 여기서 import 한다.

모은 것:
- _spinner / _token_buf / _flush_tokens — 스트리밍 토큰 버퍼링
- _UIState / _ui — 툴 실행 시작 시각 추적
- on_token / on_tool — agent.run 스트리밍 콜백
- confirm_write / confirm_bash — Write/Run 사용자 확인 (+ diff 미리보기)
- _INSTALLABLE_TOOLS / _suggest_unknown_tools — 미등록 툴 안내
- _ctx_display / _response_header / _response_footer — 응답 구분선

main.py는 호환을 위해 이 심볼을 re-export한다.
'''
import os
import time
import difflib

from rich.prompt import Confirm

import config
from cli.render import (
    console,
    _Spinner,
    _tool_meta_for,
    _tool_result_hint,
    _infer_tool_purpose,
)


# ── 스트리밍 상태 ──────────────────────────────────────────────────
_spinner = _Spinner()
_token_buf: list[str] = []


def _flush_tokens():
    _spinner.stop()
    text = ''.join(_token_buf).strip()
    if text:
        console.print(f'\n[orange3]● {config.MODEL}[/orange3]')
        # 각 줄에 2칸 들여쓰기 적용
        indented = '\n'.join('  ' + l for l in text.splitlines())
        console.out(indented, highlight=False)
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


# ── agent 스트리밍 콜백 ────────────────────────────────────────────
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


def confirm_write(path: str, content: str = None) -> bool:
    _flush_tokens()
    if content is not None:
        # diff 미리보기
        try:
            if os.path.exists(path):
                with open(path, encoding='utf-8', errors='replace') as f:
                    old_lines = f.readlines()
                label = path
            else:
                old_lines = []
                label = f'{path} (새 파일)'
            new_lines = [l if l.endswith('\n') else l + '\n' for l in content.splitlines()]
            diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=label, tofile=label, lineterm=''))
            if diff:
                for line in diff[:60]:
                    if line.startswith('+++') or line.startswith('---'):
                        console.print(f'  [dim]{line}[/dim]')
                    elif line.startswith('+'):
                        console.print(f'  [green]{line}[/green]')
                    elif line.startswith('-'):
                        console.print(f'  [red]{line}[/red]')
                    elif line.startswith('@@'):
                        console.print(f'  [cyan]{line}[/cyan]')
                    else:
                        console.print(f'  [dim]{line}[/dim]')
                if len(diff) > 60:
                    console.print(f'  [dim]... (이하 {len(diff)-60}줄 생략)[/dim]')
            else:
                console.print(f'  [dim]변경 없음[/dim]')
        except Exception:
            pass
    return Confirm.ask(f'[bold]●[/bold] [warn]Write[/warn] [bold]{path}[/bold]')


def confirm_bash(command: str) -> bool:
    _flush_tokens()
    return Confirm.ask(f'[bold]●[/bold] [bold red]Run[/bold red] [bold]{command[:100]}[/bold]')


# ── Thinking 블록 콜백 ─────────────────────────────────────────────
# 기본 정책: reasoning 모델의 <think>...</think> 내용은 화면에 실시간으로
# 찍지 않는다. 끝나면 "▸ N초 동안 생각함 · M 토큰" 한 줄 요약만 표시.
# 원본은 session_msgs의 assistant._thinking 필드에 저장돼 /think 로 펼침.
_thought_buf: list[str] = []


def on_thought(token: str):
    '''사고 토큰 수신 — 현재는 숨김(버퍼만). 디버그 모드 확장 여지.'''
    _thought_buf.append(token)


def on_thought_end(text: str, duration: float, tokens: int):
    '''</think> 도달 시 한 줄 요약. answer 스트림이 뒤따르므로 _flush_tokens()
    로 answer 버퍼는 비우지 않음 (아직 시작 안 함). _spinner만 잠시 멈췄다가
    곧 answer 토큰이 시작되면 자연스럽게 재개됨.'''
    _spinner.stop()
    console.print(
        f'  [dim]▸ {duration:.1f}초 동안 생각함 · {tokens} 토큰  '
        f'[/dim][dim italic]/think 로 펼치기[/dim italic]'
    )
    _thought_buf.clear()
    # answer 스트림이 곧 재개되므로 spinner 다시 활성화
    _spinner.start()


# ── 미등록 툴 제안 ────────────────────────────────────────────────
_INSTALLABLE_TOOLS = {
    'search_web':  ('web.py', 'duckduckgo_search'),
    'fetch_page':  ('web.py', None),
    'search_code': ('search.py', None),
}


def _suggest_unknown_tools(items: list[tuple[str, dict]]):
    if not items:
        return
    seen = set()
    for name, args in items:
        if name in seen:
            continue
        seen.add(name)

        info = _INSTALLABLE_TOOLS.get(name)
        if info:
            module_file, pkg = info
            pkg_note = f' [dim](pip install {pkg})[/dim]' if pkg else ''
            console.print(
                f'\n[bold]●[/bold] [warn]미등록 툴:[/warn] [bold]{name}[/bold]{pkg_note}\n'
                f'  [dim]tools/{module_file} 에 구현 후 tools/__init__.py에 등록하세요[/dim]'
            )
        else:
            purpose, args_str = _infer_tool_purpose(name, args)
            console.print(f'\n[bold]●[/bold] [warn]미등록 툴 감지:[/warn] [bold]{name}[/bold]')
            console.print(f'  추정 기능: {purpose}')
            console.print(f'  추가 방법: [dim]tools/{name}.py 구현 → tools/__init__.py 에 등록[/dim]')
            if args_str:
                console.print(f'  {args_str}')
            if Confirm.ask('  하네스에 추가할까요?', default=False):
                console.print(
                    f'  [tool.ok]✓[/tool.ok] /improve 를 실행하면 자동 구현을 시도합니다\n'
                    f'  [dim]또는 tools/{name}.py 를 직접 작성하세요[/dim]'
                )


# ── 응답 구분선 ────────────────────────────────────────────────────
_ctx_display: list = ['']  # main()이 _run_agent 전에 갱신 (mutable container)


def _response_header(model_label: str | None = None):
    ctx = _ctx_display[0]
    suffix = f'  {ctx}' if ctx else ''
    console.print(f'\n[dim]{model_label or config.MODEL}[/dim]{suffix}')


def _response_footer():
    console.print()
