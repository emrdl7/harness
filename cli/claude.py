'''Claude 위임 — 메시지 변환 헬퍼 + REPL 바인딩 함수.

Phase 3.1-D에서 pure 변환 함수(_truncate_for_claude / _build_claude_context /
_summarize_session_for_claude)를 먼저 옮겼고, Phase 3.1-F-2에서 REPL 상태에
결합된 _run_claude_cli / do_claude_loop 를 이어서 이동한다. DI "정리"는 이전의
self-referential module global(main.*)을 cli.callbacks/cli.setup 모듈 단위로
정돈하는 형태 — REPL 전역은 cli.callbacks 한 곳에만 살도록.

이 모듈에 모은 것:
- _truncate_for_claude / _build_claude_context / _summarize_session_for_claude
  (pure, Phase 3.1-D)
- _run_claude_cli — @claude / /claude — 단발 Claude 호출, 세션 기록 옵션
- do_claude_loop — /cloop — Claude ↔ 로컬모델 계획/실행/검토 N라운드 루프
  (최대 _CLOOP_MAX_ROUNDS).

main.py는 호환을 위해 이 심볼을 re-export한다.
'''
import agent
import config
from tools.claude_cli import ask as claude_ask, is_available as claude_available

from cli.render import console
from cli.callbacks import (
    _spinner,
    _token_buf,
    _flush_tokens,
    _ui,
    on_token,
    on_tool,
    confirm_write,
    confirm_bash,
    _response_footer,
)
from cli.setup import get_context_snippets


_CLAUDE_CTX_HEAD = 400
_CLAUDE_CTX_TAIL = 400


def _truncate_for_claude(content: str) -> str:
    '''CONCERNS.md §1.15 대응: head만 자르면 tool 결과(가장 중요한 tail)가
    날아갔음. head+tail을 유지하고 중간 생략을 명시 마커로 표시.'''
    max_chars = _CLAUDE_CTX_HEAD + _CLAUDE_CTX_TAIL
    if len(content) <= max_chars:
        return content
    omitted = len(content) - max_chars
    return (
        content[:_CLAUDE_CTX_HEAD]
        + f'\n…[중간 {omitted}자 생략]…\n'
        + content[-_CLAUDE_CTX_TAIL:]
    )


def _build_claude_context(session_msgs: list, max_turns: int = 6) -> str:
    '''session_msgs에서 최근 대화를 컨텍스트 블록으로 변환.
    에이전트 레이블에 모델명을 붙여 Claude가 로컬 모델 답변임을 인식하게 함.'''
    non_system = [m for m in session_msgs if m['role'] in ('user', 'assistant')]
    recent = non_system[-(max_turns * 2):]
    if not recent:
        return ''
    local_model = config.MODEL  # 예: qwen3-coder:30b
    lines = [f'아래는 현재 세션의 최근 대화 기록이다. 에이전트는 로컬 모델({local_model})이고 너(Claude)와 다른 모델임:\n']
    for m in recent:
        if m['role'] == 'user':
            role = '사용자'
        else:
            role = f'로컬모델({local_model})'
        content = (m.get('content') or '').strip()
        if content:
            lines.append(f'[{role}]: {_truncate_for_claude(content)}')
    lines.append('')
    return '\n'.join(lines)


def _summarize_session_for_claude(msgs: list, last_n: int = 10) -> str:
    '''최근 메시지에서 툴 실행 결과를 요약 (cloop 검토용).'''
    parts = []
    for m in msgs[-last_n:]:
        role = m.get('role', '')
        content = str(m.get('content', ''))[:500]
        if role == 'tool':
            parts.append(f'[툴 결과] {content}')
        elif role == 'assistant' and content:
            parts.append(f'[모델 응답] {content}')
    return '\n'.join(parts) or '(결과 없음)'


# ── /claude, @claude — 단발 Claude 호출 ──────────────────────────
def _run_claude_cli(query: str, session_msgs: list | None = None, working_dir: str | None = None, model: str | None = None) -> str:
    if not claude_available():
        console.print(
            '  [tool.fail]✗[/tool.fail] claude CLI를 찾을 수 없습니다\n'
            '  [dim]설치: https://claude.ai/code[/dim]'
        )
        return ''

    # 세션 컨텍스트를 query 앞에 붙여 Claude가 대화 흐름을 알 수 있게 함
    if session_msgs:
        ctx = _build_claude_context(session_msgs)
        full_query = f'{ctx}위 대화를 참고해서 다음 질문에 답해줘: {query}' if ctx else query
    else:
        full_query = query

    _token_buf.clear()
    _spinner.start()

    collected = []
    _first_token = [True]

    try:
        def _tok(line):
            if _first_token[0]:
                _first_token[0] = False
                _flush_tokens()  # 스피너 정지
                console.print('\n[bold blue]● Claude[/bold blue]')
            collected.append(line)
            console.print('  ' + line, end='', highlight=False, markup=False)
        claude_ask(full_query, on_token=_tok, cwd=working_dir, model=model)
    except RuntimeError as e:
        _spinner.stop()
        console.print(f'\n  [tool.fail]✗[/tool.fail] {e}\n')
        return ''
    except KeyboardInterrupt:
        _spinner.stop()
        console.print('\n  [dim]중단됨[/dim]\n')
        return ''

    if _first_token[0]:
        _flush_tokens()  # 토큰이 없었던 경우에도 스피너 정지

    console.print('\n')

    response = ''.join(collected).strip()

    if session_msgs is not None and response:
        session_msgs.append({'role': 'user', 'content': f'[Claude에게 질문]\n{query}'})
        session_msgs.append({'role': 'assistant', 'content': f'[Claude 답변]\n{response}'})

    return response


# ── /cloop: Claude ↔ harness 협업 루프 ───────────────────────────
_CLOOP_PLAN_TMPL = '''\
다음 작업을 분석하고 실행 계획을 작성해줘.
작업 디렉토리: {working_dir}
작업: {task}

형식:
1. 각 단계를 번호 목록으로
2. 어떤 파일을 읽고/쓸지 명시
3. 코드 변경이 필요하면 핵심 로직 포함
4. 주의사항/엣지케이스 언급

로컬 코딩 모델이 이 플랜만 보고 바로 실행할 수 있도록 구체적으로 작성해.
'''

_CLOOP_REVIEW_TMPL = '''\
로컬 모델이 작업을 실행했습니다. 결과를 검토하고 다음 중 하나로 답해줘:

[실행 결과]
{result_summary}

원래 작업: {task}

- 작업이 완료됐으면: 첫 줄에 [완료] 라고 쓰고 요약해줘
- 수정/추가 작업이 필요하면: 구체적인 보정 지시사항을 작성해줘 (로컬 모델이 바로 실행할 수 있게)
'''

_CLOOP_MAX_ROUNDS = 5


def do_claude_loop(task: str, session_msgs: list, working_dir: str, profile: dict) -> list:
    if not claude_available():
        console.print('  [tool.fail]✗[/tool.fail] claude CLI를 찾을 수 없습니다')
        return session_msgs

    snippets = get_context_snippets(task, working_dir, profile)

    for round_num in range(1, _CLOOP_MAX_ROUNDS + 1):
        # ── Claude: 계획 or 검토 ──────────────────────────────────
        if round_num == 1:
            prompt = _CLOOP_PLAN_TMPL.format(task=task, working_dir=working_dir)
            console.print(f'\n[bold blue]● Claude[/bold blue] [dim]({round_num}라운드) 플랜 작성 중...[/dim]')
        else:
            result_summary = _summarize_session_for_claude(session_msgs)
            prompt = _CLOOP_REVIEW_TMPL.format(task=task, result_summary=result_summary)
            console.print(f'\n[bold blue]● Claude[/bold blue] [dim]({round_num}라운드) 결과 검토 중...[/dim]')

        collected = []
        try:
            def _tok(line):
                collected.append(line)
                console.print(line, end='', highlight=False, markup=False)
            claude_ask(prompt, on_token=_tok, cwd=working_dir)
        except (RuntimeError, KeyboardInterrupt) as e:
            console.print(f'\n  [tool.fail]✗[/tool.fail] {e}')
            break

        claude_response = ''.join(collected).strip()
        console.print('\n')

        if not claude_response:
            break

        session_msgs.append({'role': 'user', 'content': f'[Claude {round_num}라운드]\n{claude_response}'})

        # 완료 신호 감지
        if '[완료]' in claude_response or '[DONE]' in claude_response.upper():
            console.print('  [tool.ok]✓[/tool.ok] [bold]Claude가 작업 완료를 확인했습니다[/bold]')
            break

        # ── harness: 실행 ─────────────────────────────────────────
        execute_prompt = (
            f'아래 지시사항을 실행해줘. 파일 읽기/쓰기가 필요하면 도구를 사용해.\n\n'
            f'{claude_response}\n\n원래 작업: {task}'
        )

        console.print(f'\n[dim]● {config.MODEL} ({round_num}라운드 실행)[/dim]')
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

    else:
        console.print(f'  [warn]⚠[/warn] 최대 라운드({_CLOOP_MAX_ROUNDS})에 도달했습니다')

    return session_msgs
