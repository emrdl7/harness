import subprocess


def _git(args: list, cwd: str = '.') -> dict:
    try:
        result = subprocess.run(
            ['git'] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=15,
        )
        return {
            'ok': result.returncode == 0,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
        }
    except Exception as e:
        return {'ok': False, 'stdout': '', 'stderr': str(e)}


def git_status(cwd: str = '.') -> dict:
    return _git(['status', '--short'], cwd)


def git_diff(cwd: str = '.', staged: bool = False) -> dict:
    args = ['diff', '--stat', 'HEAD'] if not staged else ['diff', '--cached']
    r = _git(args, cwd)
    if r['ok'] and not r['stdout']:
        r['stdout'] = '변경사항 없음'
    return r


def git_log(cwd: str = '.', n: int = 10) -> dict:
    '''커밋 N개를 구조화된 dict 로 반환 (T5 GitLogBlock 시각화용).
    실패 시 _git 의 기본 {ok, stdout, stderr} 형식 그대로 반환.
    성공 시 stdout(원본 oneline) + commits([{hash, short, author, date, subject}]) 둘 다 포함 — 모델은 stdout, UI 는 commits 사용.
    '''
    # \x09 = 탭. subject 안 탭은 거의 없음 (git 이 자동 escape).
    fmt = '%H%x09%h%x09%an%x09%ar%x09%s'
    r = _git(['log', f'-{n}', '--pretty=format:' + fmt], cwd)
    if not r['ok']:
        return r
    commits = []
    for line in r['stdout'].splitlines():
        parts = line.split('\t')
        if len(parts) < 5:
            continue
        commits.append({
            'hash': parts[0],
            'short': parts[1],
            'author': parts[2],
            'date': parts[3],
            'subject': parts[4],
        })
    # stdout 도 oneline 형식으로 재생성 (모델 호환 — 기존 사용자가 stdout 만 보던 케이스)
    oneline = '\n'.join(f'{c["short"]} {c["subject"]}' for c in commits)
    return {'ok': True, 'commits': commits, 'stdout': oneline, 'stderr': ''}


def git_diff_full(cwd: str = '.') -> dict:
    r = _git(['diff', 'HEAD'], cwd)
    if r['ok'] and not r['stdout']:
        r['stdout'] = '변경사항 없음'
    return r


def git_add(paths: str | list = '.', cwd: str = '.') -> dict:
    if isinstance(paths, str):
        paths = [paths]
    return _git(['add', '--'] + paths, cwd)


def git_commit(message: str, cwd: str = '.') -> dict:
    return _git(['commit', '-m', message], cwd)


def git_stash(action: str = 'push', message: str = '', cwd: str = '.') -> dict:
    if action == 'push':
        args = ['stash', 'push'] + (['-m', message] if message else [])
    elif action == 'pop':
        args = ['stash', 'pop']
    elif action == 'list':
        args = ['stash', 'list']
    elif action == 'drop':
        args = ['stash', 'drop']
    else:
        return {'ok': False, 'error': f'알 수 없는 action: {action} (push/pop/list/drop)'}
    return _git(args, cwd)


def git_checkout(branch: str, create: bool = False, cwd: str = '.') -> dict:
    args = ['checkout', '-b', branch] if create else ['checkout', branch]
    return _git(args, cwd)
