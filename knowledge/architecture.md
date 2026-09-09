# 项目架构说明

## 模块职责

- `agent.py`：Agent 主循环，负责"模型→工具→观察→再想"的循环，支持工具白名单与审计轨迹。
- `tools.py`：工具注册表，所有工具（计算/读写文件/跑命令/检索）都通过 @tool 装饰器注册。
- `llm.py`：模型后端抽象，统一 OpenAI 兼容与 Anthropic Messages API 两种格式。
- `roles.py`：多 Agent 分工，规划者/执行者/评审者三个角色协作，用 JSON 消息传递结果。
- `mcp_client.py`：MCP 客户端适配器，把外部 MCP 工具翻译成本项目 Agent 认识的 Tool。
- `codeops.py`：Bottle Code 合成层，把 Orchestrator + MCP + 审计接线成一个入口。

## MCP 接入方式

MCP（Model Context Protocol）是统一 LLM 应用接外部工具的协议。接入一个 MCP server 分三步：
1. 用子进程拉起 server（stdio 传输，换行分隔的 JSON-RPC 消息）。
2. 调用 tools/list 发现它暴露的工具。
3. 把每个工具注册成 mcp_ 前缀的 Tool，Agent 就能像用内置工具一样调用它。

## 多 Agent 分工

规划者只拆步骤不执行；执行者真正动手；评审者只看结果判定 ok/retry。
角色之间用结构化 JSON 传递 task / steps / result / verdict / feedback，评审不通过就带反馈重试。
