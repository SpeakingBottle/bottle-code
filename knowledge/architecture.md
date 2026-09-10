# 项目架构说明

## 模块职责

- `agent.py`：Agent 主循环，负责"模型→工具→观察→再想"的循环，含执行层裁决（职责边界 + 风险分级 + 工具前置条件）与审计轨迹。
- `tools.py`：工具注册表，所有工具（计算/读写文件/搜索/跑命令/检索）都通过 @tool 装饰器注册，每个工具带 `risk` 等级。
- `approval.py`：审批者抽象。`Approver` 协议 + 三个实现（`AllowAll` / `DenyAll` / `Terminal`），把"危险操作放不放行"从 Agent 核心里外置成可注入回调。
- `llm.py`：模型后端抽象，统一 OpenAI 兼容与 Anthropic Messages API 两种格式。
- `roles.py`：多 Agent 分工，规划者/执行者/评审者三个角色协作，用 JSON 消息传递结果。
- `mcp_client.py`：MCP 客户端适配器，把外部 MCP 工具翻译成本项目 Agent 认识的 Tool。
- `codeops.py`：Bottle Code 合成层，把 Orchestrator + MCP + 审计接线成一个入口。

## 执行层裁决（三道，按序）

工具调用在真正执行前要过三关，顺序不能变：

1. **职责边界**——`allowed_tools` 是硬边界：不在职责工具集里的 `write`/`execute` 一律拦，返回
   `[SECURITY]`。**`read` 类工具豁免**（读从不越权，而"写入后自验证"需要它）。
2. **风险分级**——过了边界的 `write`/`execute` 还要问 `Approver`；拒绝则返回 `[APPROVAL]`。
   未配置审批者时用 `AllowAllApprover`，但会记一条 `role=approval` 轨迹写明是自动放行。
3. **工具前置条件**——`_TOOL_PRECONDITIONS` 表驱动，如 `edit_file` 要求该文件先被
   `read_file` 读过或 `write_file` 写过（Agent 维护 `_read_files`）；不满足返回 `[PRECONDITION]`。

**为什么顺序不能反**：先判「这活是不是我的」，再判「危不危险」。反过来，模型幻觉调用一个
职责外的工具时会直接被送进审批（无人环境下默认放行），7A 挖的那个洞就回来了。

**为什么前置条件放在 Agent 层而不是工具函数里**：它依赖 Agent 的会话状态（见过哪些文件），
而工具函数是无状态、按名字调用的纯函数。「这个调用允不允许」是 Agent 的判断，不是工具的判断。

`allowed_tools` 的**提示层**作用同时保留：`_run` 里仍按其过滤工具 schema，模型看不到职责外的工具。
即"提示层软约束 + 执行层硬裁决"两层纵深。

## 工具自带防御（第 7 课三层纵深的第三层）

前两层之外，工具自身还有两处与危险等级无关的硬约束：

- **路径沙箱**（`_safe_path`）：所有读写限定在 `BASE_DIR` 内。
- **敏感路径拒绝**（`_safe_read_path` + `_is_sensitive_path`）：只作用于"读内容"的工具
  （`read_file` / `grep`）。`.env*`、`.git/` `.ssh/` `.aws/` `.gnupg/` 等目录下、
  `*.key` `*.pem` `*.p12` `*.pfx` `*.keystore` `*.jks`、名字含
  `secret` / `credential` / `password` / `id_rsa` / `id_ed25519` 的文件一律返回 `[SENSITIVE]`。

为什么需要第三条：`read` 类工具豁免了职责边界，**任何角色**都能读到 `BASE_DIR` 内的文件
（包括仓库根那个装着真实 key 的 `.env`）。这条拒绝判的是"路径"而不是"危险等级"——
路径本身就是机密，和它危不危险无关。写路径不受它约束（写仍受职责边界 + 审批双重约束）。

**为什么按路径判而不是按内容判**：按内容判会误伤——一份讲"如何管理 secret"的普通文档
会被判成机密。代价是内容里含密钥但文件名普通的文件仍会被读到，这属于"防不住的部分"，
真正的兜底是"不要把密钥放进工作目录"。

## MCP 接入方式

MCP（Model Context Protocol）是统一 LLM 应用接外部工具的协议。接入一个 MCP server 分三步：
1. 用子进程拉起 server（stdio 传输，换行分隔的 JSON-RPC 消息）。
2. 调用 tools/list 发现它暴露的工具。
3. 把每个工具注册成 mcp_ 前缀的 Tool，Agent 就能像用内置工具一样调用它。

## 多 Agent 分工

规划者只拆步骤不执行；执行者真正动手；评审者只看结果判定 ok/retry。
角色之间用结构化 JSON 传递 task / steps / result / verdict / feedback，评审不通过就带反馈重试。
