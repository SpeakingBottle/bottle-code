from __future__ import annotations

import argparse
import os
import sys

# Windows 控制台默认可能是 cp936，导致中文输出乱码；强制用 UTF-8 输出更通用。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .agent import Agent
from .llm import MockLLM, OpenAIChatLLM


def build_agent(provider, model, base_url):
    if provider == "mock":
        return Agent(MockLLM())
    if provider in ("openai", "openai-compatible"):
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("请在 .env 中设置 OPENAI_API_KEY（或通过 --api-key 传入）")
        return Agent(OpenAIChatLLM(model=model, base_url=base_url))
    raise SystemExit(f"不支持的 provider: {provider}")


def main():
    parser = argparse.ArgumentParser(description="迷你 Agent 命令行")
    parser.add_argument("--provider", choices=["mock", "openai", "openai-compatible"], default="mock")
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--prompt", "-p", help="一次性执行完这条提示后退出；不传则进入交互问答")
    args = parser.parse_args()

    agent = build_agent(args.provider, args.model, args.base_url)
    agent.max_steps = args.max_steps

    if args.prompt:
        print(agent.run(args.prompt))
        return

    print("迷你 Agent 已启动（Ctrl+C 退出）")
    print("试试：帮我计算 2+3 的结果")
    while True:
        try:
            user = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user:
            continue
        if user in ("exit", "quit", "退出"):
            break
        print("\n助手:", agent.run(user))


if __name__ == "__main__":
    main()
