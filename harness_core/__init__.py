'''harness_core — main.py와 harness_server.py가 공유하는 슬래시 핸들러.

설계 원칙:
- 핸들러는 순수 함수 (콘솔/네트워크 의존 없음)
- 입력: SlashState + 추가 인자
- 출력: SlashResult (새 state + UI에 보여줄 notice)

프런트엔드(main.py / harness_server.py)는 결과를 자기 방식대로 렌더링.
1차 추출 대상은 의존성이 가장 적은 핸들러. agent 실행이 필요한 것들은
다음 세션에서 callback 인젝션으로 추가.
'''
from .types import SlashState, SlashResult, SlashContext
from .router import dispatch, KNOWN_COMMANDS

__all__ = ['SlashState', 'SlashResult', 'SlashContext', 'dispatch', 'KNOWN_COMMANDS']
