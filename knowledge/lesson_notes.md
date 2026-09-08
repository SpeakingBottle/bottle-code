# 课程笔记

## 第2课：最小闭环
实现了多工具串行任务，并新增 run_shell 工具（白名单沙箱，只允许只读检查命令）。

## 第3课：提示词工程
学习了系统提示词，并用 final_answer 做结构化输出（终止工具，防死循环）。

## 第4课：记忆 + RAG
短期记忆用滑动窗口（max_context_messages 裁剪历史）；长期记忆用 remember/recall 写笔记；
最小 RAG 用词频向量 + 余弦相似度检索知识库（knowledge.py）。

## 第5课：规划 + ReAct
系统提示词加计划字段（先输出 1~3 步计划再执行）；写入后必须用 read_file 自验证。

## 第6课：多 Agent + MCP
多 Agent 分工：规划者拆步、执行者动手、评审者验证，JSON 消息协议 + 重试；
MCP 协议接入外部工具（repo-stats server：count_loc / list_files / git_status）。

## 第7课：可靠性 + 评测
- 7A 权限最小化：执行层白名单检查，越权调用返回 [SECURITY] 拦截，不执行。
- 7B 审计与轨迹：append-only JSONL 审计日志 + 内存 trace，单一漏斗 _record_trace。
- 7C 评测集：4 个任务 × 5 维判定（expect / must_use / file / no_secret / no_abuse），退出码可进 CI。

## 第8课：整合 + 打磨
CodeOps Agent 合成层（codeops.py）：Orchestrator + MCP repo-stats + 审计接线成一个入口；
演示 codeops_demo.py 一个任务同时考验 MCP + RAG + 写文件 + 多 Agent + 审计。
