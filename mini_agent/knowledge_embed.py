"""进阶课1 · 生产级 RAG —— embedding + 向量库 + 混合检索

与 knowledge.py（词频版）暴露【完全相同的接口】：build_index / load_index / search。
上层（tools.py 的 kb_search、Agent）只依赖接口，不依赖实现——这就是"依赖倒置"。

四个升级：
  ① embedding 向量化：fastembed 加载 BAAI/bge-small-zh-v1.5（中文，384 维，ONNX 无 torch）
  ② 向量数据库：Chroma PersistentClient（持久化 + ANN 近似最近邻检索）
  ③ 混合检索：BM25（关键词精确命中）+ 向量（语义匹配），RRF 排名融合
  ④ 检索评估：examples/rag_eval.py 用 hit@k 对比新旧方案

依赖：pip install fastembed chromadb
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter

from .knowledge import chunk_text, tokenize  # 复用第4课的切块/分词

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_DIR = os.path.join(ROOT, "knowledge")
CHROMA_DIR = os.path.join(ROOT, "chroma")          # 向量库持久化目录（已 gitignore）
COLLECTION = "kb_index"   # Chroma 集合名要求 3~512 字符
MODEL = "BAAI/bge-small-zh-v1.5"                   # 中文 embedding 模型（首次运行自动下载 ~95MB）

# ---------------------------------------------------------------------------
# ① embedding：fastembed 封装（懒加载：第一次 embed 才下载模型）
# ---------------------------------------------------------------------------

_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding
        _embedder = TextEmbedding(model_name=MODEL)
    return _embedder


def embed_texts(texts: list[str]) -> list[list[float]]:
    """把一批文本转成稠密向量（384 维 float32）。"""
    return [v.tolist() for v in _get_embedder().embed(texts)]


# ---------------------------------------------------------------------------
# ② 向量库：Chroma 持久化
# ---------------------------------------------------------------------------

def _client():
    import chromadb
    return chromadb.PersistentClient(path=CHROMA_DIR)


def _collection():
    # embedding_function=None：我们自己算好向量再传，不用 Chroma 内置的 embedding
    return _client().get_or_create_collection(name=COLLECTION, embedding_function=None)


def build_index(directory: str | None = None) -> int:
    """读 knowledge/ 下的 .md/.txt → 切块 → embedding → 写入 Chroma。返回块数。"""
    src = directory or KB_DIR
    chunks: list[dict] = []
    for fn in sorted(os.listdir(src)):
        if not fn.endswith((".md", ".txt")):
            continue
        with open(os.path.join(src, fn), encoding="utf-8") as f:
            text = f.read()
        for i, ch in enumerate(chunk_text(text)):
            chunks.append({"source": fn, "chunk_id": i, "text": ch})

    if not chunks:
        return 0
    # 重建索引：删掉旧集合再建，保证"检索结果来自本次构建"（Chroma 1.5 不支持 delete(where={})）
    client = _client()
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    col = client.get_or_create_collection(name=COLLECTION, embedding_function=None)
    col.add(
        ids=[f"{c['source']}#{c['chunk_id']}" for c in chunks],
        documents=[c["text"] for c in chunks],
        embeddings=embed_texts([c["text"] for c in chunks]),
        metadatas=[{"source": c["source"], "chunk_id": c["chunk_id"]} for c in chunks],
    )
    return len(chunks)


def load_index() -> int:
    """返回当前向量库里的块数（0 = 还没建索引）。"""
    return _collection().count()


# ---------------------------------------------------------------------------
# ③ 混合检索：BM25 + 向量，RRF 排名融合
# ---------------------------------------------------------------------------

def _bm25_scores(query_tokens: list[str], docs: list[str]) -> list[float]:
    """手写 BM25：关键词精确匹配的经典打分。

    BM25 的核心直觉：词在文档里出现越多分越高（tf），
    但"的/了"这种到处都有的词要降权（idf），文档越长越要稀释（长度归一）。
    """
    n = len(docs)
    avg_len = sum(len(d.split()) for d in docs) / max(n, 1)
    k1, b = 1.5, 0.75   # 标准超参
    scores = []
    for d in docs:
        tokens = d.split()
        df = {t: sum(1 for x in docs if t in x.split()) for t in set(query_tokens)}
        s = 0.0
        for t in query_tokens:
            tf = tokens.count(t)
            if tf == 0:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * len(tokens) / avg_len))
        scores.append(s)
    return scores


def _rrf_fuse(ranked_lists: list[list[int]], k: int = 60) -> list[int]:
    """RRF（Reciprocal Rank Fusion）：把多个排序结果按"排名"融合，不比较原始分数。

    每个文档的融合分 = Σ 1/(k + rank_i)。k=60 是论文推荐值。
    好处：BM25 的分数和余弦相似度量纲完全不同，直接加权相加没意义；
    但"排名"是可比的一一第 1 名就是第 1 名。
    """
    fused: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, idx in enumerate(ranked):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(fused, key=fused.get, reverse=True)


def search(query: str, top_k: int = 3, use_hybrid: bool = True) -> list[dict]:
    """混合检索：BM25 候选 + 向量候选 → RRF 融合 → 返回 top_k。接口与 knowledge.py 一致。

    use_hybrid=False 时退化为"纯向量检索"，供评估脚本对比混合检索的增益。
    """
    col = _collection()
    if col.count() == 0:
        return []

    # 候选池：向量检索取 top_k*3，BM25 在候选池内打分（避免对全库算 BM25）
    qvec = embed_texts([query])[0]
    vec_hits = col.query(query_embeddings=[qvec], n_results=top_k * 3,
                         include=["documents", "metadatas", "distances"])
    docs = vec_hits["documents"][0]
    metas = vec_hits["metadatas"][0]
    dists = vec_hits["distances"][0]

    # 向量排序：Chroma 返回的是距离（越小越近），转成排名
    vec_rank = sorted(range(len(docs)), key=lambda i: dists[i])
    if not use_hybrid:
        fused = vec_rank
    else:
        # BM25 排序：在候选池内按关键词打分
        bm25 = _bm25_scores(tokenize(query), docs)
        bm25_rank = sorted(range(len(docs)), key=lambda i: bm25[i], reverse=True)
        # RRF 融合两个排名
        fused = _rrf_fuse([vec_rank, bm25_rank])

    out = []
    for idx in fused[:top_k]:
        out.append({
            "source": metas[idx]["source"],
            "chunk_id": metas[idx]["chunk_id"],
            "text": docs[idx],
            "score": round(1.0 / (60 + fused.index(idx) + 1), 4),  # 融合分（RRF 值）
        })
    return out
