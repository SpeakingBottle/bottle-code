from __future__ import annotations
import json
import time
from typing import Generator, Literal, overload

from . import tools
from .llm import LLM
from .audit import AuditLogger
from .approval import Approver, AllowAllApprover

# 连续空响应上限：模型连返 N 次"无文本无工具"就中止任务，而不是静默重试直到 max_steps 耗尽
# （同上下文静默重试对确定性模型等于"原样复现"，上一轮空下一轮还空，会空转烧光步数）
MAX_EMPTY_RETRIES = 3

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
13. final_answer 的 summary 必须包含任务的实际成果（分析结论/关键发现/具体内容/数据），禁止只写"已完成/已了解/已分析"这类空话；任务要求分析时，把分析结果写进 summary 或 result。

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


def _result_ok(result: str) -> bool:
    """工具结果是否成功（不是 {"error": ...}）。

    read_file 成功时返回的是裸文本（不是 JSON），解析失败即视为成功——
    只有能解析成 dict 且带 "error" 键的才算失败。
    """
    s = result.lstrip()
    if not s.startswith("{"):
        return True
    try:
        return "error" not in json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return True


# 工具前置条件表：两道裁决都通过后、执行之前检查。
# 签名 (agent, args_dict) -> None；抛 ValueError 表示不满足（消息进 [PRECONDITION]）。
# 放在这里而不是工具函数里，是因为它依赖 Agent 的会话状态（见过哪些文件），
# 而工具函数是无状态、按名字调用的纯函数——和权限裁决同层，概念一致：
# 「这个调用允不允许」是 Agent 的判断，不是工具的判断。
def _require_read(agent: "Agent", args: dict) -> None:
    target = tools._safe_path(args["path"])
    if target not in agent._read_files:
        raise ValueError(f"修改前必须先 read_file 读取: {args.get('path')}")


_TOOL_PRECONDITIONS = {"edit_file": _require_read}


class Agent:
    """核心：把“大模型 + 工具 + 循环 + 记忆”串起来的主循环。"""

    def __init__(self, llm: LLM, max_steps: int = 24, max_context_messages: int = 20,
                 system_prompt: str = DEFAULT_SYSTEM_PROMPT,
                 allowed_tools: set[str] | None = None,
                 audit: AuditLogger | None = None, max_trace_chars: int = 300,
                 max_tool_result_chars: int = 2000,
                 approver: Approver | None = None):
        self.llm = llm
        self.max_steps = max_steps
        self.max_context_messages = max_context_messages   # 短期上下文"滑动窗口"大小
        self.system_prompt = system_prompt
        # 职责边界：None = 所有工具都在职责内；传一个集合则只允许这些。
        # 注意它只是"第一道裁决"——read 类工具会豁免（见 _adjudicate），
        # 不在集合里的 write/execute 才真的被拦。
        self.allowed_tools = None if allowed_tools is None else set(allowed_tools)
        # 审批者：write/execute 类操作放行与否由它裁决。不传 = AllowAll（与历史行为一致），
        # 但会记一条 auto-allowed 轨迹——让「默认放行」是个有记录的决定，而不是静默放行。
        self.approver = approver if approver is not None else AllowAllApprover()
        self._approver_explicit = approver is not None
        # 已「见过内容」的文件：read_file 读过、write_file 亲手写过。
        # edit_file 要求先见过内容才允许改（工具协议层面的「先观测再动手」）。
        self._read_files: set[str] = set()
        self.history: list[dict] = []   # 完整对话历史（内部保留，发送给模型时用窗口裁剪）
        self.audit = audit             # 可选审计器：挂了它，事件同时落盘 logs/agent.jsonl
        self.max_trace_chars = max_trace_chars  # 轨迹里结果截断上限（防膨胀 + 减敏感面）
        # 工具结果单独给更宽的上限：read_file/run_shell 的结果动辄几千字，
        # 300 字截断在轨迹面板里看不到内容（用户要求"记录工具结果"）。
        # 2000 字能看到大部分结果又不至于撑爆轨迹/落盘文件。
        self.max_tool_result_chars = max_tool_result_chars
        self.trace: list[dict] = []    # 内存轨迹：本次运行的完整时间线（调试/复盘用）
        self.verbose = True
        self._warned_trim = False
        self._anchor = None   # 本轮任务的用户问题：滑动窗口把它裁掉时重新钉回窗口最前（目标锚定）
        self._empty_streak = 0   # 连续空响应计数：达到 MAX_EMPTY_RETRIES 中止，防止空转烧步数

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
            # 目标锚定：超长任务（几十步）里滑动窗口会裁掉"本轮用户问题"，模型跑到一半
            # 会"忘了自己在干嘛"（实测回"没有收到具体任务指令"）。裁掉就把它钉回窗口最前；
            # 还在窗口里（短任务）则不动，避免重复注入。
            if self._anchor is not None and {"role": "user", "content": self._anchor} not in recent:
                recent.insert(0, {"role": "user", "content": self._anchor})
            if not self._warned_trim and self.verbose:
                print(f"  [memory] 短期上下文已裁剪为最近 {len(recent)} 条消息（滑动窗口）")
                self._warned_trim = True
        return msgs + recent

    def _adjudicate(self, name: str, raw_args: str, risk: str, step: int) -> str | None:
        """执行层裁决：返回 None = 放行；返回字符串 = 拒绝原因（已经是给人看的消息）。

        两道裁决的顺序不能反——先判「这活是不是我的」，再判「危不危险」。
        反过来的话，模型幻觉调用一个职责外的工具时会直接被送进审批
        （无人环境下默认放行），7A 挖的那个洞就回来了。
        """
        # ① 职责边界：allowed_tools 是硬边界。但 read 类工具豁免——读从不越权，
        #    而规则 10 要求「写入后自验证」，把 read_file 关掉会让模型没法自证。
        if (self.allowed_tools is not None
                and name not in self.allowed_tools
                and risk != tools.RISK_READ):
            return f"[SECURITY] 越权调用已拦截: {name}。允许的工具: {sorted(self.allowed_tools)}"

        # ② 风险分级：写/跑要过审批
        if risk in (tools.RISK_WRITE, tools.RISK_EXECUTE):
            approved = self.approver(name, raw_args, risk)
            label = getattr(self.approver, "label", type(self.approver).__name__)
            if approved:
                note = "批准" if self._approver_explicit else "auto-allowed（未配置审批者）"
            else:
                note = "拒绝"
            self._record_trace({
                "step": step + 1, "role": "approval", "name": name,
                "args": {"risk": risk, "approver": label}, "result": note,
            })
            if not approved:
                return f"[APPROVAL] 操作未获批准: {name}（risk={risk}）"

        # ③ 工具前置条件（如 edit_file 必须先 read_file）
        pre = _TOOL_PRECONDITIONS.get(name)
        if pre is not None:
            try:
                pre(self, json.loads(raw_args) if (raw_args or "").strip() else {})
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                return f"[PRECONDITION] {exc}"

        return None

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
            # —— 执行层裁决：职责边界 → 风险分级 → 前置条件（顺序见 _adjudicate）——
            risk = tools.get_risk(name)
            denial = self._adjudicate(name, raw_args, risk, step)
            if denial is not None:
                # 不执行！[SECURITY]/[APPROVAL]/[PRECONDITION] 稳定标记供审计与评测过滤
                result = json.dumps({"error": denial}, ensure_ascii=False)
            else:
                result = tools.execute_tool(name, raw_args)
            # 登记"已见过内容"：读过或亲手写过的文件，之后才允许 edit_file 修改。
            # write_file 也算——模型刚写下的就是它自己给的字符串，再要求"先读一遍"只会白烧步数；
            # 安全性由 edit_file 的逐字符匹配保证（记错了照样"未找到"）。
            if name in ("read_file", "write_file") and _result_ok(result):
                try:
                    _args = json.loads(raw_args) if (raw_args or "").strip() else {}
                    self._read_files.add(tools._safe_path(_args["path"]))
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    pass   # 拿不到 path 就不登记，不影响主流程
            results.append(result)
            elapsed = round(time.time() - t0, 3)
            if self.verbose and not stream:
                print(f"  [result] {result[:200]}")
            self.history.append({"role": "tool", "tool_call_id": call["id"], "content": result})
            # 记轨迹：结果截断到 max_tool_result_chars（工具结果给更宽上限，轨迹面板要能看到内容）；
            # args 保留原始 JSON 字符串（可重放）
            self._record_trace({
                "step": step + 1, "role": "tool", "name": name,
                "args": raw_args, "result": result[:self.max_tool_result_chars],
                "elapsed": elapsed,
            })
        return results

    @overload
    def run(self, user_input: str | None = None, verbose: bool = True, *, stream: Literal[True]) -> Generator[dict, None, str]: ...

    @overload
    def run(self, user_input: str | None = None, verbose: bool = True, *, stream: Literal[False] = False) -> str: ...

    def run(self, user_input: str | None = None, verbose: bool = True, stream: bool = False):
        """执行任务。

        stream=False（默认）：返回最终答复字符串（与之前完全一致）。
        stream=True：返回生成器，逐段 yield 事件（协议见 _run 的 docstring）；
        耗尽后 .value 是最终答复字符串。供网页版逐字展示 + 工具进度渲染。

        类型重载：不传 stream（或显式 False）时类型检查器认为返回 str；
        传 stream=True 时认为是 Generator——调用方不用再手动消歧。
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
        self._anchor = user_input   # 目标锚定：长任务里本轮用户问题可能被滑动窗口裁掉，用它兜底
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
                self._empty_streak = 0   # 有实际输出（工具调用），重置连续空响应计数
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

            # 空响应兜底：既无文字也无工具调用。两种情况：①思考块吃光输出预算（编码任务实测）
            # ②长会话后期模型偶发输出退化（服务端行为，无法完全控制）。绝不能把空串当"最终答复"
            # 交付，但要注意：同上下文静默重试对确定性模型等于"原样复现"（上一轮空下一轮还空），
            # 会空转烧光步数。所以空响应要 ①注入失败反馈改变上下文（打破复现）②限定连续空响应次数。
            if not response.get("content") and not response.get("tool_calls"):
                self._empty_streak += 1
                # 诊断信息：stop_reason 判断是 max_tokens 截断还是模型真没输出；usage 看输入规模
                diag = {
                    "stop_reason": response.get("stop_reason"),
                    "thinking_chars": len(response.get("thinking") or ""),
                    "usage": response.get("usage"),
                }
                if self._empty_streak >= MAX_EMPTY_RETRIES:
                    if verbose:
                        print(f"  [warn] 模型连续 {self._empty_streak} 次返回空响应（诊断: {diag}），任务中止")
                    self._record_trace({
                        "step": step + 1, "role": "empty", "name": "(model)",
                        "args": diag,
                        "result": f"连续 {self._empty_streak} 次空响应，达到上限，任务中止（不再空转消耗步数）",
                    })
                    return "（模型连续返回空响应，任务异常中止。可重试，或检查模型/上下文后再试）"
                # 失败反馈哲学：把"上一轮没输出"写回历史，改变模型下一轮的上下文，
                # 打破"同输入 → 同空响应"的确定性复现，给模型一个明确出路。
                hint = ("（上一轮没有任何输出。请继续：任务已完成就调用 final_answer；否则输出一行"
                        "简短文字说明进展，或调用一个工具推进。直接行动，不要只输出思考过程。）")
                self.history.append({"role": "user", "content": hint})
                if verbose:
                    print(f"  [warn] 模型返回空响应（诊断: {diag}），已注入反馈重试（连续第 {self._empty_streak} 次）")
                self._record_trace({
                    "step": step + 1, "role": "empty", "name": "(model)",
                    "args": diag, "result": "模型返回空响应，已注入反馈（提示直接行动）后重试",
                })
                continue
            self._empty_streak = 0   # 这轮有实际输出，重置连续空响应计数

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
