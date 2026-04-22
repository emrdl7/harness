'''PC 유휴 상태 감지 후 백그라운드 진화 실행 (macOS)'''
import os
import subprocess
import time
import json
import sys
from datetime import datetime

IDLE_THRESHOLD_SEC = 300       # 5분 이상 유휴면 실행
CHECK_INTERVAL_SEC = 60        # 1분마다 체크
LOCK_PATH = os.path.expanduser('~/.harness/evolution/.idle_lock')
LAST_RUN_PATH = os.path.expanduser('~/.harness/evolution/.last_idle_run')
MIN_INTERVAL_SEC = 3600        # 1시간에 한 번 이상은 실행 안 함

HARNESS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_idle_seconds() -> float:
    '''macOS IOHIDSystem으로 사용자 입력 없는 시간(초) 반환'''
    try:
        out = subprocess.check_output(
            ['ioreg', '-c', 'IOHIDSystem'],
            text=True, timeout=5
        )
        for line in out.splitlines():
            if 'HIDIdleTime' in line:
                ns = int(line.split('=')[-1].strip())
                return ns / 1_000_000_000
    except Exception:
        pass
    return 0.0


def _should_run() -> bool:
    if os.path.exists(LOCK_PATH):
        return False
    if os.path.exists(LAST_RUN_PATH):
        try:
            with open(LAST_RUN_PATH) as f:
                last = float(f.read().strip())
            if time.time() - last < MIN_INTERVAL_SEC:
                return False
        except Exception:
            pass
    return True


def _mark_running():
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    with open(LOCK_PATH, 'w') as f:
        f.write(str(os.getpid()))


def _mark_done():
    if os.path.exists(LOCK_PATH):
        os.unlink(LOCK_PATH)
    with open(LAST_RUN_PATH, 'w') as f:
        f.write(str(time.time()))


def _run_idle_evolution():
    '''유휴 시 실행할 진화 작업'''
    from evolution.tracker import get_recurring, dismiss_all
    from evolution.history import avg_score, recent
    from tools.improve import backup_sources, read_sources, validate_python, EDITABLE_FILES
    from session.logger import read_recent
    import agent as ag

    log_lines = []

    def silent_on_tool(name, args, result):
        if result is not None and not result.get('ok'):
            log_lines.append(f'[{name}] 실패: {result.get("error", "")}')

    # 1. 반복 패턴 체크
    recurring = get_recurring(threshold=2)
    if recurring:
        backup_sources()
        sources = read_sources()
        patterns_str = '\n'.join(f'- {r["pattern"]} ({r["count"]}회)' for r in recurring[:3])
        logs = read_recent(days=3)

        prompt = f'''유휴 시간 자동 개선 작업입니다.

반복 실패 패턴:
{patterns_str}

최근 실패 로그:
{logs[:3000]}

소스 코드:
{sources[:8000]}

위 패턴의 근본 원인을 찾아 조용히 수정하세요.
수정 후 py_compile로 검증하세요.
'''
        improve_session = [{
            'role': 'system',
            'content': f'당신은 하네스 자동 유지보수 에이전트입니다. {HARNESS_DIR} 에서 작업하세요. 출력 최소화.'
        }]
        ag.run(
            prompt,
            session_messages=improve_session,
            working_dir=HARNESS_DIR,
            profile={},
            on_token=lambda t: None,
            on_tool=silent_on_tool,
            confirm_write=lambda p: True,  # 유휴 시에는 자동 확인
        )
        dismiss_all()

        # 검증
        all_ok = all(
            validate_python(os.path.join(HARNESS_DIR, f)).get('ok')
            for f in EDITABLE_FILES
            if f.endswith('.py') and os.path.exists(os.path.join(HARNESS_DIR, f))
        )
        log_lines.append(f'소스 개선 {"완료" if all_ok else "실패 (검증 오류)"}')

    # 결과 로그
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    log_entry = {'ts': timestamp, 'event': 'idle_evolution', 'results': log_lines}
    log_path = os.path.expanduser('~/.harness/evolution/idle.log')
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')


def watch_loop():
    '''포어그라운드에서 유휴 감지 루프 실행'''
    print(f'[idle_runner] 시작 (유휴 임계값: {IDLE_THRESHOLD_SEC}초)', flush=True)
    while True:
        try:
            idle = get_idle_seconds()
            if idle >= IDLE_THRESHOLD_SEC and _should_run():
                print(f'[idle_runner] 유휴 {idle:.0f}초 — 진화 실행', flush=True)
                _mark_running()
                try:
                    _run_idle_evolution()
                finally:
                    _mark_done()
                print('[idle_runner] 완료', flush=True)
        except Exception as e:
            print(f'[idle_runner] 오류: {e}', flush=True)
        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == '__main__':
    watch_loop()
