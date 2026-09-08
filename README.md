# Mini Agent 入门项目：从 0 写一个会调用工具的智能体

这个项目是一个**极简但能跑**的 AI Agent 脚手架。它故意不引入复杂框架（LangChain / CrewAI / AutoGen），
而是用手写的方式把 Agent 的**核心循环**讲清楚——只有理解了这一层，你去看那些框架才会恍然大悟。

## 你已有的知识怎么迁移过来

| 你在 Claude Code / vibe coding 里见过的 | 对应到本项目的哪一个部分 | 说明 |
|---|---|---|
| Skill | 一个/一组工具的**描述 + 触发词** | 工具上方的 `@tool(...)` 装饰器和 `description` 就是“技能说明书” |
| Prompt / 系统提示词 | `agent.py` 里的 `DEFAULT_SYSTEM_PROMPT` | 告诉模型“你是谁、怎么用工具、何时该停” |
| Tool | `tools.py` 里注册的每个函数 | 模型通过 function calling 来“调用”这些能力 |
| 上下文（context） | `Agent.history` 短期记忆 | 每一轮对话 + 上一次工具结果都会被追加进来 |
| 人的“多步思考” | `run()` 里的 for 循环 | 模型决定调工具 → 拿到结果 → 再思考 → 再调/停 |

一句话：**ChatGPT 只会“谈话”，而 Agent 会“谈话 + 做事”。** 区别不在模型，而在于你有没有给它工具，以及有没有循环。

## 核心循环（Agent Loop）

```
用户输入
   ↓
[系统提示词 + 历史 + 用户消息]  →  大模型
   ↓
模型说“我要调用工具”？——是 → 执行工具 → 把结果追加回历史 → 回到大模型
   ↓                                  （这一步可重复很多次）
模型直接给出文字答复？ ——→ 输出最终答案
```

这个循环就是 LangChain / AutoGen 等框架帮你封装的“魔法”。看懂这张图，你就看懂了 80% 的 Agent 原理。

## 目录结构

```
agent-learn/
├── mini_agent/
│   ├── __init__.py
│   ├── agent.py      # Agent 主循环（最核心）
│   ├── llm.py        # 模型后端抽象（真实 API / mock）
│   ├── tools.py      # 工具注册表 + 各工具实现
│   ├── knowledge.py  # 最小版 RAG（切块 + 向量 + 检索）
│   ├── knowledge_embed.py  # 第9课 生产级 RAG（embedding + Chroma + 混合检索）
│   ├── roles.py      # 多 Agent 分工（规划者/执行者/评审者 + 编排器）
│   ├── mcp_client.py # MCP 客户端适配器（把外部 MCP 工具挂进 Agent）
│   ├── audit.py      # 审计日志（append-only JSONL + 轨迹渲染）
│   ├── codeops.py    # ★ CodeOps Agent 合成层（Orchestrator + MCP + 审计）
│   └── main.py       # 命令行入口
├── knowledge/        # 知识库文档（用 build_kb.py 建索引）
├── examples/
│   ├── mock_demo.py        # 离线演示脚本
│   ├── build_kb.py         # 建立知识库向量索引
│   ├── multi_agent_demo.py # 多 Agent 分工演示
│   ├── mcp_server.py       # 自定义 MCP server（仓库统计）
│   ├── mcp_demo.py         # 把 MCP 工具接进 Agent 的演示
│   ├── eval_harness.py     # 评测集：给 Agent 打分（4 任务 × 5 维度）
│   ├── lesson7a_hole.py    # 7A 漏洞演示：越权调用被拦截
│   ├── rag_eval.py         # 第9课 检索评估（hit@k 对比三方案）
│   └── codeops_demo.py     # ★ CodeOps Agent 演示（MCP + RAG + 多Agent + 写文件）
├── memory/           # 长期记忆存放处（notebook.md）
├── scripts/          # 辅助脚本（如密钥检查）
├── .githooks/        # 提交前钩子
├── .env.example
├── LICENSE
└── requirements.txt
```

## 快速开始

### 1. 先离线跑通（不需要 API key）

```
python -m mini_agent.main --provider mock --prompt "帮我计算 2+3 的结果"
```

或者进交互模式：

```
python -m mini_agent.main --provider mock
# 输入：帮我计算 2+3 的结果
# 观察它如何先调用 calculator，再根据结果给出答复
```

### 2. 换到真实大模型

```
pip install -r requirements.txt
cp .env.example .env    # 然后填上 OPENAI_API_KEY
python -m mini_agent.main --provider openai --model gpt-4o-mini
```

`--provider openai` 走的是 OpenAI 兼容的 `/chat/completions` 接口。
只要你手上是用这种协议的服务（DeepSeek / 通义千问 / 本地 Ollama 等），把 `.env` 里的
`OPENAI_BASE_URL` 改成对应地址就能复用同一个代码。

## 它是怎么工作的（逐文件拆解）

### 1. `tools.py` —— 给 Agent 安装“手脚”

一个工具就是：**函数 + 名字 + 描述 + 参数 JSON Schema**。其中“描述”尤其重要，因为模型是**读描述**而不是读源码来决定要不要调用它的。

`@tool(...)` 装饰器把函数注册进全局表，`get_tool_schemas()` 把整张表翻译成大模型能看懂的 `function calling` 声明。`execute_tool(name, args)` 负责按名字分发并执行。

> 小练习：自己加一个 `@tool("search_weather", ...)` 吧。你会立刻体会到：给 Agent 加能力 = 加一个函数 + 写清楚描述。

### 2. `llm.py` —— 模型后端

`LLM.chat(messages, tools)` 是唯一接口。Agent 只依赖它，因此你可以随时切换 OpenAI、别的兼容服务，或者一个不花钱的 mock。

- `OpenAIChatLLM`：调用真实的 function calling，返回带 `tool_calls` 的结构。
- `MockLLM`：离线、确定性。它看见“计算”就假装要调 `calculator`，拿到结果后再“假装思考”给个答复。**它的价值是让你在没有 key、没有网络时，也能肉眼看到“循环”的完整过程。**

### 3. `agent.py` —— 主循环

这是整个项目的心脏，却只有一小段：

```
1. 拼消息：system + history
2. 调模型
3. 若模型请求了工具 → 执行 → 把结果追加进 history → 回到第 1 步
4. 若模型直接给出文字 → 返回，结束
```

真正的 Agent 框架（无论多复杂）跑的也是这个循环，只是多了规划、记忆、验证、并行、子代理等“外挂”。

### 4. 两类“记忆”

- **短期记忆**：`Agent.history` + 滑动窗口（`max_context_messages`）。对话太长时只把最近 N 条发给模型，防止上下文爆掉、也避免“忘了开头”。
- **长期记忆（单条事实）**：`remember` / `recall`。把重要事实写进 `memory/notebook.md`，跨会话可检索。
- **长期记忆（RAG）**：`kb_search` + `knowledge.py`。把文档切块、向量化、按相似度检索，让 Agent 基于资料回答并注明来源。

> 三者配合：重要事实用 `remember` 存，整摞资料用 `kb_search` 检索，短期窗口保证长对话不超载。

### 5. 多 Agent 分工（`roles.py`）

单个 Agent 只有“一个脑子”。当任务复杂到需要**同时做多件事、互相审查**时，就把它拆成多个角色：

```
用户任务
   ↓
[规划者] 只拆步，不执行 → 计划步骤
   ↓
[执行者] 真正动手（计算/读写/跑命令）
   ↓
[评审者] 只看结果，判定 ok / retry
   ↓  (retry 则把反馈带回执行者重做)
结构化结果
```

- **分工本质**：给不同角色不同的 `system_prompt`（人设 + 规则）和不同的 `allowed_tools`（白名单）。
- **消息协议**：角色之间用 JSON 传递 `task / steps / result / verdict / feedback`，而不是散乱的文字。
- **复用第2课循环**：规划者/执行者/评审者都是同一个 `Agent` 类，只是人设和工具不同。

> 试运行：`python examples/multi_agent_demo.py --provider mock`（离线看骨架）或换 `openai-compatible` 用真实模型。

### 6. MCP 接入（`mcp_client.py` + `examples/mcp_server.py`）

**MCP（Model Context Protocol）** 是统一“LLM 应用如何接外部工具/数据”的开放协议，号称“给 AI 的 USB-C”。它把**提供能力**和**使用能力**解耦：

```
Agent（Host/Client）  ⇄  MCP Server（暴露工具/资源/提示）
```

- 我们的 **client 适配器**（`mcp_client.py`）用一个子进程把 MCP server 跑起来，走 stdio 交换**换行分隔的 JSON-RPC** 消息：
  `initialize` → `tools/list`（发现工具）→ `tools/call`（调用工具）。
- 它把每个 MCP 工具**翻译成本项目 Agent 认识的 `Tool`**（名字加 `mcp_` 前缀、参数直接复用 MCP 的 JSON Schema）。
- 于是 **`Agent` 主循环几乎不用改**——它只是多看到几个工具而已，这就是复用第2课循环的威力。

```
# 启动自定义 MCP server（仓库统计）
python examples/mcp_demo.py --provider openai-compatible
```

> 价值：以后给 CodeOps Agent 加能力（git / 数据库 / 文件系统）只需**挂一个 MCP server**，而不是改 Agent 代码。

### 7. CodeOps Agent（`codeops.py`）—— 前 6 节的"合体"

把前面所有零件**接线**成一个完整可运行的作品：读代码库 + 查知识库 + 多 Agent 分工 + 自动执行。

```
用户任务（"统计代码量" / "查部署步骤" / "写检查清单"）
   ↓
┌─────────────────────────────────────────────────┐
│ CodeOpsAgent（合成层：只做"接线"，不重写）         │
│  ┌───────────────────────────────────────────┐  │
│  │ Orchestrator（多Agent分工）                │  │
│  │  规划者 → 执行者 → 评审者 → ok/retry        │  │
│  └───────────────────────────────────────────┘  │
│  可靠性层：allowed_tools 白名单 + audit 审计     │
└─────────────────────────────────────────────────┘
   ↓ 工具层
┌──────────┬──────────┬──────────┬──────────────┐
│ 读代码库   │ 查知识库   │ 自动执行   │ MCP 外部能力  │
│ list_dir  │ kb_search │ write_file│ mcp_count_loc│
│ read_file │ (RAG)     │ run_shell │ mcp_git_status│
│ run_shell │           │ calculator│ mcp_list_files│
└──────────┴──────────┴──────────┴──────────────┘
```

- **合成层**（`codeops.py`）只有 ~50 行：注册 MCP 工具 → 追加进执行者白名单 → 给每个角色挂审计 → 暴露一个 `run(task)` 入口。**没有新算法，只有组合**——这就是"复用不是重写"。
- **演示**：`python examples/codeops_demo.py --provider anthropic`，一个任务同时考验 MCP（统计代码量）+ RAG（查部署步骤）+ 写文件（产出部署清单）+ 多 Agent 分工 + 审计。

## 动手练习（按难度递进）

1. **加一个新工具**：给它加 `@tool("search_weather", ...)`，然后让它回答“今天北京天气怎样？”（先用 mock 调起来，再换真模型）。
2. **加一个“规划”步骤**：在 `run()` 里，当复杂任务第一次进入时，先让模型输出一行 `计划：...`，再开始执行。
3. **加“验证/复查”循环**：让模型用一个 `run_shell` 工具执行并查看结果；如果结果是错误，再让它改一次。这就是很多“代码 Agent”的雏形。
4. **把长期记忆接上向量检索**：把 `recall` 从字符串匹配换成 embedding 相似度检索。
5. **改用 MCP**：把工具定义从“手写 schema”升级成 MCP（Model Context Protocol）服务器，可以让你的 Agent 直接使用一套标准化的外部工具。

## 本项目已覆盖的”进阶能力”（都在 examples/ 里有可运行演示）

| 能力 | 对应实现 | 演示 |
|---|---|---|
| MCP 工具生态 | `mcp_client.py` + `mcp_server.py` | `mcp_demo.py` |
| RAG 检索增强 | `knowledge.py` + `kb_search` | `build_kb.py` |
| 多 Agent 协作 | `roles.py`（规划者/执行者/评审者） | `multi_agent_demo.py` |
| 可观测性 | `audit.py`（trace + append-only JSONL） | 跑任意 demo 后看 `logs/agent.jsonl` |
| 评测 | `eval_harness.py`（4 任务 × 5 维度，退出码可进 CI） | `eval_harness.py --provider mock` |
| 安全与沙箱 | 执行层白名单 + 路径沙箱 + 命令白名单 | `lesson7a_hole.py` |
| 整合 | `codeops.py`（CodeOps Agent 合成层） | `codeops_demo.py` |

## 继续探索的方向（第9~11课路线）

- **第9课 · 生产级 RAG** ✅ 已完成：embedding（fastembed）+ 向量库（Chroma）+ 混合检索（BM25+向量 RRF）+ 检索评估（`knowledge_embed.py` + `rag_eval.py`）。
- **第10课 · CodeOps 网页版**：流式输出 + FastAPI 后端 + Vue 前端，把 CodeOps Agent 变成可交互网页。
- **第11课 · 代码 Agent 闭环**：写代码 → 跑测试 → 改，让 Agent 自主完成编码任务闭环。
- **更多 MCP server**：挂上数据库、浏览器、CI 等外部能力，CodeOps Agent 就能真正”运维”。

## 安全提示（重要）

- 项目里的 `calculator` 用 `eval` 只是教学演示，生产环境请换成 AST 白名单解析或专用计算服务。
- `write_file` / `read_file` 做了路径限制（`_safe_path`），但这还不够。真正的 Agent 一定要有**权限最小化、人工确认、沙箱执行、审计日志**。

## 小结

你已经亲手实现了 Agent 最核心的骨架。接下来不再是“学知识”，而是“加能力 + 加约束 + 加评测”。祝你玩得开心：）

## 开源许可

本项目使用 [MIT](LICENSE) 许可。

> 发布前请把 `LICENSE` 里的版权人改成你的名字；真实 API key 只放本地 `.env`（已 gitignore）。
> 提交前可跑 `python scripts/check_secrets.py` 做一次敏感信息检查。
