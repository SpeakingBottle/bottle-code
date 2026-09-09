"""第11课 · 代码 Agent 闭环演示 —— 写代码 → 跑测试 → 改

任务：让 Agent 独立完成一个编码任务。核心不是"一次写对"，而是演示闭环：
  write_file 写出实现和测试 → run_python 跑测试 → 失败反馈 → 修改 → 再跑 → 通过

默认任务（斐波那契）测试覆盖到 n=40 / n=45：朴素递归会跑到 run_python 的 30s 超时，
Agent 必须读反馈、改成迭代/DP 才能通过——闭环被确定性逼出来。
（如果模型一上来就写迭代版，首跑即过也成立：闭环收缩为 写→测→过。）

所有生成的脚本都隔离在 examples/_work/ 里，不污染仓库根目录。

用法（在项目根目录运行）：
  .venv/Scripts/python.exe examples/lesson11_demo.py --provider mock
  .venv/Scripts/python.exe examples/lesson11_demo.py --provider anthropic
  .venv/Scripts/python.exe examples/lesson11_demo.py --provider anthropic --task "自定义编码任务"
  .venv/Scripts/python.exe examples/lesson11_demo.py --provider anthropic --no-trace
"""

from __future__ import annotations

import argparse
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

# 隔离工作目录：Agent 的写文件 / run_python 都发生在 examples/_work 里。
# 必须在 import mini_agent（tools.py 读取 BASE_DIR）之前设置，否则不生效。
WORK = os.path.join(BASE, "examples", "_work")
os.makedirs(WORK, exist_ok=True)
os.environ["AGENT_WORKDIR"] = WORK

from mini_agent.main import _load_env  # noqa: E402
_load_env()

from mini_agent.agent import Agent  # noqa: E402
from mini_agent.llm import AnthropicLLM, MockLLM, OpenAIChatLLM  # noqa: E402

DEFAULT_TASK = (
    "这是一个编码任务，请完成一个计算斐波那契数列的小函数库：\n"
    "1) 写 fib.py：定义 fib(n) 返回斐波那契数列第 n 项（n 为非负整数，fib(0)=0, fib(1)=1）。\n"
    "2) 写 test_fib.py：用 assert 验证 fib(0)==0、fib(1)==1、fib(10)==55、"
    "fib(40)==102334155、fib(45)==1134903170，全部通过时打印一行 ALL PASSED。\n"
    "3) 用 run_python 运行 test_fib.py 验证：如果失败或超时，读报错、改实现、再跑，直到 ALL PASSED。\n"
    "4) 全部通过后调用 final_answer 汇报。"
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


def render_trace(trace: list[dict]) -> str:
    """把轨迹渲染成「步骤 · 角色 → 内容摘要」的短行，一眼看完整条闭环。

    注意：本代码库的 trace 里"工具调用"就是 role=tool 一条记录（args 与 result 同在一处），
    没有独立的 role=result 事件——所以 display 把 name(args) 和 → result 并在一行。最终答复
    用 ✅，超时用 ⏰。thinking/prompt 这类过程行省略（太长，只留结果型事件）。
    """
    icons = {"final_answer": "✅", "tool": "🔧", "timeout": "⏰", "assistant": "💬", "empty": "⚠️"}
    lines = []
    for ev in trace:
        role = ev.get("role")
        if role not in icons:
            continue
        if role == "tool":
            text = f"{ev.get('name')}({str(ev.get('args'))[:60]}) → {str(ev.get('result'))[:140]}"
        elif role in ("timeout", "assistant"):
            text = str(ev.get("result", ""))[:140]
        else:  # final_answer
            text = str(ev.get("args", ""))[:160]
        lines.append(f"  {icons[role]} step{ev.get('step', '?'):>2} [{role}] {text.replace(chr(10), ' ')}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="第11课 · 代码 Agent 闭环演示")
    parser.add_argument("--provider", choices=["mock", "openai", "openai-compatible", "anthropic"], default="mock")
    parser.add_argument("--model", default=None)
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument("--no-trace", action="store_true", help="不打印闭环轨迹")
    args = parser.parse_args()

    llm = build_llm(args.provider, args.model)
    agent = Agent(llm=llm, max_steps=40)   # 编码闭环通常几轮内；宽任务（如分析项目）留足余量

    print(f"任务：{args.task}\n")
    result = agent.run(args.task)

    print("\n" + "=" * 56)
    print("最终答复：")
    print(result)
    if not args.no_trace:
        print("\n" + "=" * 56)
        print("闭环轨迹：")
        print(render_trace(agent.trace))
        # 统计：真正发生过"跑 → 失败 → 改"吗？
        runs = [e for e in agent.trace if e.get("role") == "tool" and e.get("name") == "run_python"]
        if len(runs) >= 2:
            print(f"\n闭环证据：run_python 共执行 {len(runs)} 次（≥2 次 = 发生过 失败→修改→再跑）")
        else:
            print(f"\n闭环证据：run_python 共执行 {len(runs)} 次（首跑即过 = 一次写对，同样闭环）")


if __name__ == "__main__":
    main()
