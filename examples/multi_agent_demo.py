from __future__ import annotations

import argparse
import json
import os
import sys

# 让脚本能 import 到项目根目录下的 mini_agent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 复用 main 里的 .env 加载逻辑（兼容没装 python-dotenv 的情况）
from mini_agent.main import _load_env  # noqa: E402
_load_env()

from mini_agent.llm import MockLLM, OpenAIChatLLM  # noqa: E402
from mini_agent.roles import Orchestrator  # noqa: E402

DEFAULT_TASK = "请先用 calculator 算出 (3+5)*2 的结果，再查看项目根目录下有哪些 .py 文件，然后汇总这两条信息。"


def build_llm(provider: str, model: str | None):
    if provider == "mock":
        return MockLLM()
    if provider in ("openai", "openai-compatible"):
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("请在 .env 中设置 OPENAI_API_KEY")
        return OpenAIChatLLM(model=model or os.environ.get("OPENAI_MODEL", "deepseek-chat"))
    raise SystemExit(f"不支持的 provider: {provider}")


def main():
    parser = argparse.ArgumentParser(description="多 Agent 分工演示：规划者 / 执行者 / 评审者")
    parser.add_argument("--provider", choices=["mock", "openai", "openai-compatible"], default="mock")
    parser.add_argument("--model", default=None)
    parser.add_argument("--task", default=DEFAULT_TASK, help="要交给多 Agent 协作完成的任务")
    parser.add_argument("--max-retries", type=int, default=2, help="评审不通过时最多让执行者重试几轮")
    args = parser.parse_args()

    llm = build_llm(args.provider, args.model)
    orch = Orchestrator(llm, max_retries=args.max_retries, verbose=True)
    result = orch.run(args.task)

    print("\n===== 最终结构化结果 =====")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
