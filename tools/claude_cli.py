import subprocess
import shutil
import os


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


def ask(query: str, on_token=None, cwd: str | None = None) -> str:
    '''claude CLI를 --print 모드로 호출. 스트리밍 출력 지원.
    cwd를 지정하면 해당 디렉토리 컨텍스트로 실행됨 (기본: 현재 프로세스 cwd).'''
    claude_bin = _find_claude()
    if not claude_bin:
        raise FileNotFoundError(
            'claude CLI를 찾을 수 없습니다. '
            'https://claude.ai/code 에서 설치 후 PATH를 확인하세요.'
        )

    cmd = [claude_bin, '--print', query]

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
        raise RuntimeError(f'claude CLI 오류 (코드 {proc.returncode}): {err.strip()}')

    return ''.join(output_parts)


def is_available() -> bool:
    return _find_claude() is not None
