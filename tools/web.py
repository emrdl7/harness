import urllib.request
import urllib.error
import urllib.parse
import socket
import ipaddress
import html
import re

try:
    from ddgs import DDGS
    _DDGS_AVAILABLE = True
except ImportError:
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
    # 모델이 max_results 를 "5" 같은 문자열로 넘기는 케이스 — int 강제 변환
    try:
        max_results = int(max_results) if max_results is not None else 5
    except (TypeError, ValueError):
        max_results = 5
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


def _is_safe_url(url: str) -> tuple[bool, str]:
    '''CONCERNS.md §2.7 SSRF 방어:
    - scheme: http / https만
    - host: 내부망(RFC1918, loopback, link-local, metadata 169.254.169.254) 거부
    - file:// / ftp:// / data:// 등 거부
    '''
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False, 'URL 파싱 실패'
    if parsed.scheme not in ('http', 'https'):
        return False, f'허용되지 않는 scheme: {parsed.scheme or "(없음)"} — http/https만 가능'
    host = parsed.hostname
    if not host:
        return False, 'hostname 누락'
    # 모든 A 레코드 검사 (dual-stack + split-horizon 회피)
    try:
        addrs = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False, f'DNS 해석 실패: {host}'
    for family, _, _, _, sockaddr in addrs:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False, f'내부 네트워크 주소 차단: {host} → {ip_str}'
    return True, ''


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    '''SSRF: 리다이렉트 따라가면 우회 가능 — 비활성화.'''
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_page(url: str, max_chars: int = 4000) -> dict:
    # 모델이 max_chars 를 "4000" 같은 문자열로 넘기는 케이스 — int 강제 변환
    try:
        max_chars = int(max_chars) if max_chars is not None else 4000
    except (TypeError, ValueError):
        max_chars = 4000
    '''URL에서 텍스트 내용을 가져옴 (HTML 태그 제거).

    CONCERNS.md §2.7 대응: scheme 제한 + 내부망 차단 + 리다이렉트 금지.
    '''
    ok, err = _is_safe_url(url)
    if not ok:
        return {'ok': False, 'error': err}
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; harness/1.0)'},
        )
        opener = urllib.request.build_opener(_NoRedirectHandler())
        with opener.open(req, timeout=10) as resp:
            raw = resp.read().decode('utf-8', errors='ignore')
        text = _strip_html(raw)
        return {'ok': True, 'content': text[:max_chars], 'url': url}
    except urllib.error.HTTPError as e:
        # 3xx는 리다이렉트 금지로 여기에 떨어짐 — 사용자에 의미있는 에러 반환
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
