'''Claude 위임 — 메시지 변환 헬퍼 (Phase 3.1-D).

여기에 모은 것 (pure 변환 함수만):
- _truncate_for_claude — 긴 메시지 head+tail 보존 잘라내기 (CONCERNS §1.15)
- _build_claude_context — session 메시지 → Claude 컨텍스트 블록
- _summarize_session_for_claude — 최근 메시지에서 툴 결과 요약

`_run_claude_cli` / `do_claude_loop`는 main의 spinner/console/agent.run/
context_snippets 등 결합이 깊어 별도 후속 phase에서 DI 정리 후 이동.
'''
import config


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
