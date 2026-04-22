import subprocess
import shutil
import os
import json
from datetime import datetime

_CLAUDE_LOG_PATH = os.path.expanduser('~/.harness/logs/claude.jsonl')


def _find_claude() -> str | None:
    # 직접 경로 우선, 없으면 PATH 탐색
    candidates = [
        os.path.expanduser('~/.claude/local/claude'),
        '/usr/local/bin/claude',
        '/opt/homebrew/bin/claude',
    ]
    for p in candidates:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return shutil.which('claude')


def ask(query: str, on_token=None, cwd: str | None = None, model: str | None = None) -> str:
    '''claude CLI를 --print 모드로 호출. 스트리밍 출력 지원.
    cwd를 지정하면 해당 디렉토리 컨텍스트로 실행됨 (기본: 현재 프로세스 cwd).
    model을 지정하면 --model 플래그로 전달됨 (예: "sonnet", "opus").'''
    claude_bin = _find_claude()
    if not claude_bin:
        raise FileNotFoundError(
            'claude CLI를 찾을 수 없습니다. '
            'https://claude.ai/code 에서 설치 후 PATH를 확인하세요.'
        )

    cmd = [claude_bin, '--print', query]
    if model:
        cmd += ['--model', model]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=cwd,
    )

    output_parts = []
    try:
        for line in proc.stdout:
            output_parts.append(line)
            if on_token:
                on_token(line)
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        raise

    if proc.returncode != 0:
        err = proc.stderr.read() if proc.stderr else ''
        _log_call(query, '', err=err, cwd=cwd, model=model, returncode=proc.returncode)
        raise RuntimeError(f'claude CLI 오류 (코드 {proc.returncode}): {err.strip()}')

    response = ''.join(output_parts)
    _log_call(query, response, cwd=cwd, model=model)
    return response


def _log_call(query: str, response: str, *, err: str = '', cwd: str | None = None,
              model: str | None = None, returncode: int = 0) -> None:
    '''CONCERNS.md §2.6 대응: Claude 위임 호출은 harness의 confirm/hook 게이트
    밖에서 실행되므로 감사 추적용으로 prompt/response를 영구 기록.
    ~/.harness/logs/claude.jsonl 에 JSONL append.'''
    try:
        os.makedirs(os.path.dirname(_CLAUDE_LOG_PATH), exist_ok=True)
        entry = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'cwd': cwd or os.getcwd(),
            'model': model or '',
            'returncode': returncode,
            'query': query,
            'response': response,
            'error': err,
        }
        with open(_CLAUDE_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        try:
            os.chmod(_CLAUDE_LOG_PATH, 0o600)
        except OSError:
            pass
    except OSError:
        # 로깅 실패해도 agent 작업은 계속
        pass


def is_available() -> bool:
    return _find_claude() is not None
