"""审批者：把「危险操作要不要放行」从 Agent 核心里外置成一个可注入的回调。

为什么是回调而不是内置的交互逻辑？
  同一条裁决规则要跑在三种完全不同的环境里——
    CLI     有人，可以 stdin 交互        → TerminalApprover
    web     有界面但没有同步交互通道      → AllowAll / DenyAll（策略由启动参数定）
    评测/CI 没有人                      → AllowAll / DenyAll（显式声明）
  把「判断」留在 Agent、把「通道」交给调用方，核心里就没有 input() 这类环境假设。
"""

from __future__ import annotations

from typing import Protocol


class Approver(Protocol):
    """审批者：拿到「工具名 + 原始参数 + 风险等级」，回答批不批。"""

    label: str

    def __call__(self, name: str, args: str, risk: str) -> bool: ...


class AllowAllApprover:
    """全部批准。无人环境（评测/CI/演示）与「不启用审批」时的默认语义。"""

    label = "allow-all"

    def __call__(self, name: str, args: str, risk: str) -> bool:
        return True


class DenyAllApprover:
    """全部拒绝。严格模式：用来验证「危险操作真的被拦住了」。"""

    label = "deny-all"

    def __call__(self, name: str, args: str, risk: str) -> bool:
        return False


class TerminalApprover:
    """stdin 交互审批。

    输入：
      y = 批准这一次
      n = 拒绝这一次
      a = 本次会话内，同类风险等级全部批准（不必反复问）

    读不到输入（EOFError，例如被重定向/非交互运行）一律视为**拒绝**：
    不能因为"问不到人"就默认放行，那是 fail-open，比不问更糟。
    """

    label = "terminal"

    def __init__(self) -> None:
        self._always: set[str] = set()

    def __call__(self, name: str, args: str, risk: str) -> bool:
        if risk in self._always:
            return True
        try:
            answer = input(f"  [审批] {name}({args}) 风险={risk} —— 批准? [y/n/a] ").strip().lower()
        except EOFError:
            return False                      # fail-closed
        if answer == "a":
            self._always.add(risk)
            return True
        return answer == "y"
