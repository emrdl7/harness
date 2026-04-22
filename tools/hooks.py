import json
import os
import subprocess

TIMEOUT = 10  # 훅 최대 실행 시간(초)


def run_hook(
    command: str,
    event: str,
    tool: str = '',
    args: dict = None,
    result_ok: bool = None,
    working_dir: str = '.',
) -> bool:
    '''훅 명령어 실행.
    pre_tool_use 이벤트에서 비-0 종료 코드를 반환하면 False → 툴 실행 차단.
    나머지 이벤트는 반환값 무시.'''
    if not command or not command.strip():
        return True

    env = {
        **os.environ,
        'HARNESS_EVENT':       event,
        'HARNESS_TOOL':        tool,
        'HARNESS_ARGS':        json.dumps(args or {}, ensure_ascii=False),
        'HARNESS_WORKING_DIR': os.path.abspath(working_dir),
    }
    if result_ok is not None:
        env['HARNESS_RESULT_OK'] = 'true' if result_ok else 'false'

    try:
        proc = subprocess.run(
            command,
            shell=True,
            env=env,
            timeout=TIMEOUT,
        )
        return proc.returncode == 0
    except subprocess.TimeoutExpired:
        return True   # 타임아웃은 무시
    except Exception:
        return True   # 훅 오류가 에이전트를 막으면 안 됨
