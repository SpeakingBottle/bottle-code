"""工具层补全 + 风险分级权限 —— 验收脚本

12 项边界，全部用剧本 LLM 驱动（确定性，不消耗真实 API）：

  ① read 豁免职责边界
  ② 职责外的 write 被拦且不执行
  ③ 审批拒绝 → 拦截且不执行，并记入审批轨迹
  ④ 审批批准 → 执行
  ⑤ 默认（未配置审批者）→ 放行但留痕
  ⑥ TerminalApprover：输入 y 批准 / 读不到输入 fail-closed
  ⑦ read 类工具不产生审批事件
  ⑧ 未读先改 → [PRECONDITION]
  ⑨ old_string 不唯一 → 拒绝并报出现次数
  ⑩ 先读后改 → 成功
  ⑪ grep 命中且行号与 read_file 同坐标系
  ⑫ grep 达上限提示 / read_file 首行总量告知

退出码 0 = 全部符合预期（可进 CI）。

用法：在项目根目录运行
  .venv/Scripts/python.exe examples/tooling_permissions_demo.py
"""

from __future__ import annotations

import json
import os
import sys
from unittest import mock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mini_agent import tools  # noqa: E402
from mini_agent.agent import Agent  # noqa: E402
from mini_agent.approval import AllowAllApprover, DenyAllApprover, TerminalApprover  # noqa: E402
from mini_agent.llm import LLM  # noqa: E402

WORK = "examples/_work"
TARGET = f"{WORK}/tc_target.txt"


class ScriptLLM(LLM):
    """剧本 LLM：按脚本依次报工具调用，脚本用完就 final_answer 收尾。"""

    def __init__(self, script: list[tuple[str, dict]]):
        self.script = list(script)
        self.i = 0

    def chat(self, messages, tools_):
        if self.i < len(self.script):
            name, args = self.script[self.i]
            self.i += 1
            call = {"id": f"c{self.i}", "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args)}}
        else:
            call = {"id": "fin", "type": "function",
                    "function": {"name": "final_answer",
                                 "arguments": json.dumps({"summary": "done", "plan": [], "steps": []})}}
        return {"role": "assistant", "content": None, "tool_calls": [call]}


def drive(script, allowed, approver=None):
    """跑一次剧本，返回 (最后一个工具结果, approval 事件列表, Agent)。"""
    a = Agent(ScriptLLM(script), allowed_tools=allowed, approver=approver)
    a.run("任务", verbose=False)
    tool_ev = [e for e in a.trace if e.get("role") == "tool"]
    appr_ev = [e for e in a.trace if e.get("role") == "approval"]
    return (tool_ev[-1]["result"] if tool_ev else ""), appr_ev, a


def clean():
    if os.path.isfile(TARGET):
        os.remove(TARGET)


def write_target(content):
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(content)


def read_target():
    return open(TARGET, encoding="utf-8").read()


def main() -> int:
    os.makedirs(WORK, exist_ok=True)
    checks: list[tuple[str, bool, str]] = []

    def check(label: str, ok: bool, detail: str = ""):
        checks.append((label, ok, detail))

    # ① read 豁免：read_file 不在职责工具集里，仍放行且真读到内容
    res, appr, _ = drive([("read_file", {"path": "README.md"})],
                         allowed={"write_file", "final_answer"})
    check("① read 类工具豁免职责边界", "[SECURITY]" not in res and "Bottle Code" in res, res[:80])

    # ② 职责边界：write_file 不在职责工具集里 → 拦下且不执行
    clean()
    res, _, _ = drive([("write_file", {"path": TARGET, "content": "x"})], allowed={"calculator"})
    check("② 职责外的 write 被拦且未执行",
          "[SECURITY]" in res and not os.path.isfile(TARGET), res[:80])

    # ③ 审批拒绝 → 拦截且不执行
    clean()
    res, appr, _ = drive([("write_file", {"path": TARGET, "content": "x"})],
                         allowed={"write_file", "final_answer"}, approver=DenyAllApprover())
    check("③ 审批拒绝时拦截且未执行",
          "[APPROVAL]" in res and not os.path.isfile(TARGET), res[:80])
    check("③b 拒绝也记入审批轨迹", bool(appr) and appr[0]["result"] == "拒绝", str(appr[:1]))

    # ④ 审批批准 → 执行
    clean()
    res, _, _ = drive([("write_file", {"path": TARGET, "content": "x"})],
                      allowed={"write_file", "final_answer"}, approver=AllowAllApprover())
    check("④ 审批批准后执行", os.path.isfile(TARGET) and "[APPROVAL]" not in res, res[:80])

    # ⑤ 默认（未配置审批者）→ 放行，但轨迹必须写明是自动放行
    clean()
    _, appr, _ = drive([("write_file", {"path": TARGET, "content": "y"})],
                       allowed={"write_file", "final_answer"})
    check("⑤ 默认放行但留痕",
          bool(appr) and appr[0]["result"] == "auto-allowed（未配置审批者）", str(appr[:1]))

    # ⑥ TerminalApprover 交互：y 批准 / EOF fail-closed
    clean()
    with mock.patch("builtins.input", return_value="y"):
        drive([("write_file", {"path": TARGET, "content": "z"})],
              allowed={"write_file", "final_answer"}, approver=TerminalApprover())
    check("⑥a 交互输入 y → 批准执行", os.path.isfile(TARGET))
    clean()
    with mock.patch("builtins.input", side_effect=EOFError):
        res, _, _ = drive([("write_file", {"path": TARGET, "content": "z"})],
                          allowed={"write_file", "final_answer"}, approver=TerminalApprover())
    check("⑥b 读不到输入 → fail-closed 拒绝",
          "[APPROVAL]" in res and not os.path.isfile(TARGET), res[:80])

    # ⑦ read 类工具不产生审批事件
    _, appr, _ = drive([("read_file", {"path": "README.md"})], allowed={"read_file"})
    check("⑦ read 不记审批轨迹", not appr)

    # ⑧ 未读先改 → [PRECONDITION]
    write_target("hello world\n")
    res, _, _ = drive([("edit_file", {"path": TARGET, "old_string": "hello", "new_string": "HI"})],
                      allowed={"edit_file", "final_answer"})
    check("⑧ 未读先改被拦",
          "[PRECONDITION]" in res and read_target() == "hello world\n", res[:80])

    # ⑨ old_string 不唯一 → 报错并带出现次数（同一 Agent 先读才能走到唯一性检查）
    write_target("dup\ndup\n")
    a = Agent(ScriptLLM([("read_file", {"path": TARGET}),
                         ("edit_file", {"path": TARGET, "old_string": "dup", "new_string": "x"})]),
              allowed_tools={"read_file", "edit_file", "final_answer"})
    a.run("任务", verbose=False)
    res = [e for e in a.trace if e.get("role") == "tool"][-1]["result"]
    check("⑨ old_string 不唯一时拒绝并报次数", "不唯一" in res and "2" in res, res[:100])

    # ⑩ 先读后改 → 成功
    write_target("hello world\n")
    a = Agent(ScriptLLM([("read_file", {"path": TARGET}),
                         ("edit_file", {"path": TARGET, "old_string": "hello", "new_string": "HI"})]),
              allowed_tools={"read_file", "edit_file", "final_answer"})
    a.run("任务", verbose=False)
    check("⑩ 先读后改成功", read_target() == "HI world\n", read_target()[:40])

    # ⑪ grep 命中 + 行号与 read_file 同坐标系
    out = tools.grep("def execute_tool", path="mini_agent", glob="*.py")
    ok = "tools.py:" in out
    if ok:
        lineno = int(out.split("tools.py:")[1].split(":")[0])
        ok = "def execute_tool" in tools.read_file("mini_agent/tools.py", offset=lineno, limit=1)
    check("⑪ grep 命中且行号可直接喂给 read_file", ok,
          out.splitlines()[0][:80] if out else "")

    # ⑫ grep 上限提示（不静默截断）+ read_file 总量告知
    g = tools.grep("def ", path="mini_agent", glob="*.py", max_results=3)
    r = tools.read_file("README.md", offset=5, limit=3)
    check("⑫a grep 达上限时提示还有更多", "上限" in g, g.splitlines()[-1][:80])
    check("⑫b read_file 首行告知总量与范围", r.splitlines()[0].endswith("行]"), r.splitlines()[0])

    clean()

    print("=" * 60)
    print("工具层补全 + 风险分级权限 · 验收")
    print("=" * 60)
    failed = 0
    for label, ok, detail in checks:
        print(f"  {'✅' if ok else '❌'} {label}")
        if not ok:
            failed += 1
            print(f"       实际: {detail}")
    print("-" * 60)
    print(f"通过: {len(checks) - failed}/{len(checks)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
