from __future__ import annotations
import json
import time

from . import tools
from .llm import LLM
from .audit import AuditLogger

DEFAULT_SYSTEM_PROMPT = """你是一个小型自主智能体（Agent），你可以使用多个工具完成任务。

规则：
1. 只有工具能帮你完成任务时才调用工具；能直接回答就直接回答，不要滥用工具。
2. 一次可以调用多个工具；每个工具的结果会以 role=tool 的消息返回给你。
3. 复杂任务先在心里做一个简短计划，再开始调用工具。
4. 调用工具时，参数必须是合法 JSON。
5. 任务开始先用 list_dir/read_file 了解情况，最后一步必须调用 final_answer，禁止用纯文本回答。
6. 用中文回答用户，简洁、准确。
7. 涉及项目资料/文档/笔记时，先调用 kb_search 检索，回答时注明来源；检索不到就明说，不要编造。
8. 复杂任务：先输出一个简短计划（1~3 步），再按计划执行；每步先思考再行动，行动后观察结果并判断是否对。
9. 如果某步失败，分析原因并换一种方式重试，不要硬编或直接放弃。
10. 对写入/修改类操作，完成后用 read_file 或 run_shell 验证结果真的生效了，再调用 final_answer。
11. 短期上下文（history）是滑动窗口，只保留最近若干轮；重要事实/用户偏好请用 remember 存入长期记忆，需要时用 recall 检索。

工具选择表：
get_current_time：获取当前日期和时间；
calculator：计算一个数学表达式，例如 '2+3*4' 或 'sqrt(16)'；
list_dir：列出指定目录下的文件和子目录；
read_file：读取一个文本文件的内容；
write_file：把文本写入文件（会覆盖已有内容，自动创建父目录）；
remember：把一条信息写入长期记忆笔记，可加一个标签，用于跨会话记住用户偏好或事实；
recall：在长期记忆里搜索包含关键词的笔记；
run_shell：在白名单内执行一条系统命令并返回输出（不支持管道/重定向；用于查看目录、运行脚本、查版本等）；
final_answer：任务完成时调用它给出最终答复；把结果填进这些结构化字段；
kb_search：当问题涉及项目资料/文档/笔记时使用

"""


class Agent:
    """核心：把“大模型 + 工具 + 循环 + 记忆”串起来的主循环。"""

    def __init__(self, llm: LLM, max_steps: int = 12, max_context_messages: int = 20,
                 system_prompt: str = DEFAULT_SYSTEM_PROMPT,
                 allowed_tools: set[str] | None = None,
                 audit: AuditLogger | None = None, max_trace_chars: int = 300):
        self.llm = llm
        self.max_steps = max_steps
        self.max_context_messages = max_context_messages   # 短期上下文"滑动窗口"大小
        self.system_prompt = system_prompt
        # 工具白名单：None = 允许所有工具；传一个集合则只允许这些（权限最小化的雏形）
        self.allowed_tools = None if allowed_tools is None else set(allowed_tools)
        self.history: list[dict] = []   # 完整对话历史（内部保留，发送给模型时用窗口裁剪）
        self.audit = audit             # 审计日志器（可选）
        self.max_trace_chars = max_trace_chars
        self.trace: list[dict] = []    # 完整轨迹：每步工具调用/结果/耗时（审计&评测用）
        self.verbose = True
        self._warned_trim = False

    def _record_trace(self, event: dict):
        """把一步记进内嵌轨迹；若挂了审计器，也写入 JSONL 日志。"""
        event.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S"))
        self.trace.append(event)
        if self.audit:
            self.audit.log(event)

    def _messages(self) -> list[dict]:
        msgs = [{"role": "system", "content": self.system_prompt}]
        recent = list(self.history)
        if len(recent) > self.max_context_messages:
            recent = recent[-self.max_context_messages:]
            # 窗口开头若落在孤立的 tool 结果上，把它丢掉（它的 assistant 工具调用已被裁掉）
            while recent and recent[0]["role"] == "tool":
                recent.pop(0)
            if not self._warned_trim and self.verbose:
                print(f"  [memory] 短期上下文已裁剪为最近 {len(recent)} 条消息（滑动窗口）")
                self._warned_trim = True
        return msgs + recent

    def _run_tool_calls(self, tool_calls, step: int = 0):
        for call in tool_calls:
            name = call["function"]["name"]
            raw_args = call["function"]["arguments"]
            if self.verbose:
                print(f"  [tool] {name}({raw_args})")
            t0 = time.time()
            result = tools.execute_tool(name, raw_args)
            elapsed = round(time.time() - t0, 3)
            if self.verbose:
                print(f"  [result] {result[:200]}")
            self.history.append({"role": "tool", "tool_call_id": call["id"], "content": result})
            self._record_trace({
                "step": step + 1, "role": "tool", "name": name,
                "args": raw_args, "result": result[:self.max_trace_chars],
                "elapsed": elapsed,
            })

    def run(self, user_input: str | None = None, verbose: bool = True) -> str:
        self.verbose = verbose
        if user_input is not None:
            self.history.append({"role": "user", "content": user_input})

        tool_schemas = tools.get_tool_schemas()
        if self.allowed_tools is not None:
            tool_schemas = [s for s in tool_schemas if s["function"]["name"] in self.allowed_tools]
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
                        self._record_trace({
                            "step": step + 1, "role": "final_answer",
                            "name": "final_answer", "args": args,
                            "result": "structured output returned",
                        })
                        return json.dumps(args, ensure_ascii=False)   # 结构化结果就是最终答复

                message = {"role": "assistant", "content": response.get("content"),
                        "tool_calls": response["tool_calls"]}
                self.history.append(message)
                if response.get("content"):
                    print("  [reason]", response["content"][:120])
                self._run_tool_calls(response["tool_calls"], step)
                continue

            # 模型给出最终答复，结束循环
            content = response.get("content") or ""
            self.history.append({"role": "assistant", "content": content})
            self._record_trace({"step": step + 1, "role": "assistant", "name": "(text)",
                                "args": {}, "result": content[:self.max_trace_chars]})
            return content

        return "（已达到最大步数，任务未完成）"
