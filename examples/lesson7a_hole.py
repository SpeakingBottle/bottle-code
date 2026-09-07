"""第7课 · 7A 权限最小化 —— 漏洞演示（剧本 LLM）

角色设定：
  - 运营者意图：这个 Agent 只允许用 calculator 算数（+final_answer 收尾）。
  - 剧本模型：模拟"被 prompt 注入/输出污染"的 LLM，第一轮就故意报出
    一个【白名单外】的工具名字 write_file，试图写出 scratch/pwned.txt。

运行前结论（先跑一遍就明白了）：
  ❌ allowed_tools 只过滤了「提示层」（模型看不到别的工具），
     「执行层」收到谁的名字都照样放行 → 越权成功，pwned.txt 真被写出来。

修复方向（练习）：在 _run_tool_calls 执行前，先查 self.allowed_tools，
  越权调用直接返回"拒绝"，不再执行。

用法：在项目根目录运行  .venv/Scripts/python.exe examples/lesson7a_hole.py
"""

from __future__ import annotations

import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mini_agent.agent import Agent  # noqa: E402
from mini_agent.llm import LLM  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(REPO_ROOT, "scratch", "pwned.txt")


class EvilLLM(LLM):
    """剧本 LLM：模拟被劫持的模型，第一轮直接报白名单外的 write_file。"""

    def chat(self, messages, tools):
        last = messages[-1]
        # 还没执行过 → 恶意输出：无视白名单，直接报 write_file
        if last.get("role") != "tool":
            return {
                "role": "assistant",
                "content": "（恶意输出：无视白名单，我就是要调 write_file）",
                "tool_calls": [
                    {
                        "id": "evil_1",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps({
                                "path": "scratch/pwned.txt",
                                "content": "pwned",
                            }),
                        },
                    }
                ],
            }
        # 已经拿到工具结果（无论是"执行成功"还是"被拒绝"）→ final_answer 收尾
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "evil_2",
                    "type": "function",
                    "function": {
                        "name": "final_answer",
                        "arguments": json.dumps({
                            "summary": "越权尝试已结束，结果见工具返回值",
                            "plan": [],
                            "steps": ["尝试越权调用 write_file"],
                        }),
                    },
                }
            ],
        }


def main() -> int:
    # 清掉残留，保证可重复运行
    if os.path.isfile(TARGET):
        os.remove(TARGET)
    if os.path.isdir(os.path.dirname(TARGET)) and not os.listdir(os.path.dirname(TARGET)):
        os.rmdir(os.path.dirname(TARGET))

    print("运营者意图：这个 Agent 只准用 calculator（+final_answer 收尾）")
    print("剧本模型：第一轮就恶意报一个白名单外的工具 write_file，尝试写出 scratch/pwned.txt")
    print("=" * 56)

    agent = Agent(llm=EvilLLM(), allowed_tools={"calculator"})
    agent.run("帮我算 2+3")

    print("=" * 56)
    if os.path.isfile(TARGET):
        content = open(TARGET, encoding="utf-8").read()
        print(f"❌ 越权成功：scratch/pwned.txt 被写出来了（内容 {content!r}）")
        print("   漏洞确认：allowed_tools 只过滤了“提示层”，执行层对任何工具名都放行。")
        return 1
    print("✅ 越权被拒：scratch/pwned.txt 没有被创建，执行层白名单检查生效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
