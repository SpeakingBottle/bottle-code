from __future__ import annotations

import argparse
import os
import sys

# Windows 控制台默认可能是 cp936，导致中文输出乱码；强制用 UTF-8 输出更通用。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

def _load_env() -> None:
    """加载 .env：优先用 python-dotenv；没装也能用内置兜底解析器，保证项目开箱即用。"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        return
    except ImportError:
        pass

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            os.environ.setdefault(key.strip(), value)


_load_env()

from .agent import Agent
from .approval import TerminalApprover
from .llm import AnthropicLLM, MockLLM, OpenAIChatLLM


def build_agent(provider, model, base_url, approver=None):
    if provider == "mock":
        return Agent(MockLLM(), approver=approver)
    if provider in ("openai", "openai-compatible"):
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("未找到 OPENAI_API_KEY。请在项目根目录的 .env 中设置（格式见 .env.example）")
        return Agent(OpenAIChatLLM(model=model, base_url=base_url), approver=approver)
    if provider == "anthropic":
        if not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")):
            raise SystemExit("未找到 ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY。请在项目根目录的 .env 中设置（格式见 .env.example）")
        return Agent(AnthropicLLM(model=model, base_url=base_url), approver=approver)
    raise SystemExit(f"不支持的 provider: {provider}")


def main():
    parser = argparse.ArgumentParser(description="迷你 Agent 命令行")
    parser.add_argument("--provider", choices=["mock", "openai", "openai-compatible", "anthropic"], default="mock")
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--max-steps", type=int, default=24)
    parser.add_argument("--prompt", "-p", help="一次性执行完这条提示后退出；不传则进入交互问答")
    parser.add_argument("--approve", action="store_true",
                        help="写文件/跑命令前逐次征求批准（不传则自动放行并记入轨迹）")
    args = parser.parse_args()

    approver = TerminalApprover() if args.approve else None
    agent = build_agent(args.provider, args.model, args.base_url, approver=approver)
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
