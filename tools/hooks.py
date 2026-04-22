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
    나머지 이벤트는 반환값 무시.

    CONCERNS.md §2.5 대응: 민감할 수 있는 args를 env로 전달하면 훅이 spawn한
    모든 자식 프로세스에 상속되며 프로세스 리스트/디버거로 노출될 위험이 있다.
    이제 args는 stdin으로 전달(JSON 한 줄). env에는 마커만 남겨 훅 스크립트가
    stdin을 읽어야 함을 알린다. (훅 작성 예: `args=$(cat); echo "$args" | jq .`)
    '''
    if not command or not command.strip():
        return True

    args_json = json.dumps(args or {}, ensure_ascii=False)

    env = {
        **os.environ,
        'HARNESS_EVENT':       event,
        'HARNESS_TOOL':        tool,
        'HARNESS_ARGS_STDIN':  '1',   # stdin에 JSON이 들어있음을 알림
        'HARNESS_WORKING_DIR': os.path.abspath(working_dir),
    }
    if result_ok is not None:
        env['HARNESS_RESULT_OK'] = 'true' if result_ok else 'false'

    try:
        proc = subprocess.run(
            command,
            shell=True,
            env=env,
            input=args_json,
            text=True,
            timeout=TIMEOUT,
        )
        return proc.returncode == 0
    except subprocess.TimeoutExpired:
        return True   # 타임아웃은 무시
    except Exception:
        return True   # 훅 오류가 에이전트를 막으면 안 됨
