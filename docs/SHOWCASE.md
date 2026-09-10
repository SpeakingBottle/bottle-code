# Bottle Code · 作品说明与演示脚本

> 一个**从零手写、无框架**的通用 AI Agent 作品，并做成了可交互的网页版。
> 面向展示 / 求职 / 答辩 —— 这里的每一句话都能在仓库里找到对应代码和可验证的证据。

---

## 一、作品定位（30 字内）

**手写 Agent 主循环 + 生产级 RAG + 多 Agent 分工 + MCP 集成 + 网页版 + 编码闭环，一个能跑真任务的成品。**

它不只是"会聊天的 demo"，而是真正用工具"做事"：读代码库、查知识库、写文件、跑 Python、调外部 MCP 服务。全程不依赖 LangChain / CrewAI / AutoGen，核心循环是手写的 —— 所以我敢说"我理解每一个环节"。

## 二、核心能力地图

| 能力 | 一句话 | 代码 |
|---|---|---|
| Agent 主循环 | 模型→调工具→观察→再想，手写实现 | `mini_agent/agent.py` |
| 工具系统 | 13 个工具：检索/读写/编辑/记忆/RAG/跑Python/收尾，每个带风险等级 | `mini_agent/tools.py` |
| 短期记忆 | 滑动窗口裁历史，超长丢目标时锚定回钉 | `agent.py` |
| 长期记忆 | 笔记 + RAG 检索增强（不只记，还能查） | `tools.py` + `knowledge*.py` |
| 多 Agent 分工 | 规划者/执行者/评审者，JSON 协议 + 重试 | `mini_agent/roles.py` |
| MCP 集成 | 自定义 server + 客户端适配器，工具即插即用 | `mini_agent/mcp_client.py` |
| 权限与可靠性 | 职责边界 + 风险分级（危险操作走审批）+ 敏感路径拒绝 + 审计 | `agent.py` + `mini_agent/approval.py` + `audit.py` |
| 生产级 RAG | embedding + Chroma + BM25/向量 混合检索 | `mini_agent/knowledge_embed.py` |
| 网页版 | SSE 流式 + FastAPI 后端 + Vue 3 前端 | `web/` |
| 编码闭环 | run_python 沙箱 → 写→测→改，隐藏测试验证 | `examples/lesson11_*.py` |

## 三、技术亮点（每条都带验证证据）

### 1. 手写核心循环 ——"看穿框架的魔法"
不裹框架，用一个 `for` 循环 + 工具注册表把 Agent 讲清楚。看懂它 = 看懂 LangChain 帮你封装的那层。
> 证据：`mock` 离线可完整跑完"循环"全过程（无需 key/网络）。

### 2. 生产级混合检索 RAG（第9课）
BM25 关键词 + embedding 向量两类信号，用 **RRF 排名融合**（按排名取分，免调权重）合并。
> 证据：8 组查询 × hit@3，**混合检索 100%** > 词频版 88% = 纯向量 88%。语义改写查询"怎么把服务跑起来"只有混合版答对。

### 3. 多 Agent 分工（第6课）
单一 Agent 只有"一个脑子"，任务复杂时拆成规划者（只拆步）/ 执行者（动手）/ 评审者（判定 ok/retry）。
> 证据：`multi_agent_demo` 与 `codeops_demo` 一个任务串起 5 个能力，评审不通过自动重试。

### 4. MCP 集成（第6课）
用标准协议把外部能力挂进 Agent —— 写了自定义 MCP server `repo-stats`（count_loc / list_files / git_status）+ stdio 客户端适配器。
> 证据：Agent 主循环几乎不改，就多出 `mcp_*` 工具；今后加数据库/浏览器/CI 能力只需挂 server。

### 5. 权限三道裁决 + 三层纵深（第7课，后经"风险分级"升级）

执行层按**顺序**判三关，顺序不能反（先判"这活是不是我的"，再判"危不危险"）：

1. **职责边界**——`allowed_tools` 硬边界，职责外的写/执行类工具一律拦，返回 `[SECURITY]`。
   **read 类豁免**：读从不越权，而"写入后自验证"需要它。
2. **风险分级**——过了边界的 `write`/`execute` 要问 `Approver`，拒绝则返回 `[APPROVAL]`。
   未配置审批者时放行**但记一条 `role=approval` 轨迹**——让"没人可问所以自动放行"是可审计的决定。
   `TerminalApprover` 读不到输入时 **fail-closed 拒绝**（不能因为问不到人就放行）。
3. **工具前置条件**——表驱动，如 `edit_file` 要求该文件先被读过（`[PRECONDITION]`）。

纵深三层：**提示层软约束 + 执行层硬裁决 + 工具自带防御**（路径沙箱 + 敏感路径拒绝）。

> 证据：`lesson7a_hole` 用剧本模型逼它调用白名单外 `write_file`，从"越权成功"到"越权被拒"全程演示；
> `tooling_permissions_demo.py` 15 项边界全过（剧本 LLM 驱动、确定性、退出码可进 CI）。

### 6. 可观测性（第7课）
审计 = append-only 证据文件（含失败/含越权事件）+ 内存 trace + 网页版所见即所得的轨迹抽屉。
> 证据：`codeops_demo` 一次运行落盘 **42 条审计事件**；网页轨迹抽屉按会话隔离，把每步拆成「提示词注入 / 模型思考 / 调用工具 / 工具结果 / 最终答复」独立可折叠块。

### 7. 编码闭环 + 评测器（第11课）
`run_python` 分层沙箱（限工作目录内 + `shell=False` + 30s 超时 + 输出截断），让 Agent 写代码→跑测试→改到通过。评测器用**隐藏测试**独立验证产物，不盲信 Agent 自述。
> 证据：`lesson11_eval` 两个场景 —— A（标准任务）PASS；B（规定 `fib(1)=5`，隐藏测试用标准定义）**FAIL**：Agent 忠实执行错误契约、自测全过、还自述"断言通过"，但契约不符就是 FAIL。

### 8. 网页版（第10课）
SSE 流式（后端把 `run(stream=True)` 事件转成 `data:` 推送）+ Vue 3 前端；会话持久化到磁盘，刷新续聊；最终答复 markdown 渲染（marked + DOMPurify 消毒）。
> 证据：浏览器全链路验证（输入→tool 事件→result→delta→done）；会话列表/轨迹抽屉/改名/删除均可用；轨迹抽屉里每步「提示词注入/模型思考/调用工具/工具结果/答复」独立成块；`mock` 离线即玩。

## 四、演示脚本（约 3 分钟）

**① 网页版主界面**（开场，30s）
打开 `start.bat` 起的网页版，输入"帮我计算 2+3 的结果"，展示：流式打字机 + 工具事件时间线（调用工具→结果→答复）。
> 强调：这不是套壳聊天，是它真调了 `calculator` 工具拿结果再回答 —— 这就是"做事"。

**② 接真实 API 看推理**（30s）
说明换 `start.bat anthropic` 用真实模型后，点击「轨迹」，能看到模型每步的**思考块**和发给它的完整上下文 —— 可观测。

**③ CLI 合成演示**（60s，`codeops_demo.py`）
一个任务同时考验：MCP（统计代码量 1201 行）+ RAG（查部署步骤）+ 写文件（产出部署清单）+ 多 Agent 分工 + 审计落盘。

**④ 编码闭环**（30s，`lesson11_demo.py`）
给 Agent 一个编码任务，看它自己写测试跑、失败、改、再跑到全过 —— 最后用隐藏测试评测器独立判定，证明"自测通过 ≠ 正确"。

**⑤ 收尾**（30s）
一句话：无框架、手写、可观测、评测驱动 —— 这套东西我能讲清楚每一行。

## 五、评测数据汇总（硬指标）

| 项 | 指标 | 结果 |
|---|---|---|
| 检索质量 | 8 查询 × hit@3 | 混合 100% / 词频 88% / 纯向量 88% |
| 任务评测集 | 4 任务 × 5 维判定 | 真实 API 3/4（mock 1/4 是 mock 能力边界） |
| 编码闭环 | 隐藏测试独立判定 | 场景 A PASS / 场景 B FAIL（契约校验） |
| 审计 | 单次运行落盘事件 | 42 条 |
| 越权拦截 | 职责外调用 | 一律 `[SECURITY]` 拦截，不执行（read 类豁免） |
| 危险操作审批 | 写/执行类调用 | 未配置审批者时放行但**记入轨迹**；`DenyAll` 拒绝；`Terminal` 交互，读不到输入 fail-closed |
| 敏感路径 | 读含密钥的文件 | `[SENSITIVE]` 拒绝，与危险等级无关 |
| 工具层验收 | 15 项边界（剧本 LLM，确定性） | `tooling_permissions_demo.py` 15/15，退出码可进 CI |
| 网页链 | 浏览器全链路 | 流式/轨迹/会话持久化 全部可用 |

## 六、技术栈

- **语言**：Python（Agent 本体）+ JavaScript（Vue 3 前端）
- **模型**：Anthropic Messages API / OpenAI 兼容接口（DeepSeek 等）/ Mock（离线）
- **框架（只用于外围）**：FastAPI + uvicorn（网页后端）、Vue 3 + Vite + Element Plus（前端）
- **检索**：fastembed（embedding）+ Chroma（向量库）+ 手写 BM25 + RRF 融合
- **协议**：MCP（工具即插即用）、SSE（流式输出）
- **依赖刻意最少**：核心 Agent 无任何框架；`requirements.txt` 只列推理/检索/Web 所需

## 七、运行与开源

- 离线体验：`start.bat`（网页版 mock）/ `python -m mini_agent.main --provider mock`
- 接真实 API：`.env` 填 key 后 `start.bat anthropic`
- 许可：MIT；真实 key 仅存本地 `.env`（已 gitignore）
- 安全：提交前 `.githooks/pre-commit` 自动扫密钥；`python scripts/check_secrets.py` 可手动查

---

> 更完整的工程细节见 [README](../README.md)；教学约定与全部课程进度见 [AGENTS.md](../AGENTS.md)。
