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

- 当前课程：**第11课（代码 Agent 闭环）**（进行中）—— 8 课主线已完成，进入第9~11课进阶阶段；第10课（网页版）已完结（10A~10G）
  - 进阶路线（已确认，三合一，即第9~11课）：第9课 生产级 RAG（embedding + 向量库 + 混合检索 + 检索评估）→ 第10课 CodeOps 网页版（流式 + FastAPI + Vue）→ 第11课 代码 Agent 闭环（写代码→跑测试→改）
  - **10A 流式输出** ✅：`llm.py` 加 `chat_stream()`（OpenAI/Anthropic/Mock 三后端：yield 文本增量 + return 完整消息，工具调用轮次不 yield 文本）；`agent.py` 的 `run()` 加 `stream=True`（生成器逐段 yield 增量，`StopIteration.value` 拿最终答复，非流式行为不变）；`examples/stream_demo.py`（mock 打字机效果；真实 API 验证：纯文本流式 + final_answer 结构化收尾都正常）
  - **练习10A 流式事件协议** ✅：`run(stream=True)` 从 yield 裸文本升级为 yield 统一 dict 事件——`{"type":"delta","text":...}` 文本增量 / `{"type":"tool","name","args"}` 工具调用开始 / `{"type":"result","name","text"}` 工具结果，生成器 return 值 = 最终答复；`_run_tool_calls` 返回结果列表 + `stream` 参数（流式下抑制 verbose 重复打印，事件承载展示）；`stream_demo.py` 按事件类型渲染（工具进度在文本前出现）；验收：mock 工具事件先于文本 ✅、纯文本回答无工具事件 ✅、不改 llm.py ✅、非流式回归（mock_demo/eval_harness 1/4）✅、真实 API 验证 calculator 事件 + final_answer 结构化收尾 ✅
  - **10B FastAPI 后端（SSE 流式接口）** ✅：`web/server.py`（`POST /api/chat` 把 `run(stream=True)` 的事件逐个转成 SSE `data: {json}\n\n`，补发 `done`（最终答复，从 StopIteration.value 拿）/`error` 事件；`history` 字段支持多轮上下文，只收 user/assistant 文本；CORS 放开跨域；`GET /test.html` 服务浏览器测试页）；`web/test.html`（fetch + ReadableStream 消费 SSE——EventSource 不支持 POST，这是 10C Vue 前端要用的消费方式）；requirements.txt 加 fastapi/uvicorn；验收：curl mock/真实 API 事件流 tool→result→delta→done 顺序正确、history 多轮生效、浏览器全链路渲染成功（截图 web-test.png）
  - **练习10B 会话记忆** ✅：`ChatRequest` 加 `session_id`——命中复用 `sessions` dict 里的 Agent 实例（history 跨请求保留），未命中新建并存入，不传则保持无状态；`GET /api/sessions` 调试端点（看每个会话的上下文长度，mock 不真推理、靠 history 长度验证机制）；验收：mock 同会话 history 增长/异会话隔离/无状态不入库 ✅、真实 API 两轮对话正确答出 42 ✅；已知代价：dict 无限增长 + 并发写 history 竞争，生产要换 Redis/加过期/加锁
  - **10C Vue 前端（聊天页面）** ✅：`web/` 完整的 Vite + Vue 3 `<script setup>` 工程（package.json / vite.config.js 代理 /api → :8000、index.html 内联 SVG favicon）；`src/App.vue`（fetch + ReadableStream 消费 SSE，`reactive` 包裹 assistant 消息避免流式文本静默丢失，deep watch 自动滚底，session_id 存 localStorage 刷新续会）；`src/components/ChatMessage.vue`（工具事件渲染成终端日志行：左语义色边条 + 等宽字体，❯=tool 琥珀 / →=result 绿）；`src/components/ChatInput.vue`（回车/按钮发送，生成中禁用）；深色终端风（`style.css` 全局 CSS token：青=用户 / 琥珀=tool / 绿=result / 红=error，颜色即信息类型）
  - **10C 刷新恢复历史** ✅：`GET /api/sessions/{sid}/history` 读 `chat_logs`（server 层新加的展示用对话记录：user 提问 + 最终答复成对，done 事件时写入）；`App.vue` 挂载时按 localStorage 的 session_id 拉历史渲染。**架构认知**：`Agent.history` 是「模型上下文」不是「人看的对话记录」——含 tool_calls/content=null 的工具轮、final_answer 直接 return 不写回最终答复，不能直接当历史返回；展示记录与模型上下文分离（chat_logs vs history）。验收：mock/真实 API 双跑 calculator 链路 ✅、刷新后历史恢复（工具事件不恢复=设计）、`reactive` 坑验证、无状态不写 chat_logs、后端重启后旧 session_id 返回空列表分支、vite build 通过、截图 web-10c-chat.png（深色终端风）；模型不支持图片输入，全程文本式验证（Playwright 快照/DOM）未喂图给模型
  - **10C 打磨（Element Plus + 推理显示 + 干净答复）** ✅：①布局——头部全宽横贯浏览器，消息区/输入框居中限宽 1000px（`--content-width` token）；②Element Plus——el-input/el-button/el-icon/el-tooltip 替换原生组件，`html.dark` 深色模式 + style.css 覆盖 EP CSS 变量成终端风（primary=青色）；③**推理过程显示**——前端 pending-buffer：delta 先缓冲，tool 事件裁决它是推理（提交进 thinking 块）还是答复（done 时成为 content），**协议不变、展示层自己判断**（流式里文本是推理还是答复，只有看到后续事件才知道，后端不用为推理单独加事件类型）；ChatMessage 加 Claude Code 风格可折叠「思考」块；④**final_answer 干净输出**——server.py 加 `clean_final_answer()`：把结构化 JSON dump 提取 summary（+ 不在 summary 里的 result），done 事件和 chat_logs 都用干净答复；**只改展示层，Agent 核心不动**（多 Agent Orchestrator 解析完整 JSON 做评审，改了会破坏它）；前端过滤 final_answer 的 tool/result 事件。验收：vite build ✅、Playwright 文本式验证布局/EP 组件/深色主题/思考块折叠/刷新恢复干净答复/多轮上下文（2+3=5 → 5*2=10）✅、clean_final_answer 四边界（summary 含 result / 不含 / 纯文本 / 非法 JSON）✅、mock 回归 ✅、截图 web-10c-ep.png；已知代价：EP 全量引入包大（983KB JS），生产可换 unplugin-vue-components 按需引入
  - **10C 体验修复（六项）** ✅：①消息列表滚动条隐藏（scrollbar-width:none + webkit display:none）+ 底部留白 2.5rem；②工具结果默认折叠——超 100 字符截断 + 「展开/收起」按钮（短结果完整显示）；③assistant 消息改**全宽正文**（去气泡边框/背景/限宽），user 保持右侧气泡，assistant 角色标签移除；④**思考按时间线分开**——thinking[] 数组升级为统一 timeline：每次 tool 事件前 flushReason 一条独立 reason 条目，思考/工具/结果按发生顺序交错（实测：计划思考→list_dir+calc 并行→「根目录存在 README.md」思考→read_file），不再堆在顶部；⑤**折叠不跳底**——删掉 `deep watch(messages)`（它监听一切变更，折叠 toggle 也触发滚底），改为显式滚动：数据块到达时先记 `isNearBottom()`，只在用户本来就在底部时跟滚（实测折叠后 scrollTop 320 不变）；⑥主题色青色 #22d3ee → Element Plus 默认蓝 #409eff（--user + primary-dark-2 + favicon 同步）。全部纯前端改动，后端协议未动
  - **10D 磨砂重构 + 轨迹入口 + 启动脚本（五项）** ✅：①**去掉输出块背景色**——`.think`/`.event` 的实心 `--surface-2` 改透明，只留左侧语义色边条，事件直接落在页面背景上；②**页面背景换苔藓图**——`web/public/moss.jpg`（从用户图片文件夹拷入，改名 moss）+ `body` 铺满固定；「背景透明度」用 `#app::before` 一个 `z-index:-1` 的半透明深色线性渐变（rgba .72→.85）做遮罩，苔藓隐约可见、文字依然清晰；头部/输入栏/轨迹抽屉也改**磨砂玻璃**（`rgba+backdrop-filter`）与背景一体；③**输出块加 EP 图标+说明文字**——全部走 Element Plus 官方图标库：思考=Cpu / 调用工具=Tools / 工具结果=Document，替换原先的 `❯`/`→` 字符符号，图标颜色继承语义色（tool 琥珀 / result 绿）；④**会话轨迹展示面板**——后端加 `GET /api/sessions/{sid}/trace`（直接读该会话 Agent 实例的内存 `trace`，天然按会话隔离；不读 `logs/agent.jsonl`，它全局 append-only 且事件无 session_id、web 后端也未接 audit），前端头部加「轨迹」按钮弹 `el-drawer`（新 `TracePanel.vue`：同款图标语言 + step/耗时/时分秒 + 结构化参数，磨砂抽屉）；⑤**`start.bat` 一键启动**——默认 mock，可传 `anthropic`/`openai`；自动 `cd /d %~dp0`、检查 `.venv`、缺依赖自动 pip/npm install，后端前端各开一窗。**架构认知**：④ 是想展示第7课的「轨迹/审计」——结论是**展示"内存轨迹"而非"磁盘审计"**：轨迹按会话隔离、现成；审计是后端证据文件，要展示得先接线 + 加 session_id；已知代价：`agent.trace` 在实例上累积（跨多次 run），同一会话越积越长。验收：vite build ✅（无图标 import 报错）、后端 curl 轨迹（calculator step1→assistant step2 正确）✅、Playwright 三张截图（苔藓背景可读 / 时间线图标+透明块 / 轨迹抽屉）✅、mock 回归 ✅；已知：mock 不先输出文本再调工具，闲聊流程里不出现「思考」块，真实 API 才有
  - **10D 修补（背景降透明 + 502 提示 + 轨迹排版）** ✅：①背景遮罩（`#app::before` 的 rgba）收敛到 **.70→.84**——苔藓更暗更含蓄、退成背景，文字清晰、便于聚焦；用户明确不要更亮，故**不加 text-shadow**，靠暗遮罩保证可读（此前 .55→.68 提亮版弃用）；②**502 根因**=后端没在 :8000 跑、Vite 代理转发失败——前端 `send()` 对 502/网络错（`Failed to fetch`）给可行动提示（"后端未启动…请运行 start.bat"），运行 `start.bat` 或手动起 `web/server.py` 即解决；③轨迹抽屉排版——每步一张浅色卡片（左边条=类型色），head=【图标·标签·元信息靠右 nowrap】，body 用细分割线隔开，顶部加「本会话 N 个步骤」统计，`meta()` 耗时格式化到 .2f；另修复抽屉头部：标题「轨迹」与关闭按钮**贴边**→ header/body 各加左右留白 padding。验收：`vite build` ✅、真实 API（`--provider anthropic`，Ollama cloud / `deepseek-v4-flash`）浏览器全链路（read_file→工具结果→真实答复、trace 出现 final_answer）✅、截图（暗苔藓+文字清晰 / 轨迹头部留白 / 真实答复）✅
  - **10D 补丁（Anthropic 多工具 tool_result 合并）** ✅：真实 API 下模型**并行调多个工具**（一个 assistant 消息里 3 个 tool_use）时，后端报 400 `tool_use ids were found without tool_result blocks immediately after`。根因：`llm.py::_to_anthropic_messages` 把每个 `role=tool` 结果各转成**一条** user 消息（OpenAI 式），而 **Anthropic 更严**：同一条 assistant 里的所有 tool_use，其 tool_result 必须放在**紧随其后的同一条** user 消息里（否则判定悬空）。单工具轮次"结果在下一条"成立所以一直能过（前面课时没暴露）；并行/连续调多工具时，第二个起的 result 不在"下一条"里 → 400。修复：把**连续的** role=tool 合并成一条 user，一条里放多个 tool_result 块。验证：确定性复现（构造 3 tool_use 历史 + 真实 API）修复前 400、修复后 200 ✅、多轮对话（25² → /5）无报错 ✅、纯文本/单工具路径回归 ✅；教训：Anthropic 的「工具结果必须紧随其后同一条消息」比 OpenAI 严，多工具并行是隐藏雷区，`_to_anthropic_messages` 这类请求侧翻译是校验最严的地方
  - **10E 轨迹补全（模型思考 + 提示词上下文）+ 输出块配色** ✅：①轨迹抽屉补上 DeepSeek harness 那样的两类数据——**模型思考**（每步真实 `thinking` 块文本，`block.thinking`）+ **提示词·上下文**（每步发给模型的 `_messages()` 快照，按 `[role]` 短行渲染、截断到可读长度）。改动：`llm.py::_from_anthropic_response` 不再跳过 thinking 块，收集进返回 dict 的 `thinking`；`agent.py::_run` 每步调模型前记 `role=prompt` 轨迹（`_render_messages` 渲染）、拿到回复后记 `role=thinking` 轨迹。**关键**：①thinking **不开** `thinking` 参数也能拿到（真实 API 探测证实），且**不回传** history（否则触发"thinking 块必须带 signature"的 300，正是上一节那个雷区）；②流式 `get_final_message()` 已经还原 thinking，所以流式/非流式共用 `_from_anthropic_response` 都带上；③SSE 事件协议**不变**——thinking 只进轨迹，不走 delta 事件，聊天区照旧靠 pending-buffer 显示文本前言。②输出块配色（用户要求"只有图标和名称带颜色，其他文字灰色"）——`ChatMessage.vue` 的 `.ev-call`/`.result-text` 从类型色/白色改 `--text-dim` 灰，图标+语义标签保留类型色（琥珀/绿），最终答复 `.text` 保持亮色 `--text`，让它成为视觉焦点；TracePanel 同步（`tp-label` 按类型着色、`.tp-body` 灰）。③背景遮罩继续压暗（`#app::before` rgba **.70→.78 / .84→.89**）。验证：vite build ✅、真实 API 三段链路（calculator→read_file→final_answer）聊天区 + 轨迹抽屉 thinking/prompt/tool/final_answer 齐全 ✅、mock 回归（无 thinking，只 prompt/tool/assistant）✅、截图 `web-10d-trace-thinking.png`；已知：thinking 只在"模型真的产出 thinking 块"那几步出现（聊天空里"思考"来自文本前言 pending-buffer，是两类东西）
  - **10F 体验优化（思考蓝 + 思考动画 + 轨迹折叠 + 步数上限）** ✅：①**"思考"改专用蓝**——新增 CSS token `--think:#60a5fa`（区别于主题蓝 `--user`：推理是过程、用户消息是角色），ChatMessage 的 think 边条/图标/标签、TracePanel 的「模型思考」边条/图标/标签都用 `--think`，正文仍灰。②**轨迹每条可折叠（默认收起）**——TracePanel 加载时给每条 `open:false`，头部做成整条可点按钮 + caret（▸/▾），正文点击才展开，62 步的会话也一眼可扫。③**模型"思考时无输出"动画**——ChatMessage 加 `showThinking`（流式且无 content/pending 且 timeline 空或上一条是 result → 模型正在琢磨），显示转圈 spinner + 轮换状态词（思考中/分析中/推理中/计算中/整理中/编译中），像 Claude Code 的 vibing/cooking；纯前端、不改协议，首个 delta/tool/done 一到就让位。④**网页版步数上限放宽**——`web/server.py` 加 `WEB_MAX_STEPS=24`（命令行 12 步够单任务，但"分析整个项目"这类宽任务常常不够就 timeout）。验证：vite build ✅、真实 API 浏览器全链路（两条对话后轨迹 62 步）、思考动画"分析中…"捕捉到 ✅、截图 web-10e-trace-collapse.png；**已知**：④ 只解决"步数不够"——超长任务里**滑动窗口（max_context_messages=20）会裁掉最开头的用户问题**，模型跑到一半"忘了自己在干嘛"（实测"分析一下这个项目"没 timeout，但回了"没有收到具体任务指令"），这是滑动窗口 vs 长任务的设计张力，属下一个要权衡的点（锚定目标 / 摘要记忆 / 加大窗口）
  - **10G 会话历史（落盘持久化 + 列表/改名/删除 + 侧栏切换）** ✅：①**后端持久化**——`web/server.py` 加 `sessions.json` 落盘（`_load_store`/`_save_store`，tmp 文件 + `os.replace` 原子替换，写一半崩溃不留半个 JSON），存三份：`session_meta`（列表展示用元信息）/`chat_logs`（人看的对话记录）/`histories`（模型上下文，重启后重建 Agent 用——**重启后能"回到之前的对话继续聊"而不只是能看**）；不存 trace（单次运行调试产物，可能几百步，重启后旧会话轨迹为空是设计取舍）。②**列表/改名/删除接口**——`GET /api/sessions`（name/轮数/消息数/创建/最近活动，按最近活动倒序）、`PATCH /api/sessions/{sid}` 改名（404/空名 400）、`DELETE /api/sessions/{sid}`（四份数据一起清）；新会话自动命名（首条消息截 20 字 + …，用户改名后不再覆盖）。③**前端会话侧栏**——头部「会话」按钮弹 `el-drawer`（新 `SessionPanel.vue`：磨砂抽屉、当前会话高亮、行内改名 el-input、删除带 el-popconfirm 确认）；点击切换 session_id + 恢复历史 + 轨迹重载（TracePanel 加 watch sid）；删除当前会话回退新会话。**关键坑**：`from __future__ import annotations` 下 FastAPI 的 Pydantic 模型**必须定义在模块级**——注解是惰性字符串，FastAPI 靠 `get_type_hints` 在模块命名空间解析，函数内局部类解析不到退化成 ForwardRef（PATCH 被当成 query 参数 + OpenAPI 500），用两个最小复现（模块级 vs 函数内）验证后把 `RenameRequest` 移到模块级。**架构认知**：展示记录（chat_logs）与模型上下文（histories）分离落盘——前者人看、后者服务推理（含 tool_calls/content=null 的工具轮，人不可读）。验收：curl 全链路（自动命名/截断/改名/多轮/重启持久化/历史恢复/删除/404）✅、Playwright 文本式验证（列表倒序/切换恢复 2+3 历史/删除非当前/删除当前回退空状态）✅、vite build ✅；已知代价：单文件 JSON 全量读写，会话多了会慢，生产换 SQLite/Redis
  - **11A 讲：run_python 执行工具（分层沙箱）** ✅：`tools.py` 新增 `run_python(script, args)`——第7课把 python 移出 run_shell（`python -c`=RCE），但编码闭环必须能执行代码，所以"有控制地"还回去，沙箱边界四条：①脚本必须在工作目录内（`_safe_path` 校验）；②`sys.executable` + `shell=False`（无管道/重定向/命令拼接）；③30s 超时（死循环/算法太慢反馈明确可行动）；④输出截断 4000 字（traceback 不撑爆上下文）。心智模型：权限最小化不是"能力越少越好"而是"**每层能力的边界清晰、可审计、互不污染**"——`run_shell`=只读检查(低信任) vs `run_python`=沙箱内执行(高信任)。同步 `DEFAULT_SYSTEM_PROMPT` 加规则12「编码任务必须闭环：写完用 run_python 跑测试，失败/超时根据报错改到通过，测试通过才算完成」。验证：5 项冒烟（正常/断言失败带 traceback/越权路径拦截/文件不存在/死循环 30s 超时）✅
  - **11A 实战发现（空响应坑）** ✅：复杂编码任务（num_to_cn 14 用例）稳定返回"空响应"（无正文无工具调用）——根因：模型先吐长 thinking 块，`max_tokens=2048` 被思考吃光，正文/tool_calls 无处安放。修复两处：①`llm.py` AnthropicLLM 默认 max_tokens 2048→4096（编码任务思考+代码双倍占用，预算必须给足）；②`agent.py` 加**空响应兜底**——无文本无工具调用不能交付空串，记 `role=empty` 轨迹 + 重试一轮（失败反馈哲学同样适用于 Agent 自身的模型调用）。用带/不带工具的直连探测排除任务内容因素；改后 num_to_cn 完整跑通。**教训：输出预算 2048 在闲聊够用、在编码任务不够，默认值要按场景设，且 Agent 要能消化"模型自己返回垃圾"这一级失败**
  - **11B 讲：最小演示 + 闭环验证** ✅：`examples/lesson11_demo.py`（`AGENT_WORKDIR` 隔离到 `examples/_work/`（已 gitignore），生成的代码不污染仓库根；`--provider mock/anthropic`、`--task` 可换任务、轨迹渲染成「step·角色→摘要」一眼看闭环、自动统计 run_python 次数作为闭环证据）。真实 API 三段验证：①fib 任务（写 test_fib.py→run_python 首跑 ALL PASSED→final_answer，闭环收缩为写→测→过，同样成立）；②num_to_cn 任务（14 个 assert 用例，首版就处理好零连读/一十→十/万位衔接，首跑即过）；③**is_pal 修复任务（种 bug：`s==s[::-1]` 未忽略空格标点）——Agent 跑测试挂(exit 1 traceback)→定位→re.sub 修复→再跑 ALL PASSED，run_python 恰好 2 次=「失败→修改→再跑」铁证**；还自带路径纠错（任务里的 examples/_work 相对当前工作目录算错，Agent 靠 list_dir 失败反馈自己找对位置）。**实证发现：强模型对明确规格的"从零写"任务首跑即过率高，闭环真正发力在"改"——测试契约与首版行为冲突时**；练习围绕"改"设计
  - **做：练习11A 已布置**（见会话；编码闭环评测器）
  - **11C 步数上调 + 目标锚定** ✅：①**步数**——`agent.py` 默认 max_steps 12→24、`main.py` CLI 默认同、`web/server.py` WEB_MAX_STEPS 24→48、`examples/lesson11_demo.py` 24→40、`knowledge/project.md` 同步（上限是保险丝不是目标值，上调无副作用；"分析整个项目"这类宽任务 24 步常不够）；②**目标锚定**——`agent.py` 加 `self._anchor`（本轮 user_input），`_messages()` 裁剪滑动窗口后若本轮用户问题已被裁掉，就把它钉回窗口最前（`not in recent` 防重复注入，短任务不受影响）。**结论：步数与"滑动窗口丢目标"是两个独立变量**——只加步数，超长任务会先丢用户问题（10F 实测回"没有收到具体任务指令"），本次一并解决。验证：脚本 LLM 确定性 30 轮（第 11 轮起触发裁剪，此后每轮窗口最前都是用户任务、锚点全程恰好 1 份）+ mock 回归 ✅；`_to_anthropic_messages` 天然兼容"user 紧跟 user"（锚定注入不破坏消息协议）
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
