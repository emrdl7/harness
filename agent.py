import json
import os
import re
import time
import requests
import config
from tools import TOOL_DEFINITIONS, TOOL_MAP
from tools.shell import classify_command
from tools.hooks import run_hook
from session.logger import log_tool_failure, log_reflection
import skills

MAX_TOOL_RESULT_CHARS = 20_000

SYSTEM_PROMPT = f'''당신은 코드 작성 전문 AI 에이전트입니다.
당신의 실제 모델명은 {config.MODEL}입니다. 자신의 정체를 물으면 이 모델명을 정확히 답하세요.
Anthropic의 Claude가 아니며, Claude 기반이라고 주장하지 마세요.
파일 읽기/쓰기, 코드 실행, git 툴을 사용해 사용자의 요청을 완수하세요.
툴 호출 후 실패하면 원인을 분석하고 다른 방법으로 재시도하세요.
작업 완료 후 결과를 간결하게 한국어로 보고하세요.

웹 검색 규칙 (최우선):
- 다음 유형의 질문은 반드시 search_web을 먼저 호출한 뒤 답변하세요. 스스로 안다고 생각해도 검색을 먼저 하세요:
  · 특정 모델/라이브러리/프레임워크의 버전 비교 또는 성능 차이
  · 특정 제품·서비스의 출시일, 기능, 스펙
  · 2024년 이후 출시되거나 업데이트된 것들
  · 뉴스, 최신 동향, 릴리즈 노트
- 검색 결과가 충분하지 않으면 쿼리를 바꿔 재검색하거나 fetch_page로 관련 URL을 직접 열어보세요.
- 검색 결과를 받으면 그 내용을 바탕으로 구체적으로 답변하세요. "결과에 없다"는 이유로 포기하지 마세요.
- 성능 비교 질문은 반드시 수치(벤치마크 점수, 배수, %, 순위 등)로 답하세요. "더 빠르다", "더 좋다" 같은 막연한 표현은 금지. 수치가 스니펫에 없으면 fetch_page로 상세 페이지를 열어 수치를 직접 확인하세요.

Claude 위임 규칙 (ask_claude):
- 다음 상황에서는 ask_claude를 호출해 Claude에게 위임하세요:
  · 동일한 접근 방법으로 2회 이상 실패한 경우
  · 5개 이상의 파일에 걸친 아키텍처 수준의 리팩토링
  · 원인을 알 수 없는 버그 디버깅
  · 사용자가 "Claude에게", "더 정확하게", "claude로" 등을 명시한 경우
- 다음은 직접 처리하세요 (ask_claude 사용 금지):
  · 단순 파일 편집, 단일 함수 구현, 반복 패턴 작업, 문서화

일반 규칙:
- 현재 작업 디렉토리는 이 프롬프트에 명시되어 있으므로 별도 툴 호출 없이 직접 답변하세요.
- 존재하지 않는 툴을 절대 호출하지 마세요. 사용 가능한 툴만 사용하세요.
- 파일 경로는 항상 절대 경로 또는 working_dir 기준 상대 경로를 사용하세요.'''

_REFLECTION_PREFIX = '이전 툴 호출이 실패했습니다. 아래 오류를 분석하고 다른 접근 방법으로 재시도하거나, 불가능한 이유를 설명하세요.\n\n실패 목록:\n'

PLAN_PROMPT = '''다음 작업을 실행하기 전에 단계별 계획을 먼저 작성하세요.
형식:
1. [단계명]: 설명
2. [단계명]: 설명
...

계획 작성 후 "계획 완료"라고 말하면 실행을 시작합니다.'''


def _stream_response(messages: list, on_token=None) -> dict:
    payload = {
        'model': config.MODEL,
        'messages': messages,
        'tools': TOOL_DEFINITIONS,
        'stream': True,
        'options': config.OLLAMA_OPTIONS,
    }
    resp = requests.post(
        f'{config.OLLAMA_BASE_URL}/api/chat',
        json=payload,
        stream=True,
        timeout=300,
    )
    resp.raise_for_status()

    accumulated = ''
    tool_calls = []

    for line in resp.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        msg = chunk.get('message', {})
        token = msg.get('content', '')
        if token:
            accumulated += token
            if on_token:
                on_token(token)
        if msg.get('tool_calls'):
            tool_calls = msg['tool_calls']
        if chunk.get('done'):
            break

    return {'role': 'assistant', 'content': accumulated, 'tool_calls': tool_calls}


def _parse_text_tool_calls(text: str) -> list:
    '''모델이 텍스트로 툴콜을 출력한 경우 파싱. JSON/XML 두 형식 모두 지원.'''
    calls = []

    # JSON 형식: {"name": "...", "arguments": {...}}
    json_pattern = r'\{[^{}]*"name"\s*:\s*"([^"]+)"[^{}]*"arguments"\s*:\s*(\{[^{}]*\})[^{}]*\}'
    for m in re.finditer(json_pattern, text, re.DOTALL):
        try:
            calls.append({'function': {'name': m.group(1), 'arguments': json.loads(m.group(2))}})
        except json.JSONDecodeError:
            pass

    # XML 형식: <function=name><parameter=key>value</parameter></function>
    xml_pattern = r'<function=(\w+)>(.*?)</function>'
    for m in re.finditer(xml_pattern, text, re.DOTALL):
        name = m.group(1)
        args = {}
        for p in re.finditer(r'<parameter=(\w+)>\s*(.*?)\s*</parameter>', m.group(2), re.DOTALL):
            args[p.group(1)] = p.group(2).strip()
        calls.append({'function': {'name': name, 'arguments': args}})

    return calls


def _build_system(working_dir: str, profile: dict, context_snippets: str = '') -> str:
    parts = [SYSTEM_PROMPT, f'\n현재 작업 디렉토리: {working_dir}']

    if profile.get('global_doc'):
        parts.append(f'\n--- HARNESS.md ---\n{profile["global_doc"]}')

    if profile.get('project_doc'):
        label = os.path.basename(profile.get('project_doc_path', 'HARNESS.md'))
        parts.append(f'\n--- {label} ---\n{profile["project_doc"]}')

    for name, content in profile.get('extra_docs', []):
        parts.append(f'\n--- {name} ---\n{content}')

    if profile.get('conventions'):
        parts.append(f'\n코드 컨벤션:\n{profile["conventions"]}')

    if context_snippets:
        parts.append(f'\n{context_snippets}')

    return '\n'.join(parts)


def run(
    user_input: str,
    session_messages: list = None,
    working_dir: str = '.',
    profile: dict = None,
    context_snippets: str = '',
    plan_mode: bool = False,
    on_token=None,
    on_tool=None,
    confirm_write=None,
    confirm_bash=None,
    on_unknown_tool=None,
    hooks: dict = None,
) -> tuple[str, list]:
    if session_messages is None:
        session_messages = []
    if profile is None:
        profile = {}

    if not session_messages:
        system_content = _build_system(working_dir, profile, context_snippets)
        session_messages.append({'role': 'system', 'content': system_content})

    # 관련 스킬 감지 → user 메시지 앞에 주입
    skill_context = skills.build_context(user_input)
    content = user_input
    if skill_context:
        content = f'{skill_context}\n\n---\n{user_input}'

    # 계획 모드: 실행 전 계획 먼저
    if plan_mode:
        session_messages.append({'role': 'user', 'content': PLAN_PROMPT + f'\n\n작업: {content}'})
    else:
        session_messages.append({'role': 'user', 'content': content})

    consecutive_failures = 0
    _start = time.time()
    _tool_call_history: list[tuple[str, str]] = []  # (tool_name, args_hash)

    for iteration in range(config.MAX_ITERATIONS):
        if time.time() - _start > config.AGENT_TIMEOUT:
            run_hook((hooks or {}).get('on_stop', ''), 'on_stop', working_dir=working_dir)
            return f'에이전트 타임아웃 ({config.AGENT_TIMEOUT}초 초과)', session_messages
        msg = _stream_response(session_messages, on_token=on_token)
        session_messages.append(msg)

        tool_calls = msg.get('tool_calls', [])
        if not tool_calls and msg.get('content'):
            tool_calls = _parse_text_tool_calls(msg['content'])

        if not tool_calls:
            run_hook((hooks or {}).get('on_stop', ''), 'on_stop', working_dir=working_dir)
            return msg.get('content', ''), session_messages

        had_failure = False
        iteration_errors = []
        unknown_tool_count = 0

        for tc in tool_calls:
            fn_name = tc['function']['name']
            args = tc['function'].get('arguments', {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}

            # 파일 쓰기/수정 확인
            if fn_name in ('write_file', 'edit_file') and confirm_write:
                _cw_content = args.get('content') if fn_name == 'write_file' else None
                if not confirm_write(args.get('path', '?'), _cw_content):
                    result = {'ok': False, 'error': '사용자가 취소했습니다'}
                    if on_tool:
                        on_tool(fn_name, args, result)
                    session_messages.append({
                        'role': 'tool',
                        'content': json.dumps(result, ensure_ascii=False),
                    })
                    continue

            # 위험 Bash 명령 확인
            if fn_name == 'run_command' and confirm_bash:
                cmd = args.get('command', '')
                if classify_command(cmd) == 'dangerous':
                    if not confirm_bash(cmd):
                        result = {'ok': False, 'error': '사용자가 취소했습니다'}
                        if on_tool:
                            on_tool(fn_name, args, result)
                        session_messages.append({
                            'role': 'tool',
                            'content': json.dumps(result, ensure_ascii=False),
                        })
                        continue

            # pre_tool_use 훅 — False 반환 시 툴 차단
            _hooks = hooks or {}
            if not run_hook(_hooks.get('pre_tool_use', ''), 'pre_tool_use',
                            tool=fn_name, args=args, working_dir=working_dir):
                result = {'ok': False, 'error': '훅에 의해 차단됨'}
                if on_tool:
                    on_tool(fn_name, args, result)
                session_messages.append({
                    'role': 'tool',
                    'content': json.dumps(result, ensure_ascii=False),
                })
                continue

            if on_tool:
                on_tool(fn_name, args, None)

            # shell 툴은 working_dir를 cwd로 자동 주입
            if fn_name in ('run_command', 'run_python') and 'cwd' not in args:
                args = {**args, 'cwd': working_dir}

            fn = TOOL_MAP.get(fn_name)
            if fn:
                try:
                    result = fn(**args)
                except TypeError as e:
                    result = {'ok': False, 'error': f'인자 오류: {e}'}
            else:
                result = {
                    'ok': False,
                    'error': f'툴 "{fn_name}"은 존재하지 않습니다. 툴을 호출하지 말고 자연어로 직접 답변해 주세요.',
                    '_unknown_tool': fn_name,
                }
                unknown_tool_count += 1
                if on_unknown_tool:
                    on_unknown_tool(fn_name, args)

            if on_tool:
                on_tool(fn_name, args, result)

            # 반복 감지용 히스토리 기록
            _tool_call_history.append((fn_name, json.dumps(args, sort_keys=True)))

            # post_tool_use 훅 (비동기 무시)
            run_hook(_hooks.get('post_tool_use', ''), 'post_tool_use',
                     tool=fn_name, args=args, result_ok=result.get('ok'), working_dir=working_dir)

            if not result.get('ok'):
                had_failure = True
                err = result.get('error', result.get('stderr', ''))
                log_tool_failure(fn_name, args, str(err)[:200], working_dir)
                iteration_errors.append(f'{fn_name}: {str(err)[:120]}')

            result_str = json.dumps(result, ensure_ascii=False)
            if len(result_str) > MAX_TOOL_RESULT_CHARS:
                omitted = len(result_str) - MAX_TOOL_RESULT_CHARS
                result_str = result_str[:MAX_TOOL_RESULT_CHARS] + f'... [truncated: {omitted}자 생략. offset/limit으로 부분 읽기 또는 grep_search 사용]'
            session_messages.append({
                'role': 'tool',
                'content': result_str,
            })

        # 미등록 툴만 호출한 경우: 즉시 자연어 답변 유도
        if unknown_tool_count == len(tool_calls):
            session_messages.append({
                'role': 'user',
                'content': '존재하지 않는 툴을 호출했습니다. 툴 없이 자연어로 바로 답변해 주세요.',
            })
            consecutive_failures = 0
            continue

        # 반복 감지: 최근 3회 동일 툴+인자 반복 시 강제 개입
        REPEAT_WINDOW = 3
        if len(_tool_call_history) >= REPEAT_WINDOW:
            recent = _tool_call_history[-REPEAT_WINDOW:]
            if all(tc == recent[0] for tc in recent):
                session_messages.append({
                    'role': 'user',
                    'content': (
                        f'동일한 툴({recent[0][0]})을 같은 인자로 {REPEAT_WINDOW}회 반복했습니다. '
                        '다른 접근 방법을 시도하거나, 진행이 불가능한 이유를 사용자에게 설명하세요.'
                    ),
                })
                _tool_call_history.clear()
                consecutive_failures = 0
                continue

        # 반성 루프: 연속 실패 시 분석 유도
        if had_failure:
            consecutive_failures += 1
            if consecutive_failures >= config.REFLECTION_THRESHOLD:
                log_reflection('연속 툴 실패로 반성 루프 진입')
                error_detail = '\n'.join(f'- {e}' for e in iteration_errors)
                session_messages.append({
                    'role': 'user',
                    'content': _REFLECTION_PREFIX + error_detail,
                })
                consecutive_failures = 0
        else:
            consecutive_failures = 0

    run_hook((hooks or {}).get('on_stop', ''), 'on_stop', working_dir=working_dir)
    return f'최대 반복 횟수 초과 ({config.MAX_ITERATIONS}회)', session_messages
