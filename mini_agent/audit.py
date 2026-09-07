"""第7课 · 7B 审计与轨迹 —— 落盘审计 + 人类可读的轨迹渲染

两个东西：
  - AuditLogger：把 Agent 的每次事件以「一行一个 JSON」永久追加进日志文件。
  - format_trace：把内存轨迹（list[dict]）渲染成多行文本，给人复盘用。

为什么是 append-only（open(path, "a")）？
  历史记录只追加、不重写、不删除 → 审计作为"证据"的底线：事后无法篡改。
为什么是 JSONL（JSON Lines）？
  一行一个独立 JSON → 机器可读：grep 过滤、tail -f 实时跟、损坏一行不影响其余。
"""

from __future__ import annotations

import json
import os
import time

DEFAULT_LOG_PATH = "logs/agent.jsonl"


class AuditLogger:
    """把事件以 append-only 方式追加进 JSONL 文件。

    enabled=False 时所有方法静默跳过 —— 测试/演示不想污染磁盘日志时用它。
    """

    def __init__(self, path: str = DEFAULT_LOG_PATH, enabled: bool = True):
        self.path = path
        self.enabled = enabled
        if enabled:
            # 目录不存在就自动建（logs/ 在 .gitignore 里，不会污染 git status）
            os.makedirs(os.path.dirname(path), exist_ok=True)

    def log(self, event: dict):
        """写一条事件。event 会被拷贝并补上 ts，不污染调用方对象。"""
        if not self.enabled:
            return
        event = dict(event)                                  # 拷贝：调用方复用同一个 dict 也不受影响
        event.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S"))
        with open(self.path, "a", encoding="utf-8") as f:   # "a" = append-only，只追加
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


def format_trace(trace: list[dict]) -> str:
    """把内存轨迹渲染成人类可读文本：每步一行，按时间顺序。

    按 role 分三档展示：
      - tool          → 工具名(参数) -> 结果 (耗时)
      - final_answer  → 结构化参数（它就是最终答复 JSON）
      - assistant等   → 名: 内容
    """
    lines = []
    for e in trace:
        step = e.get("step", "?")
        role = e.get("role", "")
        if role == "tool":
            elapsed = e.get("elapsed", 0)
            lines.append(f"[{step}] {e.get('name')}({e.get('args')}) "
                         f"-> {e.get('result')} ({elapsed}s)")
        elif role == "final_answer":
            lines.append(f"[{step}] final_answer: {e.get('args')}")
        else:
            lines.append(f"[{step}] {e.get('name', role)}: {e.get('result', '')}")
    return "\n".join(lines)
