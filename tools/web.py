import urllib.request
import urllib.error
import html
import re
import unicodedata

try:
    from duckduckgo_search import DDGS
    _DDGS_AVAILABLE = True
except ImportError:
    _DDGS_AVAILABLE = False


def _clean_query(query: str) -> str:
    '''키릴·그리스 등 명백한 노이즈 문자가 전체 알파벳의 30% 이상일 때만 제거.
    한-영 혼합 쿼리는 보존.'''
    korean      = sum(1 for c in query if '가' <= c <= '힣' or 'ᄀ' <= c <= 'ᇿ')
    latin       = sum(1 for c in query if c.isascii() and c.isalpha())
    other_alpha = sum(1 for c in query
                      if c.isalpha() and not c.isascii()
                      and not ('가' <= c <= '힣') and not ('ᄀ' <= c <= 'ᇿ')
                      and not ('぀' <= c <= '鿿'))
    total_alpha = korean + latin + other_alpha
    if total_alpha > 0 and other_alpha / total_alpha > 0.3:
        cleaned = ''.join(
            c for c in query
            if (
                c.isascii()
                or '가' <= c <= '힣'
                or 'ᄀ' <= c <= 'ᇿ'
                or '぀' <= c <= '鿿'
                or not c.isalpha()
            )
        )
        cleaned = ' '.join(cleaned.split())
        if cleaned != query:
            return cleaned
    return query


def search_web(query: str, max_results: int = 5) -> dict:
    '''DuckDuckGo로 웹 검색. API 키 불필요.'''
    if not _DDGS_AVAILABLE:
        return {'ok': False, 'error': 'duckduckgo_search 패키지가 없습니다. pip install duckduckgo_search'}
    original = query
    query = _clean_query(query)
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    'title': r.get('title', ''),
                    'url': r.get('href', ''),
                    'snippet': r.get('body', ''),
                })
        if not results:
            return {'ok': True, 'results': [], 'summary': '검색 결과 없음'}
        summary = _format_results(results)
        note = f' (쿼리 정제: "{original}" → "{query}")' if query != original else ''
        return {'ok': True, 'results': results, 'summary': summary + note}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def fetch_page(url: str, max_chars: int = 4000) -> dict:
    '''URL에서 텍스트 내용을 가져옴 (HTML 태그 제거).'''
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; harness/1.0)'},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode('utf-8', errors='ignore')
        text = _strip_html(raw)
        return {'ok': True, 'content': text[:max_chars], 'url': url}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'error': f'HTTP {e.code}: {e.reason}'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def _format_results(results: list) -> str:
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f'[{i}] {r["title"]}\n{r["url"]}\n{r["snippet"]}')
    return '\n\n'.join(parts)


def _strip_html(raw: str) -> str:
    # script/style 블록 제거
    raw = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', raw, flags=re.DOTALL | re.IGNORECASE)
    # 태그 제거
    raw = re.sub(r'<[^>]+>', ' ', raw)
    # HTML 엔티티 디코딩
    raw = html.unescape(raw)
    # 연속 공백 정리
    raw = re.sub(r'[ \t]+', ' ', raw)
    raw = re.sub(r'\n{3,}', '\n\n', raw)
    return raw.strip()
