import os
from context.indexer import _project_id, _get_collection as _get_client

TOP_K = 8
MIN_RELEVANCE = 0.4  # cosine distance 임계값 (낮을수록 유사)


def search(query: str, directory: str, k: int = TOP_K) -> list[dict]:
    project_id = _project_id(directory)
    index_path = os.path.join(os.path.expanduser('~/.harness/index'), project_id)
    if not os.path.exists(index_path):
        return []

    try:
        collection = _get_client(project_id)
        results = collection.query(
            query_texts=[query],
            n_results=min(k, collection.count()),
            include=['documents', 'metadatas', 'distances'],
        )
    except Exception:
        return []

    chunks = []
    for doc, meta, dist in zip(
        results['documents'][0],
        results['metadatas'][0],
        results['distances'][0],
    ):
        if dist < MIN_RELEVANCE or not chunks:  # 최소 1개는 포함
            chunks.append({
                'content': doc,
                'file': meta.get('file', ''),
                'name': meta.get('name', ''),
                'kind': meta.get('kind', ''),
                'distance': round(dist, 3),
            })

    return chunks


def format_context(chunks: list[dict]) -> str:
    if not chunks:
        return ''
    parts = ['--- 관련 코드 ---']
    for c in chunks:
        parts.append(f'// {c["name"]} (유사도: {1 - c["distance"]:.2f})')
        parts.append(c['content'])
        parts.append('')
    return '\n'.join(parts)
