from __future__ import annotations

import argparse
import os
import sys

# Windows 控制台默认 GBK，中文打印乱码——强制 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mini_agent.main import _load_env  # noqa: E402
_load_env()

from mini_agent.agent import Agent  # noqa: E402
from mini_agent.llm import AnthropicLLM, MockLLM, OpenAIChatLLM  # noqa: E402
from mini_agent.mcp_client import register_mcp_tools  # noqa: E402

DEFAULT_TASK = "请调用 MCP 的 count_loc 工具，统计项目里 mini_agent 这个目录下有多少行 Python 代码，然后告诉我结果。"


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
    parser = argparse.ArgumentParser(description="把自定义 MCP server 接进 Agent")
    parser.add_argument("--provider", choices=["mock", "openai", "openai-compatible", "anthropic"], default="mock")
    parser.add_argument("--model", default=None)
    parser.add_argument("--task", default=DEFAULT_TASK)
    args = parser.parse_args()

    llm = build_llm(args.provider, args.model)

    # 关键：用一个子进程把 MCP server 拉起来，把它暴露的工具注册进 Agent
    client, n = register_mcp_tools(sys.executable, ["examples/mcp_server.py"])
    server_tools = client.list_tools()
    print(f"已挂载 {n} 个 MCP 工具: " + ", ".join("mcp_" + t["name"] for t in server_tools))

    agent = Agent(llm)
    print("\n===== Agent 运行结果 =====")
    print(agent.run(args.task))

    client.close()


if __name__ == "__main__":
    main()
