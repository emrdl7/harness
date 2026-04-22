'''슬래시 핸들러 입출력 타입.'''
from dataclasses import dataclass, field, replace
from typing import Callable, Optional


@dataclass
class SlashContext:
    '''핸들러가 사용할 콜백 / 외부 함수.

    프런트엔드(main / server)가 자기 환경에 맞게 콜백을 채워서 dispatch에 전달.
    기존 순수 핸들러(/clear, /undo 등)는 ctx를 받지만 무시한다.

    Fields:
      run_agent: 메인 세션용 agent 실행 콜백.
        시그니처: (user_input: str, *, plan_mode: bool = False, context_snippets: str = '') -> None
        main의 _run_agent / server의 run_agent를 어댑트해서 주입.

      run_agent_ephemeral: 별도 임시 세션 실행용. /improve, /learn에서 사용.
        시그니처: (user_input: str, *, system_prompt: str, working_dir: str, profile: dict) -> None
        에이전트는 별도 세션으로 실행되고 그 결과는 main 세션(state.messages)에 반영되지 않는다.
    '''
    run_agent: Optional[Callable] = None
    run_agent_ephemeral: Optional[Callable] = None
    # /cplan 전용 콜백
    ask_claude: Optional[Callable] = None          # (prompt: str) -> str (plan_text)
    confirm_execute: Optional[Callable] = None     # (plan_text, task) -> bool


@dataclass
class SlashState:
    '''슬래시 핸들러 호출 시점의 세션 상태.

    프런트엔드(main.py / server.py)가 자기 상태를 이 형태로 묶어서 전달하고,
    핸들러는 새 SlashState를 result.state로 돌려준다.
    '''
    messages: list = field(default_factory=list)
    working_dir: str = '.'
    profile: dict = field(default_factory=dict)
    undo_count: int = 0


@dataclass
class SlashResult:
    '''슬래시 핸들러 결과.

    state: 새 (또는 동일) SlashState. 프런트엔드는 이걸 자기 상태에 반영.
    notice: 사용자에게 보여줄 한 줄 메시지 (없으면 빈 문자열).
    level:  notice의 의미 등급 — 'info' | 'ok' | 'warn' | 'error'.
            프런트엔드가 색상/아이콘을 결정하는 데 쓴다.
    handled: 핸들러가 명령을 인식했는지 여부.
             False면 라우터가 "알 수 없는 명령"으로 처리.
    data: 구조화된 결과 페이로드 (filename, sessions[], tree 등).
          notice로 표현하기 어려운 데이터를 프런트엔드가 자유롭게 렌더링.
    '''
    state: SlashState
    notice: str = ''
    level: str = 'info'
    handled: bool = True
    data: dict = field(default_factory=dict)

    @classmethod
    def info(cls, state: SlashState, notice: str = '', **data) -> 'SlashResult':
        return cls(state=state, notice=notice, level='info', data=data)

    @classmethod
    def ok(cls, state: SlashState, notice: str = '', **data) -> 'SlashResult':
        return cls(state=state, notice=notice, level='ok', data=data)

    @classmethod
    def warn(cls, state: SlashState, notice: str = '', **data) -> 'SlashResult':
        return cls(state=state, notice=notice, level='warn', data=data)

    @classmethod
    def error(cls, state: SlashState, notice: str = '', **data) -> 'SlashResult':
        return cls(state=state, notice=notice, level='error', data=data)

    @classmethod
    def unknown(cls, state: SlashState, notice: str = '') -> 'SlashResult':
        return cls(state=state, notice=notice, level='warn', handled=False)


def evolve(state: SlashState, **changes) -> SlashState:
    '''SlashState 부분 갱신 헬퍼. dataclasses.replace의 짧은 alias.'''
    return replace(state, **changes)
