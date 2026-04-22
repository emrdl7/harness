'''사용 패턴 분석 → 코드 개선 제안서 생성. LLM 없이 규칙 기반으로 실행.'''
import os
import json
from datetime import datetime, date
from collections import Counter, defaultdict

PROPOSALS_PATH = os.path.expanduser('~/.harness/evolution/proposals.jsonl')
UNKNOWN_TOOLS_PATH = os.path.expanduser('~/.harness/evolution/unknown_tools.json')
TOOL_STATS_PATH = os.path.expanduser('~/.harness/evolution/tool_stats.json')
SEQUENCE_PATH = os.path.expanduser('~/.harness/evolution/sequences.json')


# ── 신호 수집 ─────────────────────────────────────────────────────

def record_unknown_tool(name: str, session_id: str):
    '''미등록 툴 호출을 누적 기록.'''
    data = _load_json(UNKNOWN_TOOLS_PATH, {})
    if name not in data:
        data[name] = {'count': 0, 'sessions': [], 'first_seen': _today()}
    entry = data[name]
    if session_id not in entry['sessions']:
        entry['sessions'].append(session_id)
        entry['count'] += 1
    entry['last_seen'] = _today()
    _save_json(UNKNOWN_TOOLS_PATH, data)


def record_tool_call(tool_name: str, success: bool):
    '''툴 호출 결과를 통계에 누적.'''
    data = _load_json(TOOL_STATS_PATH, {})
    if tool_name not in data:
        data[tool_name] = {'calls': 0, 'failures': 0}
    data[tool_name]['calls'] += 1
    if not success:
        data[tool_name]['failures'] += 1
    _save_json(TOOL_STATS_PATH, data)


def record_tool_sequence(sequence: list[str], session_id: str):
    '''툴 호출 시퀀스를 기록. 길이 2~4짜리 패턴만 추출.'''
    if len(sequence) < 2:
        return
    data = _load_json(SEQUENCE_PATH, {})
    for size in (2, 3, 4):
        for i in range(len(sequence) - size + 1):
            pattern = '→'.join(sequence[i:i + size])
            if pattern not in data:
                data[pattern] = {'count': 0, 'sessions': []}
            if session_id not in data[pattern]['sessions']:
                data[pattern]['sessions'].append(session_id)
                data[pattern]['count'] += 1
    _save_json(SEQUENCE_PATH, data)


# ── 제안서 생성 ───────────────────────────────────────────────────

def analyze(
    unknown_tools: list[str] = None,
    user_corrections: int = 0,
    session_id: str = '',
) -> list[dict]:
    '''수집된 신호를 분석해 개선 제안서 목록 반환.'''
    proposals = []

    proposals.extend(_analyze_unknown_tools(unknown_tools or []))
    proposals.extend(_analyze_tool_stats())
    proposals.extend(_analyze_sequences())

    # 중복 제거 (같은 key)
    existing = {p['key'] for p in load_pending()}
    proposals = [p for p in proposals if p['key'] not in existing]

    for p in proposals:
        p['session_id'] = session_id
        _append_proposal(p)

    return proposals


def _analyze_unknown_tools(session_unknowns: list[str]) -> list[dict]:
    '''현재 세션의 미등록 툴 + 누적 데이터 분석.'''
    proposals = []
    data = _load_json(UNKNOWN_TOOLS_PATH, {})

    # 현재 세션의 미등록 툴도 카운트에 반영
    for name in session_unknowns:
        if name not in data:
            data[name] = {'count': 1, 'sessions': [], 'first_seen': _today(), 'last_seen': _today()}
        else:
            data[name]['count'] = data[name].get('count', 0) + 1

    for name, info in data.items():
        count = info.get('count', 0)
        if count < 2:
            continue
        priority = 'high' if count >= 4 else 'medium'
        proposals.append({
            'key': f'new_tool__{name}',
            'type': 'new_tool',
            'priority': priority,
            'rationale': f'{count}개 세션에서 존재하지 않는 툴 "{name}" 호출',
            'proposed_change': (
                f'tools/ 에 {name}() 함수 추가 및 TOOL_DEFINITIONS 등록. '
                f'함수명과 사용 맥락을 보고 적절한 구현 판단.'
            ),
            'affected_files': ['tools/__init__.py'],
            'evidence': info.get('sessions', [])[-5:],
            'created_at': _today(),
        })
    return proposals


def _analyze_tool_stats() -> list[dict]:
    '''실패율이 높은 툴 → description/에러처리 개선 제안.'''
    proposals = []
    data = _load_json(TOOL_STATS_PATH, {})
    for tool_name, stats in data.items():
        calls = stats.get('calls', 0)
        failures = stats.get('failures', 0)
        if calls < 5:
            continue
        rate = failures / calls
        if rate < 0.25:
            continue
        priority = 'high' if rate >= 0.5 else 'medium'
        proposals.append({
            'key': f'improve_tool__{tool_name}',
            'type': 'improve_tool',
            'priority': priority,
            'rationale': f'{tool_name} 실패율 {rate:.0%} ({failures}/{calls}회)',
            'proposed_change': (
                f'{tool_name}의 에러 처리 강화 또는 TOOL_DEFINITIONS description 개선. '
                f'실패 원인을 분석해 파라미터 검증 추가 또는 설명 보완.'
            ),
            'affected_files': ['tools/__init__.py'],
            'evidence': [],
            'created_at': _today(),
        })
    return proposals


def _analyze_sequences() -> list[dict]:
    '''반복 툴 시퀀스 → 복합 툴 또는 슬래시 명령 제안.'''
    proposals = []
    data = _load_json(SEQUENCE_PATH, {})

    # 복합 툴로 가치 있는 시퀀스
    valuable = {
        'git_add→git_commit': (
            'new_slash_cmd', '/commit',
            'git_add + git_commit 두 단계를 하나로',
            'main.py에 /commit <message> 슬래시 명령 추가',
        ),
        'read_file→edit_file': (
            'optimize_flow', 'read_then_edit',
            'read_file 후 edit_file 패턴은 이미 권장 흐름이므로 HARNESS.md에 명시',
            'HARNESS.md "자주 쓰는 패턴" 섹션에 read→edit 패턴 추가',
        ),
        'git_status→git_add→git_commit': (
            'new_slash_cmd', '/save',
            'git_status→add→commit 3-step을 하나의 /save 명령으로',
            'main.py에 /save <message> 슬래시 명령 추가',
        ),
    }

    for pattern, info in data.items():
        if info.get('count', 0) < 3:
            continue
        if pattern in valuable:
            ptype, key_suffix, rationale, change = valuable[pattern]
            proposals.append({
                'key': f'{ptype}__{key_suffix}',
                'type': ptype,
                'priority': 'medium',
                'rationale': f'"{pattern}" 패턴이 {info["count"]}회 반복 — {rationale}',
                'proposed_change': change,
                'affected_files': ['main.py'],
                'evidence': info.get('sessions', [])[-3:],
                'created_at': _today(),
            })

    return proposals


# ── 제안서 관리 ───────────────────────────────────────────────────

def load_pending(status: str = 'pending') -> list[dict]:
    if not os.path.exists(PROPOSALS_PATH):
        return []
    result = []
    with open(PROPOSALS_PATH, encoding='utf-8') as f:
        for line in f:
            try:
                p = json.loads(line)
                if p.get('status', 'pending') == status:
                    result.append(p)
            except Exception:
                pass
    return result


def load_all() -> list[dict]:
    if not os.path.exists(PROPOSALS_PATH):
        return []
    result = []
    with open(PROPOSALS_PATH, encoding='utf-8') as f:
        for line in f:
            try:
                result.append(json.loads(line))
            except Exception:
                pass
    return result


def mark_proposal(key: str, status: str, note: str = ''):
    '''제안서 상태 변경 (applied / rejected / failed).'''
    all_proposals = load_all()
    os.makedirs(os.path.dirname(PROPOSALS_PATH), exist_ok=True)
    with open(PROPOSALS_PATH, 'w', encoding='utf-8') as f:
        for p in all_proposals:
            if p.get('key') == key:
                p['status'] = status
                p['updated_at'] = datetime.now().isoformat()
                if note:
                    p['note'] = note
            f.write(json.dumps(p, ensure_ascii=False) + '\n')


def _append_proposal(p: dict):
    os.makedirs(os.path.dirname(PROPOSALS_PATH), exist_ok=True)
    p.setdefault('status', 'pending')
    with open(PROPOSALS_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(p, ensure_ascii=False) + '\n')


# ── 유틸 ─────────────────────────────────────────────────────────

def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _today() -> str:
    return date.today().isoformat()
