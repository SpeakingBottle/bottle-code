"""第10课 · 流式输出演示 —— 让 Agent 边想边说

对比非流式：等模型全部生成完才一次性看到答复；
流式：第一个字几百毫秒就出现，边生成边显示（网页版体验的关键）。

用法（在项目根目录运行）：
  .venv/Scripts/python.exe examples/stream_demo.py --provider mock
  .venv/Scripts/python.exe examples/stream_demo.py --provider anthropic
"""

from __future__ import annotations

import argparse
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mini_agent.agent import Agent  # noqa: E402
from mini_agent.llm import AnthropicLLM, MockLLM, OpenAIChatLLM  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="流式输出演示")
    parser.add_argument("--provider", default="mock", choices=["mock", "anthropic", "openai"])
    parser.add_argument("--prompt", default="帮我计算 2+3 的结果")
    parser.add_argument("--system", default=None,
                        help="自定义系统提示词。默认用 Agent 的（会强制 final_answer 结构化收尾）；"
                             "想看纯文本流式可传 '直接回答，不要调用工具'")
    args = parser.parse_args()

    if args.provider == "mock":
        llm = MockLLM()
    elif args.provider == "anthropic":
        llm = AnthropicLLM()
    else:
        llm = OpenAIChatLLM()

    agent = Agent(llm, system_prompt=args.system) if args.system else Agent(llm)
    print(f"用户: {args.prompt}\n")
    print("Agent（流式）: ", end="", flush=True)
    gen = agent.run(args.prompt, stream=True)
    streamed: list[str] = []
    try:
        while True:
            delta = next(gen)
            streamed.append(delta)
            print(delta, end="", flush=True)
    except StopIteration as e:
        final = e.value   # 生成器 return 的最终答复
    print()
    # final_answer 结构化收尾时没有流式文本，把结构化结果补打出来
    if final and final != "".join(streamed):
        print("最终答复（结构化）:", final)


if __name__ == "__main__":
    main()
