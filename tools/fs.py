import os
import re
import glob as _glob

def read_file(path: str = None, file_path: str = None, offset: int = 1, limit: int = 0) -> dict:
    path = path or file_path
    '''offset: 시작 줄(1-based), limit: 읽을 줄 수(0=전체)'''
    try:
        with open(os.path.expanduser(path), 'r', encoding='utf-8') as f:
            lines = f.readlines()
        total = len(lines)
        start = max(1, offset) - 1          # 0-based index
        end   = (start + limit) if limit > 0 else total
        end   = min(end, total)
        sliced = lines[start:end]
        # 줄 번호 prefix (cat -n 스타일)
        content = ''.join(f'{start + i + 1:4d}\t{l}' for i, l in enumerate(sliced))
        return {
            'ok': True,
            'content': content,
            'total_lines': total,
            'start_line': start + 1,
            'end_line': start + len(sliced),
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def write_file(path: str, content: str) -> dict:
    try:
        path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> dict:
    try:
        path = os.path.expanduser(path)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        count = content.count(old_string)
        if count == 0:
            return {'ok': False, 'error': f'old_string을 찾을 수 없음: {repr(old_string[:80])}'}
        if count > 1 and not replace_all:
            return {'ok': False, 'error': f'old_string이 {count}곳에서 발견됨 — replace_all=true로 전체 교체하거나 더 구체적으로 지정하세요'}
        new_content = content.replace(old_string, new_string) if replace_all else content.replace(old_string, new_string, 1)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return {'ok': True, 'replaced': count if replace_all else 1}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def grep_search(
    pattern: str,
    path: str = '.',
    include: str = '',
    case_insensitive: bool = False,
    context_lines: int = 0,
) -> dict:
    try:
        flags = re.IGNORECASE if case_insensitive else 0
        regex = re.compile(pattern, flags)
        search_path = os.path.expanduser(path)
        results = []

        def _search_file(fp):
            try:
                with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
            except Exception:
                return
            matches = [i for i, l in enumerate(lines) if regex.search(l)]
            if not matches:
                return
            collected = set()
            for i in matches:
                for j in range(max(0, i - context_lines), min(len(lines), i + context_lines + 1)):
                    collected.add(j)
            snippets = []
            prev = -2
            for j in sorted(collected):
                if j > prev + 1 and snippets:
                    snippets.append('---')
                prefix = '>' if j in matches else ' '
                snippets.append(f'{prefix} {j+1:4d}: {lines[j].rstrip()}')
                prev = j
            results.append({'file': fp, 'lines': snippets})

        if os.path.isfile(search_path):
            _search_file(search_path)
        else:
            include_pat = re.compile(include) if include else None
            for root, dirs, files in os.walk(search_path):
                dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', '.venv'}]
                for fname in files:
                    fp = os.path.join(root, fname)
                    if include_pat and not include_pat.search(fp):
                        continue
                    _search_file(fp)

        total = sum(sum(1 for l in r['lines'] if l.startswith('>')) for r in results)
        return {'ok': True, 'results': results, 'total_matches': total}
    except re.error as e:
        return {'ok': False, 'error': f'잘못된 정규식: {e}'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def list_files(pattern: str = None, path: str = None) -> dict:
    # path 인자 호환 — 디렉토리 경로를 받으면 glob으로 변환
    if path and not pattern:
        pattern = os.path.join(os.path.expanduser(path), '*')
    if not pattern:
        return {'ok': False, 'error': 'pattern 또는 path 인자가 필요합니다'}
    try:
        matches = _glob.glob(os.path.expanduser(pattern), recursive=True)
        return {'ok': True, 'files': sorted(matches)}
    except Exception as e:
        return {'ok': False, 'error': str(e)}
