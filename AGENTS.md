# AGENTS.md — AI Agent 教学项目

本文件记录这轮「AI Agent 教学」的**教学约定**、**项目现状**与**学习进度**。
任何一次会话（包括未来的新会话）都以此文件为准，先读它再继续教学。

---

## 学习者画像

- 计算机科学与技术专业 大三
- 已有 Web 开发经验（Vue + SpringBoot）
- 熟练使用 Claude Code 进行 vibe coding，熟悉 skill / prompt / tool 等概念
- 语言主线：**Python**
- 模型：**接真实 API**（Anthropic Messages API 格式，当前用 Ollama 云，模型 `deepseek-v4-flash:0731`，与 Claude Code 会话同源；`llm.py` 同时保留 OpenAI 兼容后端）
- 时间投入：**冲刺型**（每周 >=6h）
- 目标：做出一个**完整、可运行、可展示的 Agent 作品**（重在把八课知识真正合体）
- 感兴趣主题：**知识库问答（RAG）/ 多 Agent 协作 / 代码与运维自动化**
- 最终作品方向：**CodeOps Agent**（读代码库 + 查知识库 + 多 Agent 分工 + 自动执行）

---

## 教学方式（已确认）

采用「**讲 → 做 → 查 → 复盘**」四步闭环：

### 1. 讲
- 我先讲**概念 + 最小可运行示例**，并逐行解释"为什么这么做"。
- 不堆砌理论，每一项都要能直接跑起来看。

### 2. 做
- 布置一个与示例**同构但不同题**的练习，附**明确验收标准**。

### 3. 查
- 我**实际运行**学习者的代码，反馈分三档：
  - ✅ **对了**：确认思路，指出可复用点
  - 🔧 **优化**：更稳 / 更简洁 / 更符合惯例的做法 + 理由
  - 🐛 **Bug**：定位根因，讲清"为什么 + 怎么改 + 下次怎么避免"

### 4. 复盘
- 追问一句"为什么这样写 / 换个场景会怎样"，把技巧沉淀成可迁移的心智模型。

---

## 工作约定（git）

- **每次变更后自动提交**：每完成一个有意义的变更（新功能 / 修复 / 文档更新 / 清理），自动执行 `git add` + `git commit`，不要堆积改动。
- 提交信息用**中文**，遵循 conventional commits 前缀（`feat:` / `fix:` / `refactor:` / `docs:` / `chore:`），正文简述改了什么、为什么。
- `.githooks/pre-commit` 会自动跑密钥扫描：若扫描失败，先定位并修复再提交，不要 `--no-verify` 跳过。

---

## 练习验收标准模板

```
任务：<一句话说清要做什么>
验收标准
- 功能：给定 <输入>，应产出 <可观察结果>
- 边界：当 <异常情况> 时，应 <正确处理>
- 约束：<不许做的事 / 必须做的事>
- 合格：<我如何验证，例如运行后能看到 X>
```

---

## 项目现状（仓库里现在有什么）

- **Agent 主循环**：`mini_agent/agent.py`（工具调用 + 终止工具 + 计划字段 + ReAct 规则）
- **工具**（`mini_agent/tools.py`）：`calculator` / `list_dir` / `read_file` / `write_file` / `remember` / `recall` / `run_shell`（只读检查白名单）/ `final_answer`（终止工具，结构化输出）/ `kb_search`（RAG 检索）
- **短期记忆**：`Agent.history` + 滑动窗口（`max_context_messages`），长对话裁成最近 N 条
- **长期记忆**：`remember`/`recall`（`memory/notebook.md`）+ `kb_search`（`knowledge/` 向量检索）
- **最小 RAG**：`mini_agent/knowledge.py`（切块 + 词频向量 + 余弦相似度）+ `examples/build_kb.py`（建索引）
- **多 Agent 分工**：`mini_agent/roles.py`（`RoleAgent` = 复用 Agent + 角色人设 + 受限工具集；`Orchestrator` = 规划者/执行者/评审者 + JSON 消息协议 + 重试）+ `examples/multi_agent_demo.py`
- **MCP 接入**：`mini_agent/mcp_client.py`（同步 stdio 客户端适配器，把外部 MCP 工具翻译成 Agent 的 `Tool`）+ `examples/mcp_server.py`（自定义 MCP server，`repo-stats`：count_loc / list_files / git_status）+ `examples/mcp_demo.py`；依赖 `mcp>=1.0.0`
- **模型后端**：`mini_agent/llm.py`（OpenAI 兼容 + Anthropic Messages API + 超时/重试 + `MockLLM`）
- **防护**：`.githooks/pre-commit` + `scripts/check_secrets.py`（提交前扫密钥）
- **知识库**：`knowledge/project.md`、`knowledge/lesson_notes.md`（索引 `knowledge/index.json` 已 gitignore）

---

## 课程表

| 课程 | 主题 | 核心产出 |
|---|---|---|
| 第1课 | 心智模型 + 环境准备 | 配好 Python 环境、接通真实 API、看懂 Agent 五大要素 |
| 第2课 | 最小闭环 | 手写"模型→工具→观察→再想"循环；加读/写/跑命令工具 |
| 第3课 | 提示词工程 | 工具选择表 + final_answer 终止工具 + 结构化输出 + 抗幻觉自纠 |
| 第4课 | 记忆 + RAG | 短期上下文滑动窗口 + 长期记忆(remember/recall) + 最小向量检索(kb_search/build_kb) |
| 第5课 | 规划 + ReAct | 计划字段 + ReAct 规则 + 思考可见 + 写入后自验证 |
| 第6课 | 多 Agent + MCP | 规划者/执行者/评审者分工 + 接入/编写自定义 MCP |
| 第7课 | 可靠性 + 评测 | 权限最小化、沙箱、审计日志、轨迹观测、任务评测集 |
| 第8课 | 整合 + 打磨 | 合成 CodeOps Agent：合成层、演示、README、作品收尾 |
| 第9课 | 生产级 RAG | embedding 向量化 + 向量库(Chroma) + 混合检索(BM25+向量 RRF) + 检索评估(hit@k) |
| 第10课 | CodeOps 网页版 | 流式输出 + FastAPI 后端 + Vue 前端，把 CodeOps Agent 变成可交互网页 |
| 第11课 | 代码 Agent 闭环 | 写代码 → 跑测试 → 改，让 Agent 自主完成编码任务闭环 |

---

## 学习进度

- 当前课程：**第10课（CodeOps 网页版）**（进行中）—— 8 课主线已完成，进入第9~11课进阶阶段
  - 进阶路线（已确认，三合一，即第9~11课）：第9课 生产级 RAG（embedding + 向量库 + 混合检索 + 检索评估）→ 第10课 CodeOps 网页版（流式 + FastAPI + Vue）→ 第11课 代码 Agent 闭环（写代码→跑测试→改）
  - **10A 流式输出** ✅：`llm.py` 加 `chat_stream()`（OpenAI/Anthropic/Mock 三后端：yield 文本增量 + return 完整消息，工具调用轮次不 yield 文本）；`agent.py` 的 `run()` 加 `stream=True`（生成器逐段 yield 增量，`StopIteration.value` 拿最终答复，非流式行为不变）；`examples/stream_demo.py`（mock 打字机效果；真实 API 验证：纯文本流式 + final_answer 结构化收尾都正常）
  - **练习10A 流式事件协议** ✅：`run(stream=True)` 从 yield 裸文本升级为 yield 统一 dict 事件——`{"type":"delta","text":...}` 文本增量 / `{"type":"tool","name","args"}` 工具调用开始 / `{"type":"result","name","text"}` 工具结果，生成器 return 值 = 最终答复；`_run_tool_calls` 返回结果列表 + `stream` 参数（流式下抑制 verbose 重复打印，事件承载展示）；`stream_demo.py` 按事件类型渲染（工具进度在文本前出现）；验收：mock 工具事件先于文本 ✅、纯文本回答无工具事件 ✅、不改 llm.py ✅、非流式回归（mock_demo/eval_harness 1/4）✅、真实 API 验证 calculator 事件 + final_answer 结构化收尾 ✅
  - **10B FastAPI 后端（SSE 流式接口）** ✅：`web/server.py`（`POST /api/chat` 把 `run(stream=True)` 的事件逐个转成 SSE `data: {json}\n\n`，补发 `done`（最终答复，从 StopIteration.value 拿）/`error` 事件；`history` 字段支持多轮上下文，只收 user/assistant 文本；CORS 放开跨域；`GET /test.html` 服务浏览器测试页）；`web/test.html`（fetch + ReadableStream 消费 SSE——EventSource 不支持 POST，这是 10C Vue 前端要用的消费方式）；requirements.txt 加 fastapi/uvicorn；验收：curl mock/真实 API 事件流 tool→result→delta→done 顺序正确、history 多轮生效、浏览器全链路渲染成功（截图 web-test.png）
  - **练习10B 会话记忆** ✅：`ChatRequest` 加 `session_id`——命中复用 `sessions` dict 里的 Agent 实例（history 跨请求保留），未命中新建并存入，不传则保持无状态；`GET /api/sessions` 调试端点（看每个会话的上下文长度，mock 不真推理、靠 history 长度验证机制）；验收：mock 同会话 history 增长/异会话隔离/无状态不入库 ✅、真实 API 两轮对话正确答出 42 ✅；已知代价：dict 无限增长 + 并发写 history 竞争，生产要换 Redis/加过期/加锁
  - **10C Vue 前端（聊天页面）** ✅：`web/` 完整的 Vite + Vue 3 `<script setup>` 工程（package.json / vite.config.js 代理 /api → :8000、index.html 内联 SVG favicon）；`src/App.vue`（fetch + ReadableStream 消费 SSE，`reactive` 包裹 assistant 消息避免流式文本静默丢失，deep watch 自动滚底，session_id 存 localStorage 刷新续会）；`src/components/ChatMessage.vue`（工具事件渲染成终端日志行：左语义色边条 + 等宽字体，❯=tool 琥珀 / →=result 绿）；`src/components/ChatInput.vue`（回车/按钮发送，生成中禁用）；深色终端风（`style.css` 全局 CSS token：青=用户 / 琥珀=tool / 绿=result / 红=error，颜色即信息类型）
  - **10C 刷新恢复历史** ✅：`GET /api/sessions/{sid}/history` 读 `chat_logs`（server 层新加的展示用对话记录：user 提问 + 最终答复成对，done 事件时写入）；`App.vue` 挂载时按 localStorage 的 session_id 拉历史渲染。**架构认知**：`Agent.history` 是「模型上下文」不是「人看的对话记录」——含 tool_calls/content=null 的工具轮、final_answer 直接 return 不写回最终答复，不能直接当历史返回；展示记录与模型上下文分离（chat_logs vs history）。验收：mock/真实 API 双跑 calculator 链路 ✅、刷新后历史恢复（工具事件不恢复=设计）、`reactive` 坑验证、无状态不写 chat_logs、后端重启后旧 session_id 返回空列表分支、vite build 通过、截图 web-10c-chat.png（深色终端风）；模型不支持图片输入，全程文本式验证（Playwright 快照/DOM）未喂图给模型
- 已完成：
  - 第1课：真实 API 接通（DeepSeek 兼容）
  - 第2课：多步串行 + run_shell 白名单沙箱
  - 第3课：final_answer 终止工具 + 结构化输出 + API 超时/重试
  - 第4课：短期上下文滑动窗口 + 长期记忆(remember/recall) + 最小 RAG(kb_search/knowledge.py)
  - 第5课：计划字段 + ReAct 规则 + 思考可见 + 写入后自验证
  - 第6课：多 Agent 分工（规划者/执行者/评审者 + JSON 消息协议 + 白名单工具）+ MCP 接入（自定义 server `repo-stats` + 客户端适配器）+ 练习6b（给 server 新增 `git_status` 只读工具）
  - 第7课：可靠性 + 评测（三关重做）
    - **7A 权限最小化** ✅：`mini_agent/agent.py` 的 `_run_tool_calls` 加执行层白名单检查——越权调用不执行，返回 `[SECURITY] 越权调用已拦截 + 允许列表` 并回填 history（同一 tool_call_id）；`examples/lesson7a_hole.py`（剧本 LLM 报白名单外 write_file）验证"越权成功"→"越权被拒"，None/白名单内/默认/越权 四项边界全过；复盘确认三层纵深（提示层软约束 + 执行层硬裁决 + 工具自带防御），`final_answer` 是无条件逃生门（零副作用+防死循环）
    - **7B 审计与轨迹** ✅：`mini_agent/audit.py`（AuditLogger append-only JSONL + format_trace 轨迹渲染）+ `agent.py` 加 `_record_trace` 单一漏斗（内存 trace + 可选落盘）、`_run_tool_calls` 计时/结果截断/越权事件记录、`run()` 记录 final_answer/纯文本/timeout；`logs/` 已 gitignore；验收：trace 与 `logs/agent.jsonl` 对应、越权 [SECURITY] 事件进审计、audit=None/enabled=False 不写盘、结果截断到 max_trace_chars=300；复盘确认"审计=证据(append-only/结构化/完整含失败) vs 日志=调试(可丢可改)"、"截断结果+保留 args 可重放"
    - **7C 评测集** ✅：`examples/eval_harness.py`（4 个任务：calc / read_readme / write_verify / no_leak，数据驱动 TASKS + 5 维判定 expect/must_use/file/no_secret/no_abuse + 退出码 0/1 可进 CI）；mock 1/4（正确暴露 mock 能力边界）、真实 API 3/4；no_leak 失败复盘：模型想用 read_file 验证写入被 7A 拦截（最小权限集 {write_file, final_answer}）→ 权限最小化 vs 验证习惯的设计张力；修复两处 Pylance 报错（agent.py `step` 未绑定真 bug：max_steps=0 时 NameError，循环前 `step=0` 修复；eval_harness/lesson7a_hole 的 `reconfigure` 类型误报，`# type: ignore[attr-defined]` 消除）
  - 第8课：整合 + 打磨（CodeOps Agent 合成层 / 演示 / README / 作品收尾）
    - **8A 合成层** ✅：`mini_agent/codeops.py`（CodeOpsAgent = Orchestrator + MCP repo-stats + 审计，~50 行纯接线）；`roles.py` 加向后兼容注入点（RoleAgent/Orchestrator 透传 `audit`、Orchestrator 支持 `extra_executor_tools`）；真实 API 演示通过：mcp_count_loc 统计 10 文件 1201 行 + kb_search 查部署步骤 + 写出 results/deploy_steps.md（内容准确非编造）+ 评审通过 + 42 条审计事件落盘；mock 回归 + multi_agent_demo 回归通过
    - **8B 演示** ✅：`examples/codeops_demo.py`（一个任务同时考验 MCP + RAG + 写文件 + 多Agent + 审计）
    - **8C 打磨** ✅：README 更新（目录结构 + CodeOps 章节 + 进阶能力表）
  - 第9课：生产级 RAG（embedding + 向量库 + 混合检索 + 检索评估）
    - **9A embedding + 向量库** ✅：`mini_agent/knowledge_embed.py`（fastembed `BAAI/bge-small-zh-v1.5` + Chroma PersistentClient，接口与 knowledge.py 一致）；`tools.py` kb_search 优先 embedding 版、缺依赖回退词频版
    - **9B 混合检索** ✅：手写 BM25 + 向量 RRF 排名融合（`use_hybrid=False` 可退化为纯向量）
    - **9C 检索评估** ✅：`examples/rag_eval.py`（8 查询 × hit@3，对比三方案）；知识库补全（project.md 加部署步骤、lesson_notes.md 补第4~8课笔记、新增 architecture.md / troubleshooting.md）
    - **9D 查** ✅：混合版 100% > 词频版 88% = embedding 版 88%；评测逮住两个坏评测项（project.md 无部署内容、lesson_notes.md 无第7课内容）——评测逼你验证对数据的假设；语义改写查询"怎么把服务跑起来"是 embedding 的强项（词频版唯一挂掉的一条）
    - 复盘：待做
- 环境：Python 3.13 虚拟环境 `.venv`；运行激活 venv 或用 `.venv/Scripts/python.exe`；真实 key 在本地 `.env`（已 gitignore）
- 待补/备注（整理阶段已处理）：
  - ✅ `run_shell` 白名单已移除 python/py/node（`python -c` = 任意代码执行），只留只读检查命令（git/ls/cat/wc/findstr/where）；7A 已解决"工具层"白名单强制执行；命令级剩余限制（cat 读任意文件 / git 仓库操作）仍开放，属更深的命令级沙箱，可留给第8课整合或后续加强

---

## 相关文件

- `README.md` —— 项目说明与上手教程
- `AGENTS.md` —— 本文件，教学约定 + 项目现状 + 进度（每次会话先读）
- `mini_agent/` —— 核心：`agent.py`(主循环) `tools.py`(工具) `llm.py`(模型后端) `knowledge.py`(最小RAG) `knowledge_embed.py`(第9课 embedding版RAG) `roles.py`(多Agent分工) `mcp_client.py`(MCP客户端适配器) `main.py`(CLI)
- `knowledge/` —— 知识库文档（project.md / lesson_notes.md / architecture.md / troubleshooting.md），索引 index.json 已 gitignore
- `examples/` —— `mock_demo.py`(离线演示) / `build_kb.py`(建索引) / `multi_agent_demo.py`(多Agent演示) / `mcp_server.py`(自定义MCP server) / `mcp_demo.py`(MCP接入演示) / `rag_eval.py`(第9课检索评估)
- `scripts/` + `.githooks/` —— 敏感信息检查与提交前钩子
