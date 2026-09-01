from __future__ import annotations

from . import tools
from .llm import LLM

DEFAULT_SYSTEM_PROMPT = """你是一个小型自主智能体（Agent），你可以使用多个工具完成任务。

规则：
1. 只有工具能帮你完成任务时才调用工具；能直接回答就直接回答，不要滥用工具。
2. 一次可以调用多个工具；每个工具的结果会以 role=tool 的消息返回给你。
3. 复杂任务先在心里做一个简短计划，再开始调用工具。
4. 调用工具时，参数必须是合法 JSON。
5. 用中文回答用户，简洁、准确。"""


class Agent:
    """核心：把“大模型 + 工具 + 循环 + 记忆”串起来的主循环。"""

    def __init__(self, llm: LLM, max_steps: int = 12, system_prompt: str = DEFAULT_SYSTEM_PROMPT):
        self.llm = llm
        self.max_steps = max_steps
        self.system_prompt = system_prompt
        self.history: list[dict] = []   # 短期记忆：完整对话上下文
        self.verbose = True

    def _messages(self) -> list[dict]:
        return [{"role": "system", "content": self.system_prompt}] + list(self.history)

    def _run_tool_calls(self, tool_calls):
        for call in tool_calls:
            name = call["function"]["name"]
            raw_args = call["function"]["arguments"]
            if self.verbose:
                print(f"  [tool] {name}({raw_args})")
            result = tools.execute_tool(name, raw_args)
            if self.verbose:
                print(f"  [result] {result[:200]}")
            self.history.append({"role": "tool", "tool_call_id": call["id"], "content": result})

    def run(self, user_input: str | None = None, verbose: bool = True) -> str:
        self.verbose = verbose
        if user_input is not None:
            self.history.append({"role": "user", "content": user_input})

        tool_schemas = tools.get_tool_schemas()
        for step in range(self.max_steps):
            if verbose:
                print(f"\n--- Step {step + 1} ---")
            response = self.llm.chat(self._messages(), tool_schemas)

            if response.get("tool_calls"):
                # 模型决定调用工具：把 assistant 的“调用意图”写进历史，然后执行
                message = {"role": "assistant", "content": response.get("content")}
                message["tool_calls"] = response["tool_calls"]
                self.history.append(message)
                self._run_tool_calls(response["tool_calls"])
                continue

            # 模型给出最终答复，结束循环
            content = response.get("content") or ""
            self.history.append({"role": "assistant", "content": content})
            return content

        return "（已达到最大步数，任务未完成）"
