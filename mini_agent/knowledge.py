from __future__ import annotations

import json
import math
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_DIR = os.path.join(ROOT, "knowledge")
INDEX_FILE = os.path.join(KB_DIR, "index.json")


def tokenize(text: str) -> list[str]:
    """简单分词：英文按词、中文按字。生产会换成真正的分词/embedding。"""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    tokens += re.findall(r"[\u4e00-\u9fff]", text)
    return tokens


def embed(text: str) -> dict[str, float]:
    """最朴素的向量：词频归一化（bag-of-words）。真正的 RAG 会换成 embedding 模型。"""
    tokens = tokenize(text)
    if not tokens:
        return {}
    counts = Counter(tokens)
    maxc = max(counts.values())
    return {k: v / maxc for k, v in counts.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def chunk_text(text: str, size: int = 400, overlap: int = 80) -> list[str]:
    """按段落切块，块之间保留一点重叠，避免信息被切碎。"""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) + 1 > size and buf:
            chunks.append(buf)
            buf = buf[-overlap:] if overlap else ""
        buf = (buf + "\n" + p).strip()
    if buf:
        chunks.append(buf)
    return chunks


def build_index(directory: str | None = None, out: str = INDEX_FILE) -> dict:
    """读取目录下的 .md/.txt，切块 + 向量化，保存到 out。"""
    src = directory or KB_DIR
    chunks: list[dict] = []
    for fn in sorted(os.listdir(src)):
        if not fn.endswith((".md", ".txt")):
            continue
        path = os.path.join(src, fn)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for i, ch in enumerate(chunk_text(text)):
            chunks.append({"source": fn, "chunk_id": i, "text": ch})
    for ch in chunks:
        ch["vector"] = embed(ch["text"])
    data = {"chunks": chunks}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def load_index(path: str = INDEX_FILE) -> dict:
    if not os.path.isfile(path):
        return {"chunks": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def search(query: str, top_k: int = 3) -> list[dict]:
    index = load_index()
    qvec = embed(query)
    scored = []
    for ch in index.get("chunks", []):
        s = cosine(qvec, ch.get("vector", {}))
        scored.append({
            "source": ch["source"],
            "chunk_id": ch["chunk_id"],
            "text": ch["text"],
            "score": round(s, 4),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
