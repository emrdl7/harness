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
    return _git(['log', f'-{n}', '--oneline', '--graph'], cwd)


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
