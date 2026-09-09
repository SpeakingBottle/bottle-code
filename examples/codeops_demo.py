"""第8课 · Bottle Code 演示 —— 一个任务同时用上：MCP + RAG + 多Agent + 写文件

默认任务会同时考验四条能力线：
  - mcp_count_loc   统计代码量（第6课 MCP 外部能力）
  - kb_search       查知识库部署步骤（第4课 RAG）
  - write_file      把结果写成文件（第2课工具）
  - 多Agent分工     规划者拆步 / 执行者动手 / 评审者验证（第6课 Orchestrator）
  - 审计            每个角色的轨迹落盘 logs/agent.jsonl（第7课）

用法（在项目根目录运行）：
  .venv/Scripts/python.exe examples/codeops_demo.py --provider mock
  .venv/Scripts/python.exe examples/codeops_demo.py --provider anthropic
"""

from __future__ import annotations

import argparse
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mini_agent.main import _load_env  # noqa: E402
_load_env()

from mini_agent.audit import AuditLogger  # noqa: E402
from mini_agent.codeops import CodeOpsAgent  # noqa: E402
from mini_agent.llm import AnthropicLLM, MockLLM, OpenAIChatLLM  # noqa: E402

DEFAULT_TASK = (
    "请统计这个仓库里 mini_agent 目录有多少行 Python 代码（用 MCP 的 count_loc 工具），"
    "再用 kb_search 查知识库了解这个项目的部署步骤，"
    "最后把部署步骤写进 results/deploy_steps.md，并告诉我结果。"
)


def build_llm(provider: str, model: str | None):
    if provider == "mock":
        return MockLLM()
    if provider in ("openai", "openai-compatible"):
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("请在 .env 中设置 OPENAI_API_KEY")
        return OpenAIChatLLM(model=model or os.environ.get("OPENAI_MODEL", "deepseek-chat"))
    if provider == "anthropic":
        if not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")):
            raise SystemExit("请在 .env 中设置 ANTHROPIC_AUTH_TOKEN")
        return AnthropicLLM(model=model or os.environ.get("ANTHROPIC_MODEL"))
    raise SystemExit(f"不支持的 provider: {provider}")


def main():
    parser = argparse.ArgumentParser(description="Bottle Code 演示")
    parser.add_argument("--provider", choices=["mock", "openai", "openai-compatible", "anthropic"], default="mock")
    parser.add_argument("--model", default=None)
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument("--no-audit", action="store_true", help="不写审计日志（默认写 logs/agent.jsonl）")
    args = parser.parse_args()

    llm = build_llm(args.provider, args.model)
    audit = None if args.no_audit else AuditLogger()

    agent = CodeOpsAgent(llm, mcp_server=["examples/mcp_server.py"], audit=audit)
    try:
        print(f"\n任务：{args.task}\n")
        result = agent.run(args.task)
        print("\n" + "=" * 56)
        print("最终结果：")
        print(f"  status:   {result.get('status')}")
        print(f"  summary:  {result.get('execution', {}).get('summary')}")
        print(f"  result:   {result.get('execution', {}).get('result')}")
        print(f"  评审:      {result.get('review', {}).get('verdict')} — {result.get('review', {}).get('feedback')}")
    finally:
        agent.close()   # 关掉 MCP 子进程


if __name__ == "__main__":
    main()
