'''슬래시 핸들러 입출력 타입.'''
from dataclasses import dataclass, field, replace


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
