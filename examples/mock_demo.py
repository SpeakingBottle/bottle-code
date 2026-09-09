"""离线演示：用 MockLLM 展示 Agent 循环（不需要 API key）。

运行：python examples/mock_demo.py
它会经历：用户提问 → 模型决定调用 calculator → 工具返回结果 → 模型给出最终答复。
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mini_agent.agent import Agent
from mini_agent.llm import MockLLM

agent = Agent(MockLLM())
answer = agent.run("帮我计算 2+3 的结果")
print("\n最终答复:", answer)
