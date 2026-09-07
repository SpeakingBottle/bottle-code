from __future__ import annotations

import json

from .agent import Agent
from .audit import AuditLogger
from .llm import LLM

# ---------------------------------------------------------------------------
# 各角色的系统提示词：多 Agent 分工的本质 = 给不同"工人"不同的人设 + 规则 + 工具
# ---------------------------------------------------------------------------

PLANNER_PROMPT = """你是「规划者」(Planner)，一个只负责把大目标拆成小步骤、不亲自执行任务的 Agent。

你对用户的任务做拆解，输出一份清晰可执行的步骤清单。
规则：
1. 不要执行任务，只做计划；但可以调用 read_file / list_dir / kb_search 了解背景。
2. 拆成 1~6 个具体、可直接执行的步骤。
3. 简单任务（如"算一个表达式"）给 1 步即可；复杂任务要合理分解。
4. 最后一步必须调用 final_answer：
   - 把步骤放进 steps[]；
   - 把给用户的一句话说明放进 summary。"""

EXECUTOR_PROMPT = """你是「执行者」(Executor)，负责真正把规划者给出的步骤做出来。

你会拿到一份计划，逐条执行，产出可验证的结果。
规则：
1. 需要真实能力时调用工具（calculator / read_file / write_file / list_dir / run_shell / kb_search）。
2. 每执行一步，先思考再行动，观察结果是否合理；出错就换一种方式重试，不要硬编。
3. 对写入/修改类操作，完成后要用 read_file 或 run_shell 验证真的生效了。
4. 最后一步必须调用 final_answer：
   - 把关键结果放进 result；
   - 把实际执行的步骤放进 steps[]；
   - 给用户的一句话总结放进 summary。"""

REVIEWER_PROMPT = """你是「评审者」(Reviewer)，负责检查执行者的结果是否真实、可信、符合任务要求。

你会收到"原始任务 + 执行结果"，只做审查，绝不动手改任何文件、不执行任何命令。
规则：
1. 判断结果是否回答了问题、有没有幻觉/矛盾/偷工减料/副作用。
2. 结果可信 → verdict=ok；有问题 → verdict=retry。
3. 无论哪种都要给 feedback：一句话说明哪里对、或哪里需要改。
4. 如果执行者声称写入了文件，你必须用 read_file 实际读取该文件，确认它真的存在、内容符合任务要求，再下 verdict——不能只信执行者自己报的 result。
5. 最后一步必须调用 final_answer：verdict 和 feedback 都要填，summary 写一句话结论。
"""


class RoleAgent(Agent):
    """多 Agent 里的一个"工人"：固定角色 + 受限工具集 + 独立历史。"""

    def __init__(self, llm: LLM, name: str, role_prompt: str,
                 allowed_tools: set[str], max_steps: int = 10,
                 audit: AuditLogger | None = None):
        # 任何角色都必须能调用 final_answer 来"收尾"，所以把它强制加进白名单
        super().__init__(llm, max_steps=max_steps, system_prompt=role_prompt,
                         allowed_tools=set(allowed_tools) | {"final_answer"},
                         audit=audit)
        self.name = name

    def __repr__(self):
        return f"<RoleAgent {self.name}>"


class Orchestrator:
    """把"规划者/执行者/评审者"三个角色协作起来，靠结构化 JSON 消息在角色之间传递结果。"""

    def __init__(self, llm: LLM, max_retries: int = 2, verbose: bool = True,
                 extra_executor_tools: set[str] | None = None,
                 audit: AuditLogger | None = None):
        self.llm = llm
        self.max_retries = max_retries   # 评审不通过时，最多让执行者重试几轮
        self.verbose = verbose

        # 分工设计：
        #   规划者 —— 只用"看"的工具（读文件/列目录/检索知识库），它不该改文件
        #   执行者 —— 能用"改/跑"的工具（计算/读写文件/跑白名单命令/检索）
        #   评审者 —— 不给任何工具，纯靠传入的消息做审查（最"干净"的角色）
        # 注入点：extra_executor_tools 让外部（如第8课 CodeOps）给执行者追加 MCP 工具；
        #         audit 让每个角色都挂上审计（第7课产物）。不传 = 行为与原来完全一致。
        executor_tools = {"calculator", "list_dir", "read_file", "write_file", "run_shell", "kb_search"}
        if extra_executor_tools:
            executor_tools |= set(extra_executor_tools)
        self.planner = RoleAgent(
            llm, "planner", PLANNER_PROMPT,
            {"list_dir", "read_file", "kb_search"}, audit=audit,
        )
        self.executor = RoleAgent(
            llm, "executor", EXECUTOR_PROMPT,
            executor_tools, audit=audit,
        )
        self.reviewer = RoleAgent(
            llm, "reviewer", REVIEWER_PROMPT,
            {"read_file", "list_dir"}, audit=audit,  # 只读
        )

    def _parse(self, raw: str) -> dict:
        """把 Agent 返回的 final_answer JSON 字符串变成 dict；解析失败给个兜底。"""
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"summary": raw, "steps": [], "used_tools": []}

    def run(self, task: str) -> dict:
        _log = (lambda *a: print(*a)) if self.verbose else (lambda *a: None)

        # 1) 规划：先让规划者把大任务拆成步骤
        _log("=== \U0001f9ed 规划者 ===")
        plan_msg = self._parse(self.planner.run(task))
        steps = plan_msg.get("steps") or [task]
        _log(f"计划步骤（{len(steps)} 步）:")
        for i, s in enumerate(steps, 1):
            _log(f"  {i}. {s}")

        # 2) 执行 + 3) 评审：执行者做，评审者看，不通过就带反馈重试
        last_feedback = None
        review_msg = {}
        for attempt in range(self.max_retries + 1):
            _log(f"\n=== ⚙️ 执行者（第 {attempt + 1} 轮）===")
            plan_text = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
            prompt = f"任务：{task}\n计划步骤：\n{plan_text}"
            if last_feedback:
                prompt += f"\n\n[上一轮评审反馈，请据此修改]：{last_feedback}"
            exec_msg = self._parse(self.executor.run(prompt))
            _log(f"执行结果: {exec_msg.get('result')}")

            _log("=== \U0001f50d 评审者 ===")
            review_msg = self._parse(self.reviewer.run(
                f"原始任务：{task}\n执行结果：\n" + json.dumps(exec_msg, ensure_ascii=False, indent=2)
            ))
            verdict = review_msg.get("verdict") or "ok"
            feedback = review_msg.get("feedback") or ""
            _log(f"评审: {verdict} — {feedback}")

            if verdict == "ok":
                return {"task": task, "steps": steps, "execution": exec_msg,
                        "review": review_msg, "status": "ok"}
            last_feedback = feedback

        return {"task": task, "steps": steps, "status": "failed",
                "review": review_msg,
                "note": "评审多次未通过，已放弃（可调大 max_retries）"}
