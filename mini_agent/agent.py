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
12. 编码任务必须闭环：写完代码后用 run_python 运行测试脚本验证；失败/超时就根据报错修改实现再跑，直到通过为止——不要自认为写好了就交差，测试通过才算完成。

工具选择表：
get_current_time：获取当前日期和时间；
calculator：计算一个数学表达式，例如 '2+3*4' 或 'sqrt(16)'；
list_dir：列出指定目录下的文件和子目录；
read_file：读取一个文本文件的内容；
write_file：把文本写入文件（会覆盖已有内容，自动创建父目录）；
remember：把一条信息写入长期记忆笔记，可加一个标签，用于跨会话记住用户偏好或事实；
recall：在长期记忆里搜索包含关键词的笔记；
run_shell：在白名单内执行一条只读检查命令并返回输出（不支持管道/重定向；用于查看目录、查版本、git 状态等）；
final_answer：任务完成时调用它给出最终答复；把结果填进这些结构化字段；
kb_search：当问题涉及项目资料/文档/笔记时使用；
run_python：在项目沙箱内运行一个 Python 脚本并返回退出码与输出——写代码任务里用它跑测试/验证

"""


def _render_messages(msgs: list[dict], per_line: int = 140, cap: int = 2000) -> str:
    """把发给模型的消息渲染成可读的短行文本（轨迹里展示「提示词/上下文」用）。

    不存完整 JSON（臃肿、且带工具调用细节），每个消息取「角色 + 前 per_line 字符」，
    系统提示/工具结果这类长的截断，最后整体压到 cap 字符内——复盘时扫一眼"模型看到了什么"。
    """
    out = []
    for m in msgs:
        role = m.get("role")
        if role == "system":
            head = f"[system] {m.get('content', '')}"
        elif role == "tool":
            head = f"[tool:{str(m.get('tool_call_id', ''))[:12]}] {m.get('content', '')}"
        elif role == "assistant":
            content = m.get("content")
            if content:
                head = f"[assistant] {content}"
            else:
                names = ",".join(c["function"]["name"] for c in m.get("tool_calls", []))
                head = f"[assistant] <tool_calls: {names}>"
        else:
            head = f"[{role}] {m.get('content', '')}"
        out.append(head[:per_line] + ("…" if len(head) > per_line else ""))
    text = "\n".join(out)
    if len(text) > cap:
        text = text[:cap] + "\n…(截断)"
    return text


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
        self.audit = audit             # 可选审计器：挂了它，事件同时落盘 logs/agent.jsonl
        self.max_trace_chars = max_trace_chars  # 轨迹里结果截断上限（防膨胀 + 减敏感面）
        self.trace: list[dict] = []    # 内存轨迹：本次运行的完整时间线（调试/复盘用）
        self.verbose = True
        self._warned_trim = False

    def _record_trace(self, event: dict):
        """单一漏斗：所有事件先记进内存轨迹；若挂了审计器，再落盘 JSONL。

        事件字段约定：step / role / name / args / result / elapsed；
        ts（时间戳）在这里统一补，调用点不用关心。
        """
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

    def _run_tool_calls(self, tool_calls, step: int = 0, stream: bool = False) -> list[str]:
        """执行一批工具调用，返回每个调用的结果（流式模式下由 _run 广播成 result 事件）。

        stream=True 时抑制 verbose 打印：流式模式下 [tool]/[result] 由事件承载，
        再打印一遍会重复（调用方拿到事件自己渲染）。
        """
        results: list[str] = []
        for call in tool_calls:
            name = call["function"]["name"]
            raw_args = call["function"]["arguments"]
            if self.verbose and not stream:
                print(f"  [tool] {name}({raw_args})")
            t0 = time.time()   # 计时从"处理这个调用"开始：越权拒绝(不执行)也记一个近 0 的耗时
            # —— 权限检查：执行之前，先问一句"这个工具我有权调吗" ——
            if self.allowed_tools is not None and name not in self.allowed_tools:
                # 不执行！[SECURITY] 稳定标记供审计过滤；带上允许列表，让模型下一轮能自纠
                result = json.dumps({
                    "error": f"[SECURITY] 越权调用已拦截: {name}。允许的工具: {sorted(self.allowed_tools)}",
                }, ensure_ascii=False)
            else:
                result = tools.execute_tool(name, raw_args)
            results.append(result)
            elapsed = round(time.time() - t0, 3)
            if self.verbose and not stream:
                print(f"  [result] {result[:200]}")
            self.history.append({"role": "tool", "tool_call_id": call["id"], "content": result})
            # 记轨迹：结果截断到 max_trace_chars；args 保留原始 JSON 字符串（可重放）
            self._record_trace({
                "step": step + 1, "role": "tool", "name": name,
                "args": raw_args, "result": result[:self.max_trace_chars],
                "elapsed": elapsed,
            })
        return results

    def run(self, user_input: str | None = None, verbose: bool = True, stream: bool = False):
        """执行任务。

        stream=False（默认）：返回最终答复字符串（与之前完全一致）。
        stream=True：返回生成器，逐段 yield 事件（协议见 _run 的 docstring）；
        耗尽后 .value 是最终答复字符串。供网页版逐字展示 + 工具进度渲染。
        """
        if stream:
            return self._run(user_input, verbose, stream=True)
        gen = self._run(user_input, verbose, stream=False)
        try:
            while True:
                next(gen)   # 非流式：不转发增量，跑完即可
        except StopIteration as e:
            return e.value   # 生成器的 return 值 = 最终答复

    def _run(self, user_input, verbose, stream):
        """核心循环（生成器）。stream=True 时 yield 事件，最后 return 最终答复。

        流式事件协议（run(stream=True) yield 的每个 dict）：
          {"type": "delta", "text": str}     —— 文本增量（模型生成的内容）
          {"type": "tool", "name": str, "args": str}    —— 工具调用开始
          {"type": "result", "name": str, "text": str} —— 工具结果
        生成器 return 值 = 最终答复字符串（StopIteration.value）。

        流式与非流式共用这一个循环：唯一区别是调 chat_stream（yield 增量）
        还是 chat（一次性返回）。工具调用轮次不 yield 文本，行为与非流式一致。
        """
        self.verbose = verbose
        if user_input is not None:
            self.history.append({"role": "user", "content": user_input})

        tool_schemas = tools.get_tool_schemas()
        if self.allowed_tools is not None:
            tool_schemas = [s for s in tool_schemas if s["function"]["name"] in self.allowed_tools]
        step = 0   # 先给 step 一个初值：max_steps=0 时循环不执行，下面的 timeout 事件才不会 NameError
        for step in range(self.max_steps):
            if verbose:
                print(f"\n--- Step {step + 1} ---")
            # 这一轮发给模型的消息快照 = 「提示词/上下文」（system + 窗口切好的历史）。
            # 先记轨迹再发，复盘时能"按步骤对"——模型的每轮回答对应哪一批输入。
            msgs = self._messages()
            self._record_trace({
                "step": step + 1, "role": "prompt", "name": "(context)",
                "args": {"n_messages": len(msgs)},
                "result": _render_messages(msgs),
            })
            if stream:
                gen = self.llm.chat_stream(msgs, tool_schemas)
                try:
                    while True:
                        yield {"type": "delta", "text": next(gen)}   # 文本增量包成事件
                except StopIteration as e:
                    response = e.value   # 生成器 return 的完整消息（含 tool_calls）
            else:
                response = self.llm.chat(msgs, tool_schemas)

            # 模型的推理过程记入轨迹（「模型思考」）。只进轨迹供展示，不写回 history——
            # 否则触发 Anthropic"thinking 块必须带 signature"的校验（多轮工具循环会 400）。
            if response.get("thinking"):
                self._record_trace({
                    "step": step + 1, "role": "thinking", "name": "(reasoning)",
                    "args": {}, "result": response["thinking"][:self.max_trace_chars],
                })

            if response.get("tool_calls"):
                # 判断是否是"终止工具"
                for call in response["tool_calls"]:
                    if call["function"]["name"] == "final_answer":
                        args = json.loads(call["function"]["arguments"])
                        self._record_trace({
                            "step": step + 1, "role": "final_answer",
                            "name": "final_answer", "args": args,
                            "result": "结构化输出，run() 返回",
                        })
                        return json.dumps(args, ensure_ascii=False)   # 结构化结果就是最终答复

                message = {"role": "assistant", "content": response.get("content"),
                        "tool_calls": response["tool_calls"]}
                self.history.append(message)
                # 流式模式下推理文本已经 yield 给调用方了，这里不再重复打印
                if response.get("content") and not stream:
                    print("  [reason]", response["content"][:120])
                # 工具事件：执行前先广播"要调什么"，执行后再广播"结果是什么"
                if stream:
                    for call in response["tool_calls"]:
                        yield {"type": "tool", "name": call["function"]["name"],
                               "args": call["function"]["arguments"]}
                results = self._run_tool_calls(response["tool_calls"], step, stream=stream)
                if stream:
                    for call, result in zip(response["tool_calls"], results):
                        yield {"type": "result", "name": call["function"]["name"], "text": result}
                continue

            # 空响应兜底：既无文字也无工具调用（如思考块吃光输出预算）——绝不能把空串
            # 当"最终答复"交付，给模型重试一轮的机会（失败反馈哲学同样适用于调用本身）。
            if not response.get("content") and not response.get("tool_calls"):
                if verbose:
                    print("  [warn] 模型返回空响应（可能思考过长吃光输出预算），重试一轮")
                self._record_trace({
                    "step": step + 1, "role": "empty", "name": "(model)",
                    "args": {}, "result": "模型返回空响应（无文本无工具调用），本轮重试",
                })
                continue

            # 模型给出最终答复，结束循环
            content = response.get("content") or ""
            self.history.append({"role": "assistant", "content": content})
            self._record_trace({
                "step": step + 1, "role": "assistant", "name": "(text)",
                "args": {}, "result": content[:self.max_trace_chars],
            })
            return content

        self._record_trace({
            "step": step + 1, "role": "timeout", "name": "(max_steps)",
            "args": {}, "result": "达到最大步数，任务未完成",
        })
        return "（已达到最大步数，任务未完成）"
