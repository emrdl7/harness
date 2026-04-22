import os
import ast
import re
import json
import hashlib
import chromadb
from chromadb.utils import embedding_functions

INDEX_DIR = os.path.expanduser('~/.harness/index')

EXTENSIONS = {
    '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
    '.tsx': 'tsx', '.jsx': 'jsx', '.go': 'go', '.rs': 'rust',
    '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.rb': 'ruby',
    '.php': 'php', '.swift': 'swift', '.kt': 'kotlin',
    '.sh': 'bash', '.md': 'markdown',
}
IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.next'}
MAX_FILE_SIZE = 100 * 1024


def _project_id(directory: str) -> str:
    return hashlib.md5(os.path.abspath(directory).encode()).hexdigest()[:12]


def _mtime_path(project_id: str) -> str:
    return os.path.join(INDEX_DIR, project_id, 'mtimes.json')


def _load_mtimes(project_id: str) -> dict:
    path = _mtime_path(project_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_mtimes(project_id: str, mtimes: dict):
    path = _mtime_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(mtimes, f)


_EMBED_MODEL_DIR = os.path.expanduser('~/.cache/chroma/onnx_models')


def _embed_model_already_cached() -> bool:
    '''ChromaDB DefaultEmbeddingFunction의 ONNX 모델 캐시 존재 여부.'''
    return os.path.isdir(_EMBED_MODEL_DIR) and any(os.scandir(_EMBED_MODEL_DIR))


def _get_collection(project_id: str):
    '''CONCERNS.md §1.11 대응: 첫 실행 시 ONNX 임베딩 모델(~80MB) 다운로드가
    있어 사용자에겐 멈춘 것처럼 보였음. 캐시 부재 시 stderr에 명시 안내.
    HARNESS_EMBED_MODEL env로 override 가능 (향후 확장용 훅).'''
    os.makedirs(INDEX_DIR, exist_ok=True)
    if not _embed_model_already_cached():
        import sys
        print(
            '[indexer] 첫 인덱싱 — 임베딩 모델(ONNX, ~80MB) 다운로드 중...\n'
            '           캐시 위치: ~/.cache/chroma/onnx_models\n'
            '           네트워크 없이 시작하면 실패할 수 있음.',
            file=sys.stderr,
        )
    client = chromadb.PersistentClient(path=os.path.join(INDEX_DIR, project_id))
    ef = embedding_functions.DefaultEmbeddingFunction()
    return client.get_or_create_collection('code', embedding_function=ef)


def _chunk_python(source: str, filepath: str) -> list[dict]:
    chunks = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [{'content': source[:2000], 'name': filepath, 'kind': 'file'}]

    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            snippet = '\n'.join(lines[node.lineno - 1:node.end_lineno])
            if len(snippet) > 50:
                chunks.append({
                    'content': snippet,
                    'name': f'{filepath}:{node.name}',
                    'kind': 'class' if isinstance(node, ast.ClassDef) else 'function',
                })
    return chunks or [{'content': source[:3000], 'name': filepath, 'kind': 'file'}]


def _chunk_generic(source: str, filepath: str, lang: str) -> list[dict]:
    fn_patterns = [
        r'(?:^|\n)(?:export\s+)?(?:async\s+)?function\s+(\w+)',
        r'(?:^|\n)(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(',
        r'(?:^|\n)func\s+(\w+)', r'(?:^|\n)(?:pub\s+)?fn\s+(\w+)',
        r'(?:^|\n)(?:export\s+)?class\s+(\w+)',
        r'(?:^|\n)type\s+(\w+)\s+struct',
    ]
    lines = source.splitlines()
    chunks = []
    for i in range(0, len(lines), 60):
        block = '\n'.join(lines[i:i + 60])
        if len(block.strip()) < 20:
            continue
        name = filepath
        for pat in fn_patterns:
            m = re.search(pat, block)
            if m:
                name = f'{filepath}:{m.group(1)}'
                break
        chunks.append({'content': block, 'name': name, 'kind': 'chunk'})
    return chunks or [{'content': source[:3000], 'name': filepath, 'kind': 'file'}]


def _index_file(fpath: str, rel: str, collection, ext: str):
    try:
        with open(fpath, encoding='utf-8', errors='ignore') as f:
            source = f.read()
    except Exception:
        return 0

    lang = EXTENSIONS[ext]
    chunks = _chunk_python(source, rel) if ext == '.py' else _chunk_generic(source, rel, lang)

    # 기존 청크 삭제 후 재삽입
    existing = collection.get(where={'file': rel})
    if existing['ids']:
        collection.delete(ids=existing['ids'])

    docs, ids, metas = [], [], []
    for i, chunk in enumerate(chunks):
        doc_id = hashlib.md5(f'{rel}:{i}'.encode()).hexdigest()
        docs.append(chunk['content'])
        ids.append(doc_id)
        metas.append({'file': rel, 'name': chunk['name'], 'kind': chunk['kind'], 'lang': lang})

    if docs:
        collection.upsert(documents=docs, ids=ids, metadatas=metas)
    return len(docs)


def _scan_files(directory: str) -> dict[str, float]:
    '''디렉토리 내 대상 파일 경로 → mtime 매핑'''
    result = {}
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in EXTENSIONS:
                continue
            fpath = os.path.join(root, fname)
            if os.path.getsize(fpath) > MAX_FILE_SIZE:
                continue
            rel = os.path.relpath(fpath, directory)
            result[rel] = os.path.getmtime(fpath)
    return result


def index_directory(directory: str) -> dict:
    '''전체 인덱싱 (첫 실행 또는 /index 강제 실행)'''
    project_id = _project_id(directory)
    collection = _get_collection(project_id)

    current = _scan_files(directory)
    total, skipped = 0, 0

    for rel, mtime in current.items():
        fpath = os.path.join(directory, rel)
        ext = os.path.splitext(rel)[1].lower()
        n = _index_file(fpath, rel, collection, ext)
        if n:
            total += n
        else:
            skipped += 1

    _save_mtimes(project_id, current)
    return {'project_id': project_id, 'indexed': total, 'skipped': skipped}


def sync_index(directory: str) -> dict:
    '''증분 인덱싱 — 변경/추가/삭제된 파일만 처리'''
    project_id = _project_id(directory)

    if not is_indexed(directory):
        return index_directory(directory)

    collection = _get_collection(project_id)
    saved = _load_mtimes(project_id)
    current = _scan_files(directory)

    added = {r: t for r, t in current.items() if r not in saved}
    changed = {r: t for r, t in current.items() if r in saved and t != saved[r]}
    removed = {r for r in saved if r not in current}

    updated = 0
    for rel in {**added, **changed}:
        fpath = os.path.join(directory, rel)
        ext = os.path.splitext(rel)[1].lower()
        updated += _index_file(fpath, rel, collection, ext)

    for rel in removed:
        existing = collection.get(where={'file': rel})
        if existing['ids']:
            collection.delete(ids=existing['ids'])

    if added or changed or removed:
        _save_mtimes(project_id, current)

    return {
        'added': len(added),
        'changed': len(changed),
        'removed': len(removed),
        'updated_chunks': updated,
    }


def is_indexed(directory: str) -> bool:
    project_id = _project_id(directory)
    return os.path.exists(_mtime_path(project_id))
