"""把 knowledge/ 下的文档建成向量索引，供 kb_search 检索。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mini_agent import knowledge

data = knowledge.build_index()
print(f"已建立 {len(data['chunks'])} 个分块的索引 -> {knowledge.INDEX_FILE}")
