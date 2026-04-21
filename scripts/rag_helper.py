"""
rag_helper.py — 年报向量检索模块（含 Reranking）
"""
from pathlib import Path

_DB_DIR = Path(__file__).parent.parent / "pulse_vectordb"
_embedder = None
_collection = None
_reranker = None

def _init():
    global _embedder, _collection, _reranker
    if _collection is not None:
        return
    if not _DB_DIR.exists():
        print("[RAG] 向量数据库不存在，跳过")
        return
    try:
        from sentence_transformers import SentenceTransformer, CrossEncoder
        import chromadb
        _embedder = SentenceTransformer("BAAI/bge-small-zh-v1.5")
        _reranker = CrossEncoder("BAAI/bge-reranker-base")
        client = chromadb.PersistentClient(path=str(_DB_DIR))
        _collection = client.get_collection("reports")
        print(f"[RAG] 已加载，共 {_collection.count()} 个文本块")
    except Exception as e:
        print(f"[RAG] 初始化失败，跳过: {e}")

def retrieve(query: str, top_k: int = 3) -> str:
    _init()
    if _collection is None or _embedder is None:
        return ""
    try:
        # 1. 粗召回：多取一些候选
        vector = _embedder.encode(query).tolist()
        results = _collection.query(
            query_embeddings=[vector],
            n_results=min(20, _collection.count())
        )
        candidates = results["documents"][0]
        if not candidates:
            return ""

        # 2. Reranking：重新打分排序
        if _reranker is not None:
            pairs = [(query, doc) for doc in candidates]
            scores = _reranker.predict(pairs)
            ranked = sorted(zip(candidates, scores),
                          key=lambda x: x[1], reverse=True)
            top_docs = [doc for doc, score in ranked[:top_k]]
        else:
            top_docs = candidates[:top_k]

        context = "\n---\n".join(top_docs)
        return f"\n## 相关年报背景\n{context}\n"

    except Exception as e:
        print(f"[RAG] 检索失败: {e}")
        return ""
