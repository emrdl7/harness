'''제안서를 받아 실제 코드 변경을 실행. 백업→구현→검증→적용/롤백.'''
import os
import sys
import json
import subprocess
from datetime import datetime

from tools.improve import backup_sources, validate_python, HARNESS_DIR, EDITABLE_FILES
from evolution.proposer import load_pending, mark_proposal

CHANGELOG_PATH = os.path.expanduser('~/.harness/evolution/changelog.jsonl')
MAX_CHANGES_PER_DAY = 3
DAILY_COUNT_PATH = os.path.expanduser('~/.harness/evolution/.daily_change_count')


# ── 공개 API ─────────────────────────────────────────────────────

def execute_pending(force: bool = False, console=None) -> list[dict]:
    '''pending 제안서 중 high/medium 우선순위 항목을 순서대로 실행.
    force=True 이면 하루 횟수 제한을 무시.'''
    proposals = load_pending('pending')
    if not proposals:
        return []

    # 우선순위 정렬: high → medium
    ordered = sorted(proposals, key=lambda p: (0 if p['priority'] == 'high' else 1))
    results = []

    for proposal in ordered:
        if not force and _daily_limit_reached():
            _log(console, f'  [dim]오늘 코드 변경 한도({MAX_CHANGES_PER_DAY}회) 도달 — 내일 재시도[/dim]')
            break
        result = _execute_one(proposal, console=console)
        results.append(result)
        if result['ok']:
            _increment_daily_count()

    return results


def execute_proposal(key: str, console=None) -> dict:
    '''특정 제안서 하나를 key로 강제 실행.'''
    for p in load_pending('pending'):
        if p.get('key') == key:
            return _execute_one(p, console=console)
    return {'ok': False, 'error': f'제안서 없음: {key}'}


# ── 실행 파이프라인 ───────────────────────────────────────────────

def _execute_one(proposal: dict, console=None) -> dict:
    key = proposal['key']
    _log(console, f'\n  [dim]── 자율 개선: {key}[/dim]')
    _log(console, f'  [dim]{proposal["rationale"]}[/dim]')

    # 1. 백업
    backup_ts = backup_sources()
    _log(console, f'  [dim]백업: {backup_ts}[/dim]')

    # 2. LLM으로 구현
    ok, changed_files, error = _run_implementation(proposal)

    if not ok:
        _rollback(backup_ts, console)
        mark_proposal(key, 'failed', note=error)
        _append_changelog(proposal, 'failed', error=error)
        return {'ok': False, 'key': key, 'error': error}

    # 3. 검증
    ok, error = _validate(changed_files)
    if not ok:
        _rollback(backup_ts, console)
        mark_proposal(key, 'failed', note=f'검증 실패: {error}')
        _append_changelog(proposal, 'failed', error=f'검증 실패: {error}')
        _log(console, f'  [tool.fail]✗ 검증 실패 — 롤백 완료[/tool.fail]')
        return {'ok': False, 'key': key, 'error': error}

    # 4. 성공
    mark_proposal(key, 'applied')
    _append_changelog(proposal, 'applied', changed_files=changed_files)
    _log(console, f'  [tool.ok]✓ 적용 완료[/tool.ok]')
    return {'ok': True, 'key': key, 'changed_files': changed_files}


def _run_implementation(proposal: dict) -> tuple[bool, list[str], str]:
    '''에이전트로 제안서를 구현. (changed_files, error) 반환.'''
    import agent as ag

    # EDITABLE_FILES 목록 + proposal의 affected_files 교집합만 허용
    allowed = set(EDITABLE_FILES)
    target_files = [f for f in proposal.get('affected_files', []) if f in allowed]
    if not target_files:
        # affected_files가 제한 목록 밖이면 EDITABLE_FILES 전체를 컨텍스트로 제공
        target_files = list(allowed)

    # 대상 파일 소스 읽기
    sources_parts = []
    for rel in target_files:
        path = os.path.join(HARNESS_DIR, rel)
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                sources_parts.append(f'=== {rel} ===\n{f.read()}')
    sources = '\n\n'.join(sources_parts)

    prompt = f'''자율 코드 개선 작업입니다. 아래 제안을 구현하세요.

## 제안 정보
- 타입: {proposal["type"]}
- 근거: {proposal["rationale"]}
- 변경 내용: {proposal["proposed_change"]}
- 수정 가능 파일: {", ".join(target_files)}

## 현재 소스 코드
{sources[:10000]}

## 구현 규칙
1. 수정 가능 파일({", ".join(target_files)}) 외에는 절대 건드리지 말 것
2. 기존 코드 스타일 유지
3. 최소한의 변경만 가할 것
4. 구현 후 반드시 run_command("python3 -m py_compile <파일>")로 검증
5. 구현이 불가능하거나 안전하지 않으면 "구현 불가: <이유>" 를 출력하고 파일 수정 없이 종료

HARNESS_DIR: {HARNESS_DIR}
'''

    changed: list[str] = []
    error_msg = ''

    def _on_tool(name, args, result):
        if name in ('write_file', 'edit_file') and result and result.get('ok'):
            path = args.get('path', '')
            rel = os.path.relpath(path, HARNESS_DIR)
            if rel not in changed:
                changed.append(rel)

    impl_session = [{'role': 'system', 'content': (
        '당신은 harness 자율 개선 에이전트입니다. '
        '지정된 파일만 수정하고, 검증 후 결과를 간결하게 보고하세요.'
        f'\nHARNESS_DIR: {HARNESS_DIR}'
    )}]

    try:
        text, _ = ag.run(
            prompt,
            session_messages=impl_session,
            working_dir=HARNESS_DIR,
            profile={},
            on_token=lambda t: None,
            on_tool=_on_tool,
            confirm_write=lambda p: True,
        )
        if '구현 불가' in (text or ''):
            return False, [], text
    except Exception as e:
        return False, [], str(e)

    return True, changed, ''


def _validate(changed_files: list[str]) -> tuple[bool, str]:
    '''변경된 파일에 대해 3단계 검증 실행.'''
    # 1단계: py_compile
    for rel in changed_files:
        path = os.path.join(HARNESS_DIR, rel)
        if not path.endswith('.py') or not os.path.exists(path):
            continue
        result = validate_python(path)
        if not result['ok']:
            return False, f'문법 오류 ({rel}): {result["error"]}'

    # 2단계: import test
    try:
        result = subprocess.run(
            [sys.executable, '-c', 'import agent, tools, config, profile'],
            cwd=HARNESS_DIR,
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return False, f'import 실패: {result.stderr.strip()[:200]}'
    except subprocess.TimeoutExpired:
        return False, 'import 테스트 타임아웃'
    except Exception as e:
        return False, f'import 테스트 오류: {e}'

    # 3단계: 변경된 TOOL_DEFINITIONS가 있으면 툴 목록 로드 확인
    if any('tools' in f for f in changed_files):
        try:
            result = subprocess.run(
                [sys.executable, '-c',
                 'from tools import TOOL_DEFINITIONS, TOOL_MAP; '
                 'assert len(TOOL_DEFINITIONS) >= 17, "툴 정의 개수 이상"'],
                cwd=HARNESS_DIR,
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return False, f'툴 검증 실패: {result.stderr.strip()[:200]}'
        except Exception as e:
            return False, f'툴 검증 오류: {e}'

    return True, ''


def _rollback(backup_ts: str, console=None):
    from tools.improve import restore_backup
    restore_backup(backup_ts)
    _log(console, f'  [dim]롤백 완료 ({backup_ts})[/dim]')


# ── changelog ────────────────────────────────────────────────────

def _append_changelog(proposal: dict, status: str, error: str = '', changed_files: list = None):
    os.makedirs(os.path.dirname(CHANGELOG_PATH), exist_ok=True)
    entry = {
        'ts': datetime.now().isoformat(),
        'key': proposal['key'],
        'type': proposal['type'],
        'rationale': proposal['rationale'],
        'status': status,
        'changed_files': changed_files or [],
    }
    if error:
        entry['error'] = error
    with open(CHANGELOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def load_changelog(n: int = 20) -> list[dict]:
    if not os.path.exists(CHANGELOG_PATH):
        return []
    lines = []
    with open(CHANGELOG_PATH, encoding='utf-8') as f:
        for line in f:
            try:
                lines.append(json.loads(line))
            except Exception:
                pass
    return lines[-n:]


# ── 하루 횟수 제한 ────────────────────────────────────────────────

def _daily_limit_reached() -> bool:
    today = datetime.now().strftime('%Y-%m-%d')
    if not os.path.exists(DAILY_COUNT_PATH):
        return False
    try:
        with open(DAILY_COUNT_PATH) as f:
            data = json.load(f)
        return data.get('date') == today and data.get('count', 0) >= MAX_CHANGES_PER_DAY
    except Exception:
        return False


def _increment_daily_count():
    today = datetime.now().strftime('%Y-%m-%d')
    data = {'date': today, 'count': 1}
    if os.path.exists(DAILY_COUNT_PATH):
        try:
            with open(DAILY_COUNT_PATH) as f:
                existing = json.load(f)
            if existing.get('date') == today:
                data['count'] = existing.get('count', 0) + 1
        except Exception:
            pass
    os.makedirs(os.path.dirname(DAILY_COUNT_PATH), exist_ok=True)
    with open(DAILY_COUNT_PATH, 'w') as f:
        json.dump(data, f)


def _log(console, msg: str):
    if console is not None:
        console.print(msg)
