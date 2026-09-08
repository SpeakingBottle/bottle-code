"""进阶课1 · 检索质量评估 —— 对比 词频版 vs embedding版 vs 混合版

评测集：一组"查询 → 期望命中的文档"，指标 hit@k（期望文档是否出现在前 k 名）。
没有评估，你分不清新旧方案谁好——这是第7课评测思想在 RAG 上的复用。

用法（在项目根目录运行）：
  .venv/Scripts/python.exe examples/rag_eval.py
"""

from __future__ import annotations

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mini_agent import knowledge  # noqa: E402   # 词频版（第4课）
from mini_agent import knowledge_embed  # noqa: E402   # embedding 版（进阶课1）

# 评测集：查询 → 期望命中的文档（knowledge/ 下有哪些文件，就按内容设计查询）
# 4 份文档、10+ 个块，top-3 才有区分度——如果知识库太小，任何方案都是 100%，评测就失去意义
EVAL_SET = [
    {"query": "这个项目的部署步骤是什么", "expect": "project.md"},
    {"query": "怎么把服务跑起来", "expect": "project.md"},
    {"query": "第7课讲了什么", "expect": "lesson_notes.md"},
    {"query": "权限最小化怎么做", "expect": "lesson_notes.md"},
    {"query": "MCP 怎么接入外部工具", "expect": "architecture.md"},
    {"query": "多 Agent 怎么分工", "expect": "architecture.md"},
    {"query": "越权调用被拦截怎么处理", "expect": "troubleshooting.md"},
    {"query": "审计日志没写盘怎么办", "expect": "troubleshooting.md"},
]


def hit_at_k(search_fn, k: int = 3) -> float:
    """对评测集跑检索，返回 hit@k：期望文档出现在前 k 名的查询占比。"""
    hits = 0
    for item in EVAL_SET:
        results = search_fn(item["query"], top_k=k)
        sources = {r["source"] for r in results}
        if item["expect"] in sources:
            hits += 1
    return hits / len(EVAL_SET)


def main():
    # 两个方案都要先建索引（词频版用 JSON，embedding 版用 Chroma）
    print("构建词频版索引...")
    knowledge.build_index()
    print("构建 embedding 版索引（首次会下载模型，稍等）...")
    n = knowledge_embed.build_index()
    print(f"embedding 版索引：{n} 个块\n")

    print("=" * 56)
    print(f"{'方案':<16}{'hit@3':<10}")
    print("-" * 56)
    for name, fn in [
        ("词频版（第4课）", knowledge.search),
        ("embedding 版", lambda q, top_k: knowledge_embed.search(q, top_k, use_hybrid=False)),
        ("混合版（BM25+向量）", knowledge_embed.search),
    ]:
        score = hit_at_k(fn)
        print(f"{name:<16}{score * 100:>6.0f}%")
    print("=" * 56)


if __name__ == "__main__":
    main()
