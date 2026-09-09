"""第11课 · 练习11A —— 编码闭环评测器

核心思想：Agent 的"自测通过"不算数——评测器用自己手里的隐藏测试独立验证产物。
自测通过 ≠ 正确：测试即契约，契约以评测器为准。

两个场景：
  A. 斐波那契任务（隐藏测试用标准定义）→ 应 PASS
  B. "规定 fib(1)=5" 任务（Agent 按指令实现、自测全过；隐藏测试用标准定义）→ 应 FAIL
     —— 证明评价器不盲信 Agent 的"自测通过"

用法（在项目根目录运行）：
  .venv/Scripts/python.exe examples/lesson11_eval.py --provider anthropic
  .venv/Scripts/python.exe examples/lesson11_eval.py --provider anthropic --scenario B
  .venv/Scripts/python.exe examples/lesson11_eval.py --provider mock   # 冒烟
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

# 评测工作目录：Agent 的写文件 / run_python 都发生在这里。
# 必须在 import mini_agent（tools.py 读取 BASE_DIR）之前设置，否则不生效。
WORK = os.path.join(BASE, "examples", "_work", "eval")
os.makedirs(WORK, exist_ok=True)
os.environ["AGENT_WORKDIR"] = WORK

from mini_agent.main import _load_env  # noqa: E402
_load_env()

from mini_agent.agent import Agent  # noqa: E402
from mini_agent.llm import AnthropicLLM, MockLLM, OpenAIChatLLM  # noqa: E402

# ---------------------------------------------------------------------------
# 场景定义：任务（给 Agent 的提示词）+ 隐藏测试（评测器自己的判定标准）
# ---------------------------------------------------------------------------

FIB_TASK = (
    "这是一个编码任务：1) 写 fib.py，定义 fib(n) 返回斐波那契数列第 n 项"
    "（n 为非负整数，fib(0)=0, fib(1)=1）。"
    "2) 写 test_fib.py 用 assert 验证 fib(0)==0、fib(1)==1、fib(10)==55，"
    "全部通过时打印一行 ALL PASSED。"
    "3) 用 run_python 运行 test_fib.py，失败就根据报错修改直到 ALL PASSED。"
    "4) 全部通过后 final_answer 汇报。"
)

FIB_WRONG_TASK = (
    "这是一个编码任务：1) 写 fib.py，定义 fib(n) 返回斐波那契数列第 n 项。"
    "注意：本任务规定 fib(1)=5（这是任务要求，不是笔误）。"
    "2) 写 test_fib.py 用 assert 验证 fib(0)==0、fib(1)==5、fib(10)==55，"
    "全部通过时打印一行 ALL PASSED。"
    "3) 用 run_python 运行 test_fib.py，失败就根据报错修改直到 ALL PASSED。"
    "4) 全部通过后 final_answer 汇报。"
)

# 隐藏测试：评测器自己的契约，Agent 从头到尾看不到它
HIDDEN_TEST_FIB = """\
from fib import fib

# 评测器自己的契约：标准斐波那契定义
assert fib(0) == 0
assert fib(1) == 1
assert fib(10) == 55
assert fib(40) == 102334155
assert fib(45) == 1134903170

print("ALL PASSED")
"""

SCENARIOS = {
    "A": {"name": "fib 标准任务", "task": FIB_TASK, "hidden": HIDDEN_TEST_FIB, "expect": "PASS"},
    "B": {"name": "fib(1)=5 错误契约任务", "task": FIB_WRONG_TASK, "hidden": HIDDEN_TEST_FIB, "expect": "FAIL"},
}


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


def clean_workdir():
    """清空评测工作目录：上次场景的产物不能影响本次判定（两个场景都写 fib.py）。"""
    for name in os.listdir(WORK):
        p = os.path.join(WORK, name)
        if os.path.isfile(p):
            os.remove(p)
        else:
            shutil.rmtree(p)


def run_hidden_test(hidden_code: str) -> tuple[int, str]:
    """把隐藏测试写进工作目录并真实运行，返回 (exit_code, 输出)。

    用 subprocess 直接跑（不经过 Agent 的工具注册表）——评测器要独立于 Agent。
    """
    test_path = os.path.join(WORK, "_hidden_test.py")
    with open(test_path, "w", encoding="utf-8") as f:
        f.write(hidden_code)
    try:
        proc = subprocess.run(
            [sys.executable, test_path],
            cwd=WORK, shell=False, capture_output=True, text=True,
            timeout=30, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return 1, "隐藏测试超时（>30s）"
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def agent_self_tests(trace: list[dict]) -> list[str]:
    """从轨迹里提取 Agent 自己跑 run_python 的结果——它的"自测"长什么样。"""
    out = []
    for ev in trace:
        if ev.get("role") == "tool" and ev.get("name") == "run_python":
            try:
                r = json.loads(ev.get("result", "{}"))
                out.append(f"exit_code={r.get('exit_code')} ok={r.get('ok')}")
            except Exception:
                out.append(str(ev.get("result"))[:60])
    return out


def main():
    parser = argparse.ArgumentParser(description="第11课 · 编码闭环评测器")
    parser.add_argument("--provider", choices=["mock", "openai", "openai-compatible", "anthropic"], default="mock")
    parser.add_argument("--model", default=None)
    parser.add_argument("--scenario", choices=["A", "B", "all"], default="all")
    args = parser.parse_args()

    llm = build_llm(args.provider, args.model)
    keys = ["A", "B"] if args.scenario == "all" else [args.scenario]

    all_ok = True
    for key in keys:
        sc = SCENARIOS[key]
        print("\n" + "=" * 60)
        print(f"场景 {key}：{sc['name']}（预期 {sc['expect']}）")
        print("=" * 60)

        clean_workdir()   # 每个场景从干净目录开始
        agent = Agent(llm=llm, max_steps=24)
        result = agent.run(sc["task"])

        # 1) Agent 的自测（它自己写的测试，自己跑的）
        self_tests = agent_self_tests(agent.trace)
        print(f"\n[Agent 自测] {self_tests if self_tests else '（没有跑过 run_python）'}")

        # 2) 评测器的独立验证：隐藏测试
        rc, out = run_hidden_test(sc["hidden"])
        verdict = "PASS" if (rc == 0 and "ALL PASSED" in out) else "FAIL"
        match = "✓ 符合预期" if verdict == sc["expect"] else "✗ 与预期不符"
        print(f"[隐藏测试] exit_code={rc} → 判定 {verdict}  {match}")
        tail = out.strip().splitlines()[-3:]
        for line in tail:
            print(f"    {line[:120]}")

        # 3) Agent 的最终答复（截断，供对照）
        try:
            summary = json.loads(result).get("summary", result)
        except Exception:
            summary = result
        print(f"[Agent 自述] {str(summary)[:160]}")

        if verdict != sc["expect"]:
            all_ok = False

    print("\n" + "=" * 60)
    print("评测器结论：全部符合预期" if all_ok else "评测器结论：存在与预期不符的判定")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
