"""第8课 · 合成层 —— CodeOps Agent

把前 7 课的东西"接线"成一个完整可运行的作品：
  读代码库（第2课工具） + 查知识库（第4课RAG） + 多Agent分工（第6课Orchestrator）
  + 外部能力（第6课MCP repo-stats） + 可靠性（第7课白名单/审计）

设计原则：复用不是重写。这个文件里没有新算法，只有"组合"——
  1. 把 MCP server 的工具注册成 mcp_* 前缀的 Tool（第6课 mcp_client 的活）
  2. 把 mcp_* 工具追加进执行者的白名单（第7课 allowed_tools 的活）
  3. 给每个角色挂上审计（第7课 audit 的活）
  4. 对外只暴露一个 run(task) 入口
"""

from __future__ import annotations

import sys

from .audit import AuditLogger
from .llm import LLM
from .mcp_client import register_mcp_tools
from .roles import Orchestrator


class CodeOpsAgent:
    """CodeOps Agent：Orchestrator + MCP repo-stats + 审计，一个干净的 run() 入口。

    用法：
        agent = CodeOpsAgent(llm, mcp_server=["examples/mcp_server.py"], audit=AuditLogger())
        result = agent.run("统计这个仓库的代码量")
        agent.close()   # 关掉 MCP 子进程
    """

    def __init__(self, llm: LLM, mcp_server: list[str] | None = None,
                 audit: AuditLogger | None = None, max_retries: int = 2,
                 verbose: bool = True):
        self.llm = llm
        self.verbose = verbose
        self.mcp_client = None

        # ① 接线 MCP：把 server 暴露的工具注册成 mcp_* 前缀的 Tool
        extra_tools: set[str] = set()
        if mcp_server:
            self.mcp_client, n = register_mcp_tools(sys.executable, mcp_server)
            extra_tools = {f"mcp_{t['name']}" for t in self.mcp_client.list_tools()}
            if verbose:
                print(f"已挂载 {n} 个 MCP 工具: {sorted(extra_tools)}")

        # ② 接线多 Agent + 可靠性：执行者追加 mcp_* 工具，所有角色挂审计
        self.orchestrator = Orchestrator(
            llm, max_retries=max_retries, verbose=verbose,
            extra_executor_tools=extra_tools, audit=audit,
        )

    def run(self, task: str) -> dict:
        """一个入口：把任务交给编排器（规划者 → 执行者 → 评审者）。"""
        return self.orchestrator.run(task)

    def close(self):
        """收尾：关掉 MCP 子进程，避免残留。"""
        if self.mcp_client:
            self.mcp_client.close()
