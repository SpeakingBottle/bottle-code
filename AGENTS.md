# AGENTS.md — AI Agent 教学项目

本文件记录这轮「AI Agent 教学」的**教学约定**、**项目现状**与**学习进度**。
任何一次会话（包括未来的新会话）都以此文件为准，先读它再继续教学。

---

## 学习者画像

- 计算机科学与技术专业 大三
- 已有 Web 开发经验（Vue + SpringBoot）
- 熟练使用 Claude Code 进行 vibe coding，熟悉 skill / prompt / tool 等概念
- 语言主线：**Python**
- 模型：**接真实 API**（OpenAI 兼容接口，当前用 DeepSeek）
- 时间投入：**冲刺型**（每周 >=6h）
- 目标：做出**能写进简历的作品**
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
- **工具**（`mini_agent/tools.py`）：`calculator` / `list_dir` / `read_file` / `write_file` / `remember` / `recall` / `run_shell`（白名单沙箱）/ `final_answer`（终止工具，结构化输出）/ `kb_search`（RAG 检索）
- **短期记忆**：`Agent.history` + 滑动窗口（`max_context_messages`），长对话裁成最近 N 条
- **长期记忆**：`remember`/`recall`（`memory/notebook.md`）+ `kb_search`（`knowledge/` 向量检索）
- **最小 RAG**：`mini_agent/knowledge.py`（切块 + 词频向量 + 余弦相似度）+ `examples/build_kb.py`（建索引）
- **多 Agent 分工**：`mini_agent/roles.py`（`RoleAgent` = 复用 Agent + 角色人设 + 受限工具集；`Orchestrator` = 规划者/执行者/评审者 + JSON 消息协议 + 重试）+ `examples/multi_agent_demo.py`
- **MCP 接入**：`mini_agent/mcp_client.py`（同步 stdio 客户端适配器，把外部 MCP 工具翻译成 Agent 的 `Tool`）+ `examples/mcp_server.py`（自定义 MCP server，`repo-stats`：count_loc / list_files / git_status）+ `examples/mcp_demo.py`；依赖 `mcp>=1.0.0`
- **模型后端**：`mini_agent/llm.py`（OpenAI 兼容 + 超时/重试 + `MockLLM`）
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
| 第8课 | 整合 + 打磨 | 合成 CodeOps Agent：README、架构图、演示、部署、简历包装 |

---

## 学习进度

- 当前课程：**第6课（多 Agent + MCP）** —— 已完成：6a「多 Agent 分工」（规划者/执行者/评审者 + JSON 消息协议 + 白名单工具）、6b「MCP 接入」（自定义 MCP server `repo-stats` + 客户端适配器挂进 Agent）+ 练习6b（给 server 新增 `git_status` 只读工具）
- 已完成：
  - 第1课：真实 API 接通（DeepSeek 兼容）
  - 第2课：多步串行 + run_shell 白名单沙箱
  - 第3课：final_answer 终止工具 + 结构化输出 + API 超时/重试
  - 第4课：短期上下文滑动窗口 + 长期记忆(remember/recall) + 最小 RAG(kb_search/knowledge.py)
  - 第5课：计划字段 + ReAct 规则 + 思考可见 + 写入后自验证
- 环境：Python 3.13 虚拟环境 `.venv`；运行激活 venv 或用 `.venv/Scripts/python.exe`；真实 key 在本地 `.env`（已 gitignore）
- 待补/备注：第6课重点：多 Agent 分工 + 消息协议，以及 MCP 接入与自定义 MCP server

---

## 相关文件

- `README.md` —— 项目说明与上手教程
- `AGENTS.md` —— 本文件，教学约定 + 项目现状 + 进度（每次会话先读）
- `mini_agent/` —— 核心：`agent.py`(主循环) `tools.py`(工具) `llm.py`(模型后端) `knowledge.py`(最小RAG) `roles.py`(多Agent分工) `mcp_client.py`(MCP客户端适配器) `main.py`(CLI)
- `knowledge/` —— 知识库文档（project.md / lesson_notes.md），索引 index.json 已 gitignore
- `examples/` —— `mock_demo.py`(离线演示) / `build_kb.py`(建索引) / `multi_agent_demo.py`(多Agent演示) / `mcp_server.py`(自定义MCP server) / `mcp_demo.py`(MCP接入演示)
- `scripts/` + `.githooks/` —— 敏感信息检查与提交前钩子
