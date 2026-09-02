from __future__ import annotations

import datetime
import json
import os


class AuditLogger:
    """把 Agent 的每一步写进 JSONL 日志文件，实现"审计"。

    JSONL（每行一个 JSON 对象）很适合审计：
    - 只追加、不覆盖，天然是只读的历史；
    - 每行独立，可以逐行读、用工具/脚本 grep 分析；
    - 随时可以 truncate，不需要数据库。
    """

    def __init__(self, path: str = "logs/agent.jsonl", enabled: bool = True):
        self.path = path
        self.enabled = enabled
        self.count = 0

    def log(self, event: dict):
        self.count += 1
        if not self.enabled:
            return
        event = dict(event)
        event.setdefault("ts", datetime.datetime.now().isoformat(timespec="seconds"))
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


def format_trace(trace: list[dict]) -> str:
    """把 Agent.trace 转成人类可读的轨迹文本，用于"轨迹观测"。"""
    lines = []
    for ev in trace:
        role = ev.get("role")
        name = ev.get("name")
        step = ev.get("step")
        if role == "tool":
            lines.append(
                f"[{step}] 调用 {name}({ev.get('args')})  → {str(ev.get('result'))[:200]}  ({ev.get('elapsed')}s)"
            )
        elif role == "final_answer":
            args = ev.get("args") or {}
            lines.append(f"[{step}] ✅ final_answer → summary={args.get('summary', '')}")
        else:
            lines.append(f"[{step}] {name}: {str(ev.get('result'))[:200]}")
    return "\n".join(lines)
