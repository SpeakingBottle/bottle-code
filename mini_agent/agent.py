from __future__ import annotations
import json

from . import tools
from .llm import LLM

DEFAULT_SYSTEM_PROMPT = """你是一个小型自主智能体（Agent），你可以使用多个工具完成任务。

规则：
1. 只有工具能帮你完成任务时才调用工具；能直接回答就直接回答，不要滥用工具。
2. 一次可以调用多个工具；每个工具的结果会以 role=tool 的消息返回给你。
3. 复杂任务先在心里做一个简短计划，再开始调用工具。
4. 调用工具时，参数必须是合法 JSON。
5. 任务开始先用 list_dir/read_file 了解情况，最后一步必须调用 final_answer，禁止用纯文本回答。
6. 用中文回答用户，简洁、准确。

工具选择表：
get_current_time：获取当前日期和时间；
calculator：计算一个数学表达式，例如 '2+3*4' 或 'sqrt(16)'；
list_dir：列出指定目录下的文件和子目录；
read_file：读取一个文本文件的内容；
write_file：把文本写入文件（会覆盖已有内容，自动创建父目录）；
remember：把一条信息写入长期记忆笔记，可加一个标签，用于跨会话记住用户偏好或事实；
recall：在长期记忆里搜索包含关键词的笔记；
run_shell：在白名单内执行一条系统命令并返回输出（不支持管道/重定向；用于查看目录、运行脚本、查版本等）；
final_answer：任务完成时调用它给出最终答复；把结果填进这些结构化字段

"""


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

            # 在 run() 的循环里，处理 tool_calls 之前加：
            if response.get("tool_calls"):
                # 判断是否是"终止工具"
                for call in response["tool_calls"]:
                    if call["function"]["name"] == "final_answer":
                        args = json.loads(call["function"]["arguments"])
                        return json.dumps(args, ensure_ascii=False)   # 结构化结果就是最终答复

                message = {"role": "assistant", "content": response.get("content"),
                        "tool_calls": response["tool_calls"]}
                self.history.append(message)
                self._run_tool_calls(response["tool_calls"])
                continue

            # 模型给出最终答复，结束循环
            content = response.get("content") or ""
            self.history.append({"role": "assistant", "content": content})
            return content

        return "（已达到最大步数，任务未完成）"
