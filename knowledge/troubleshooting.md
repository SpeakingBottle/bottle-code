# 常见问题排查

## 越权调用被拦截

现象：Agent 调用工具时返回 `[SECURITY] 越权调用已拦截`。
原因：执行层白名单检查生效——模型报出的工具不在 allowed_tools 里，直接拒绝执行。
处理：检查该角色的 allowed_tools 是否漏配；或让模型下一轮自纠（拒绝消息里带了允许列表）。

## 审计日志没写盘

现象：跑了 Agent 但 logs/agent.jsonl 没有新事件。
原因：AuditLogger 的 enabled=False，或 Agent 构造时没传 audit 参数。
处理：`Agent(llm, audit=AuditLogger())` 即可；enabled=False 用于评测等不想污染日志的场景。

## 评测任务失败

现象：eval_harness 里某个任务判定 ✗。
处理：看判定明细——expect 是结果不对，must_use 是没用对工具，no_abuse 是越权。
注意：权限最小化（allowed_tools 很小）和"写入后验证"的习惯可能冲突，这是设计张力，不是 bug。

## 知识库检索不到内容

现象：kb_search 返回空或无关结果。
处理：先跑 examples/build_kb.py 重建索引；确认 knowledge/ 下有 .md 文件；
如果用了 embedding 版，确认 chroma/ 目录存在且 build_index 成功。
