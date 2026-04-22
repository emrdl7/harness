import os
import re

SKILLS_DIR = os.path.dirname(os.path.abspath(__file__))
_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
_MAX_SKILL_CHARS = 3000


def _parse(path: str) -> dict | None:
    try:
        with open(path, encoding='utf-8') as f:
            text = f.read()
    except Exception:
        return None

    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None

    meta = {}
    for line in m.group(1).splitlines():
        if ':' in line:
            k, _, v = line.partition(':')
            meta[k.strip()] = v.strip()

    keywords = [kw.strip().lower() for kw in meta.get('keywords', '').split(',') if kw.strip()]
    if not keywords:
        return None

    body = text[m.end():]
    if len(body) > _MAX_SKILL_CHARS:
        body = body[:_MAX_SKILL_CHARS] + '\n... (truncated)'

    return {
        'name': meta.get('name', os.path.basename(path)),
        'keywords': keywords,
        'content': body.strip(),
        'path': path,
    }


def _load_all() -> list[dict]:
    skills = []
    for fname in sorted(os.listdir(SKILLS_DIR)):
        if fname.endswith('.md'):
            skill = _parse(os.path.join(SKILLS_DIR, fname))
            if skill:
                skills.append(skill)
    return skills


def match(user_input: str, max_skills: int = 3) -> list[dict]:
    '''사용자 입력에서 관련 스킬을 찾아 반환. 최대 max_skills개.'''
    text = user_input.lower()
    matched = []
    for skill in _load_all():
        score = sum(1 for kw in skill['keywords'] if kw in text)
        if score > 0:
            matched.append((score, skill))
    matched.sort(key=lambda x: -x[0])
    return [s for _, s in matched[:max_skills]]


def build_context(user_input: str) -> str:
    '''매칭된 스킬을 시스템 프롬프트 삽입용 텍스트로 변환.'''
    skills = match(user_input)
    if not skills:
        return ''
    parts = ['--- 관련 스킬 ---']
    for skill in skills:
        parts.append(f'[{skill["name"]}]\n{skill["content"]}')
    return '\n\n'.join(parts)
