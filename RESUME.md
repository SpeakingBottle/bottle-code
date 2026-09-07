# 简历包装 —— 把项目翻译成简历语言

> 第8课 · 打磨的最后一环。项目本身已经能跑，这里教你**怎么把它讲给面试官听**。

## 一句话定位（电梯演讲）

> 从零手写了一个 **CodeOps Agent**：能读代码库、查知识库、多 Agent 分工、自动执行，并带权限控制与审计日志——不依赖 LangChain 等框架，核心循环全部手写。

## 技术栈（简历上这么写）

- **Python**：类型注解、装饰器、面向对象设计、`subprocess`/`asyncio` 进程管理
- **LLM 应用**：Function Calling、ReAct 循环、提示词工程、结构化输出
- **RAG**：文本切块、词频向量、余弦相似度检索
- **MCP**：Model Context Protocol 客户端/服务端（stdio + JSON-RPC）
- **可靠性**：权限最小化（白名单）、审计日志（append-only JSONL）、评测集（CI 可接入）

## 简历 Bullet（中文版，挑 3~4 条）

1. **手写 Agent 核心循环**：实现"模型→工具→观察→再想"的 ReAct 循环，支持多步工具调用、终止工具、滑动窗口短期记忆，不依赖 LangChain 等框架，代码量 < 200 行。
2. **多 Agent 协作框架**：设计规划者/执行者/评审者三角色分工，用结构化 JSON 消息协议传递任务与反馈，评审不通过自动带反馈重试。
3. **RAG 知识库问答**：实现最小版向量检索（切块 + 词频向量 + 余弦相似度），让 Agent 基于项目文档回答并注明来源，降低幻觉。
4. **MCP 协议接入**：手写 MCP stdio 客户端（JSON-RPC），把外部工具（代码统计/文件清单/git 状态）挂进 Agent，实现"加能力不改代码"。
5. **可靠性工程**：实现执行层工具白名单（越权调用拦截 + 审计事件）、append-only JSONL 审计日志、4 任务 × 5 维度的评测集（退出码可接入 CI 做回归）。

## 简历 Bullet（英文版）

1. Built a from-scratch AI Agent loop (ReAct: model → tool → observe → re-think) with multi-step tool calling, termination tools, and sliding-window short-term memory — no LangChain dependency, <200 LOC.
2. Designed a multi-agent orchestration framework (planner/executor/reviewer) with structured JSON message protocol and automatic retry on review failure.
3. Implemented a minimal RAG pipeline (chunking + TF vector + cosine similarity) enabling source-cited answers from project docs, reducing hallucination.
4. Wrote an MCP stdio client (JSON-RPC over subprocess) to mount external tools (code stats / file listing / git status) into the agent — adding capabilities without touching agent code.
5. Hardened the agent with an execution-layer tool whitelist (blocked calls logged as [SECURITY] events), append-only JSONL audit logging, and a 4-task × 5-dimension eval harness with CI-ready exit codes.

## 面试防身（大概率被问，先想好答案）

| 问题 | 你的答案要点 |
|---|---|
| 为什么不用 LangChain？ | 手写是为了理解核心循环；框架只是封装了"模型→工具→循环"。看懂底层，用框架才不慌。 |
| 权限控制怎么做的？ | 三层纵深：提示层软约束（模型看不到越权工具）+ 执行层硬裁决（白名单检查，越权不执行）+ 工具自带防御（路径沙箱/命令白名单）。 |
| 审计和日志有什么区别？ | 审计=证据：append-only、结构化、含失败事件；日志=调试：可丢可改。 |
| 评测集怎么设计的？ | 数据驱动：每个任务声明允许工具/必用工具/期望结果/泄密陷阱，5 个维度独立判定，退出码可进 CI。 |
| RAG 为什么用词频向量不用 embedding？ | 教学最小实现，零依赖可跑；生产换 embedding + 向量库即可，接口不变。 |
| MCP 是什么？ | 统一 LLM 应用接外部工具的协议（"给 AI 的 USB-C"），stdio 传输 + JSON-RPC，工具发现/调用标准化。 |
