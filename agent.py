import json
import os
import re
import time
from collections import deque

import requests
import config
from tools import TOOL_DEFINITIONS, TOOL_MAP
from tools.shell import classify_command, should_confirm
from tools.hooks import run_hook
from session.logger import log_tool_failure, log_reflection
import skills

MAX_TOOL_RESULT_CHARS = 20_000


# ── Thinking 스트리밍 파서 ────────────────────────────────────────
class _ThinkingParser:
    '''Ollama 스트리밍 토큰에서 <think>...</think> 블록을 분리한다.

    로컬 reasoning 모델(DeepSeek-R1, Qwen3 thinking 등)이 사고 과정을
    <think> 태그로 감싸서 출력할 때, 답변 토큰과 사고 토큰을 다른 콜백으로
    라우팅한다. 사고 블록이 없는 일반 모델에서는 기존 동작과 동일
    (전부 on_answer로 흘러감).

    - on_answer(text): 일반 답변 토큰 (기존 on_token 역할)
    - on_thought(text): 사고 블록 내부 토큰. None이면 버림
    - on_thought_end(text, duration, tokens): </think> 만날 때 호출.
      text=사고 전체, duration=<think>→</think> 경과 초, tokens=대략 추정

    토큰 경계가 태그 중간을 가르는 경우('<th'|'ink>')를 처리하기 위해
    tail prefix를 carry로 홀드한다. 태그 최대 길이는 CLOSE(8) 기준.
    '''
    OPEN = '<think>'
    CLOSE = '</think>'

    def __init__(self, on_answer=None, on_thought=None, on_thought_end=None):
        self.on_answer = on_answer
        self.on_thought = on_thought
        self.on_thought_end = on_thought_end
        self._mode = 'answer'          # 'answer' or 'thought'
        self._carry = ''               # 태그 prefix 후보 suffix 홀드
        self._thought_start_ts = 0.0
        self._thought_buf: list[str] = []
        self.accumulated = ''          # answer 파트만 — session_messages content와 매칭
        self._thinkings: list[dict] = []  # 완료 블록 [{text, duration, tokens}]

    def feed(self, token: str):
        data = self._carry + token
        self._carry = ''
        while data:
            if self._mode == 'answer':
                idx = data.find(self.OPEN)
                if idx >= 0:
                    if idx > 0:
                        self._emit_answer(data[:idx])
                    data = data[idx + len(self.OPEN):]
                    self._mode = 'thought'
                    self._thought_start_ts = time.time()
                    self._thought_buf = []
                    continue
                hold = self._tail_hold(data, self.OPEN)
                if hold:
                    if hold < len(data):
                        self._emit_answer(data[:-hold])
                    self._carry = data[-hold:]
                else:
                    self._emit_answer(data)
                data = ''
            else:  # thought
                idx = data.find(self.CLOSE)
                if idx >= 0:
                    if idx > 0:
                        self._emit_thought(data[:idx])
                    data = data[idx + len(self.CLOSE):]
                    text = ''.join(self._thought_buf)
                    duration = time.time() - self._thought_start_ts
                    tokens = max(1, len(text) // 4)
                    self._thinkings.append({'text': text, 'duration': duration, 'tokens': tokens})
                    if self.on_thought_end:
                        self.on_thought_end(text, duration, tokens)
                    self._mode = 'answer'
                    self._thought_buf = []
                    continue
                hold = self._tail_hold(data, self.CLOSE)
                if hold:
                    if hold < len(data):
                        self._emit_thought(data[:-hold])
                    self._carry = data[-hold:]
                else:
                    self._emit_thought(data)
                data = ''

    def flush(self):
        '''스트림 종료 호출 — carry 남은 건 현재 모드로 흘려보낸다.
        미종료 thought는 end 이벤트를 쏘지 않음(`_thinkings`에도 기록 안 함).'''
        if self._carry:
            if self._mode == 'answer':
                self._emit_answer(self._carry)
            else:
                self._emit_thought(self._carry)
            self._carry = ''

    @staticmethod
    def _tail_hold(data: str, tag: str) -> int:
        '''data의 suffix가 tag의 prefix일 수 있는 최대 길이.
        `<th` 가 `<think>`의 prefix인지 체크해서, 맞으면 3 리턴.
        '''
        max_check = min(len(tag) - 1, len(data))
        for k in range(max_check, 0, -1):
            if tag.startswith(data[-k:]):
                return k
        return 0

    def _emit_answer(self, text: str):
        self.accumulated += text
        if self.on_answer:
            self.on_answer(text)

    def _emit_thought(self, text: str):
        self._thought_buf.append(text)
        if self.on_thought:
            self.on_thought(text)

def _system_prompt() -> str:
    '''CONCERNS §3.13: import 시점 f-string 빌드는 config.runtime_override 후
    바뀐 MODEL을 반영 못 함. 호출 시점에 lazy 빌드해 .harness.toml override 반영.
    '''
    return f'''당신은 코드 작성 전문 AI 에이전트입니다.
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
- 파일 경로는 항상 절대 경로 또는 working_dir 기준 상대 경로를 사용하세요.
- 동일한 도구를 한 turn 안에서 5회 이상 호출하지 마세요. 검색/페치 결과가 충분치 않아도 가진 정보로 답변하세요. 부족하면 사용자에게 추가 정보를 요청하세요. 무한 검색은 메모리 부족과 응답 지연을 유발합니다.

툴 결과 표시 규칙 (중요):
- 클라이언트 UI 가 read_file/write_file/edit_file/grep_search/run_command 등의 결과를
  자동으로 카드 형태로 시각화합니다 (코드 미리보기·diff·매치 결과 등).
- 따라서 자연어 답변에 같은 내용을 backtick 코드 블록으로 다시 출력하지 마세요.
  예) read_file 후 파일 전체 내용을 ``` 으로 감싸 다시 출력하는 것 금지.
- 답변에는 결과의 의미·다음 행동·요약만 한두 문장으로 적으세요.
- diff 가 필요한 설명에서도 직접 diff 를 그리지 말고 "위 변경사항은 …" 식으로 카드를 참조하세요.

자연어 답변 시각 표현 규칙 (UI 가 자동 처리하므로 적극 활용):
- 비교/스펙/표 형태의 정보는 GitHub 스타일 마크다운 표를 사용하세요. UI 가 자동 정렬합니다:
    | 항목 | A | B |
    |------|---|---|
    | 속도 | 100ms | 250ms |
- 단순 나열·여러 항목은 - 또는 1. 2. 3. 형식의 목록을 사용하세요.
- 메트릭 / 수치는 단위와 함께 명시하세요 (예: 245ms, 1.2 MB, 98.5%, 60fps). 단위 붙은 숫자는 자동 강조됩니다.
- 파일 경로는 src/foo.ts:42:7 형식으로 줄·열까지 적으면 자동 하이라이트됩니다.
- 코드/명령은 ```lang 펜스로 감싸세요 (lang 명시 권장 — 신택스 하이라이트 적용).
- JSON object/array 는 backtick 펜스 없이 그대로 출력해도 자동으로 정렬+컬러가 적용됩니다.'''

_REFLECTION_PREFIX = '이전 툴 호출이 실패했습니다. 아래 오류를 분석하고 다른 접근 방법으로 재시도하거나, 불가능한 이유를 설명하세요.\n\n실패 목록:\n'

PLAN_PROMPT = '''다음 작업을 실행하기 전에 단계별 계획을 먼저 작성하세요.
형식:
1. [단계명]: 설명
2. [단계명]: 설명
...

계획 작성 후 "계획 완료"라고 말하면 실행을 시작합니다.'''


def _stream_response(messages: list, on_token=None, on_thought=None, on_thought_end=None) -> dict:
    # 백엔드 분기 — MLX 면 OpenAI 호환 경로, 기본은 Ollama
    if config.BACKEND == 'mlx':
        return _stream_mlx_response(messages, on_token, on_thought, on_thought_end)
    payload = {
        'model': config.MODEL,
        'messages': messages,
        'tools': TOOL_DEFINITIONS,
        'stream': True,
        'options': config.OLLAMA_OPTIONS,
    }
    url = f'{config.OLLAMA_BASE_URL}/api/chat'

    # Ollama 연결 최대 3회 재시도 (지수 백오프 1s→2s→4s)
    # 재시도 대상: ConnectionError, Timeout, 5xx 서버 에러. 4xx는 즉시 raise.
    resp = None
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, stream=True, timeout=300)
            if 500 <= resp.status_code < 600:
                resp.close()
                raise requests.HTTPError(f'HTTP {resp.status_code}', response=resp)
            resp.raise_for_status()
            break
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt == 2:
                raise
            delay = 2 ** attempt
            if on_token:
                on_token(f'\n[Ollama 재연결 {attempt + 2}/3 — {delay}s 대기: {type(e).__name__}]\n')
            time.sleep(delay)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status < 500 or attempt == 2:
                raise
            delay = 2 ** attempt
            if on_token:
                on_token(f'\n[Ollama 재연결 {attempt + 2}/3 — {delay}s 대기: HTTP {status}]\n')
            time.sleep(delay)

    parser = _ThinkingParser(
        on_answer=on_token,
        on_thought=on_thought,
        on_thought_end=on_thought_end,
    )
    tool_calls = []

    for line in resp.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        msg = chunk.get('message', {})
        token = msg.get('content', '')
        if token:
            parser.feed(token)
        if msg.get('tool_calls'):
            tool_calls = msg['tool_calls']
        if chunk.get('done'):
            break
    parser.flush()

    # assistant 메시지에 _thinking 필드 부착 (완료된 마지막 블록 기준).
    # Ollama는 payload의 unknown 필드를 무시하므로 세션에 그대로 보관해도 안전.
    # /think 슬래시가 이 필드를 읽는다.
    result = {'role': 'assistant', 'content': parser.accumulated, 'tool_calls': tool_calls}
    if parser._thinkings:
        result['_thinking'] = parser._thinkings[-1]
    return result


def _stream_mlx_response(messages: list, on_token=None, on_thought=None, on_thought_end=None) -> dict:
    '''mlx_lm.server (OpenAI /v1/chat/completions) 백엔드.

    Ollama 와 다른 점:
    - SSE 프레임 (`data: {...}\\n\\n`, `data: [DONE]` 종료, `:keepalive` 주석 무시)
    - delta.content 로 토큰 도착, delta.tool_calls 는 완성 형태로 한 번에 옴
    - delta.reasoning 필드 (Qwen3.6 thinking) 는 on_thought 로 라우팅
    '''
    payload = {
        'model': config.MODEL,
        'messages': messages,
        'tools': TOOL_DEFINITIONS,
        'stream': True,
        'temperature': config.OLLAMA_OPTIONS.get('temperature', 0.2),
        'top_p': config.OLLAMA_OPTIONS.get('top_p', 0.9),
        'max_tokens': config.OLLAMA_OPTIONS.get('num_predict', 4096),
        'chat_template_kwargs': {'enable_thinking': config.MLX_THINKING},
    }
    url = f'{config.MLX_BASE_URL}/v1/chat/completions'

    # 재시도 — Ollama 경로와 동일 정책 (3회, 지수 백오프, 5xx/Connection/Timeout 만 재시도)
    resp = None
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, stream=True, timeout=300)
            if 500 <= resp.status_code < 600:
                resp.close()
                raise requests.HTTPError(f'HTTP {resp.status_code}', response=resp)
            resp.raise_for_status()
            break
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt == 2:
                raise
            delay = 2 ** attempt
            if on_token:
                on_token(f'\n[MLX 재연결 {attempt + 2}/3 — {delay}s 대기: {type(e).__name__}]\n')
            time.sleep(delay)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status < 500 or attempt == 2:
                raise
            delay = 2 ** attempt
            if on_token:
                on_token(f'\n[MLX 재연결 {attempt + 2}/3 — {delay}s 대기: HTTP {status}]\n')
            time.sleep(delay)

    parser = _ThinkingParser(
        on_answer=on_token,
        on_thought=on_thought,
        on_thought_end=on_thought_end,
    )
    tool_calls = []

    for raw in resp.iter_lines():
        if not raw:
            continue
        line = raw.decode('utf-8') if isinstance(raw, bytes) else raw
        # SSE 주석(:keepalive ...) 과 비-data 라인은 무시
        if not line.startswith('data: '):
            continue
        data = line[6:]
        if data.strip() == '[DONE]':
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        choices = chunk.get('choices') or []
        if not choices:
            continue
        delta = choices[0].get('delta', {})
        content = delta.get('content', '')
        if content:
            parser.feed(content)
        # Qwen3.6 reasoning 필드 → thought 콜백 (있을 때만)
        reasoning = delta.get('reasoning', '')
        if reasoning and on_thought:
            on_thought(reasoning)
        if delta.get('tool_calls'):
            for tc in delta['tool_calls']:
                fn = tc.get('function', {})
                tool_calls.append({
                    'function': {
                        'name': fn.get('name', ''),
                        # arguments 는 stringified JSON — agent loop 가 str/dict 둘 다 처리
                        'arguments': fn.get('arguments', '{}'),
                    }
                })
    parser.flush()

    result = {'role': 'assistant', 'content': parser.accumulated, 'tool_calls': tool_calls}
    if parser._thinkings:
        result['_thinking'] = parser._thinkings[-1]
    return result


def _parse_text_tool_calls(text: str) -> list:
    '''모델이 텍스트로 툴콜을 출력한 경우 파싱. JSON/XML 두 형식 모두 지원.

    CONCERNS.md §1.5 대응: 기존 regex는 `[^{}]`로 중첩 중괄호를 막아
    `arguments: {"filter": {"type": "eq"}}` 같은 구조화 입력을 놓쳤음.
    이제 `json.JSONDecoder.raw_decode`로 스캔해 중첩 객체도 파싱.
    '''
    calls = []
    decoder = json.JSONDecoder()
    i = 0
    n = len(text)
    while i < n:
        idx = text.find('{', i)
        if idx < 0:
            break
        try:
            obj, end = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            i = idx + 1
            continue
        i = idx + end
        if isinstance(obj, dict) and 'name' in obj and 'arguments' in obj:
            calls.append({'function': {'name': obj['name'], 'arguments': obj['arguments']}})

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
    parts = [_system_prompt(), f'\n현재 작업 디렉토리: {working_dir}']

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
    on_thought=None,
    on_thought_end=None,
    hooks: dict = None,
) -> tuple[str, list]:
    if session_messages is None:
        session_messages = []
    if profile is None:
        profile = {}

    # 파일 시스템 샌드박스 설정 (원격 사용자 working_dir 격리)
    # profile.fs_sandbox 가 True면 fs 툴이 working_dir 밖 접근 거부.
    # CONCERNS.md §1.7/§1.8 대응: full-auto 모드에선 confirm_write를 건너뛰므로
    # 명시적 opt-in이 없더라도 자동 샌드박스 걸어 작업 디렉토리 밖 쓰기를 차단.
    from tools import fs as _fs
    sandbox_on = profile.get('fs_sandbox') or config.APPROVAL_MODE == 'full-auto'
    _fs.set_sandbox(working_dir if sandbox_on else None)

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
    # CONCERNS §3.8: maxlen=10으로 unbounded 성장 차단. REPEAT_WINDOW=3 기준
    # 충분 — 과거 기록을 길게 들고 있어도 활용 안 됨.
    _tool_call_history: deque[tuple[str, str]] = deque(maxlen=10)
    # 사용자가 이번 turn 안에서 confirm을 한 번이라도 거부했으면 True.
    # 이후 모든 run_command/run_python은 safe 분류여도 confirm을 강제 (모델이
    # 우회 명령으로 같은 의도를 달성하는 것을 차단).
    denied_in_turn = False

    for iteration in range(config.MAX_ITERATIONS):
        if time.time() - _start > config.AGENT_TIMEOUT:
            run_hook((hooks or {}).get('on_stop', ''), 'on_stop', working_dir=working_dir)
            return f'에이전트 타임아웃 ({config.AGENT_TIMEOUT}초 초과)', session_messages
        msg = _stream_response(session_messages, on_token=on_token,
                               on_thought=on_thought, on_thought_end=on_thought_end)
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
                    denied_in_turn = True  # 거부 후 모델 우회 차단
                    result = {'ok': False, 'error': '사용자가 취소했습니다'}
                    if on_tool:
                        on_tool(fn_name, args, result)
                    session_messages.append({
                        'role': 'tool',
                        'content': json.dumps(result, ensure_ascii=False),
                    })
                    continue

            # Bash 명령 확인 — sticky deny 시 safe 명령도 confirm 강제
            if fn_name == 'run_command' and confirm_bash:
                cmd = args.get('command', '')
                if should_confirm(cmd, sticky_deny=denied_in_turn):
                    if not confirm_bash(cmd):
                        denied_in_turn = True
                        result = {'ok': False, 'error': '사용자가 취소했습니다'}
                        if on_tool:
                            on_tool(fn_name, args, result)
                        session_messages.append({
                            'role': 'tool',
                            'content': json.dumps(result, ensure_ascii=False),
                        })
                        continue

            # run_python: 임의 코드 실행이라 항상 confirm 요구 (샌드박스 대체)
            if fn_name == 'run_python' and confirm_bash:
                code = args.get('code', '')
                preview = 'python: ' + code[:200].replace('\n', ' ⏎ ')
                if not confirm_bash(preview):
                    denied_in_turn = True
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
        # deque는 슬라이싱 미지원이라 list 변환 (maxlen=10이라 비용 무시 가능).
        REPEAT_WINDOW = 3
        if len(_tool_call_history) >= REPEAT_WINDOW:
            recent = list(_tool_call_history)[-REPEAT_WINDOW:]
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

        # 반복 감지 #2: 동일 툴 5회 (인자 무관) — search_web/fetch_page 처럼 매번 다른
        # 쿼리로 도는 무한 루프 차단. 위 #1 은 같은 인자만 잡아서 빠짐.
        SAME_TOOL_LIMIT = 5
        if len(_tool_call_history) >= SAME_TOOL_LIMIT:
            recent_names = [tc[0] for tc in list(_tool_call_history)[-SAME_TOOL_LIMIT:]]
            if all(n == recent_names[0] for n in recent_names):
                session_messages.append({
                    'role': 'user',
                    'content': (
                        f'동일한 툴({recent_names[0]})을 {SAME_TOOL_LIMIT}회 연속 호출했습니다. '
                        '더 이상 같은 도구를 부르지 말고 지금까지의 결과만으로 답변을 마무리하세요. '
                        '결과가 충분치 않으면 그 점을 명시하고 사용자가 추가로 알려줄 정보를 요청하세요.'
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
