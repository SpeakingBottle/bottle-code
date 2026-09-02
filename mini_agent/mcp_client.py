from __future__ import annotations

import json
import subprocess
import sys

from . import tools as tool_module


class MCPClient:
    """一个极简、同步的 MCP stdio 客户端。

    MCP stdio 传输 = 通过子进程 stdin/stdout 交换“换行分隔的 JSON-RPC 2.0”消息。
    我们手动实现最小子集（initialize / tools/list / tools/call），
    这样能看清协议底层，也方便配合同步的 Agent 主循环。
    """

    def __init__(self, command: str, args: list[str] | None = None,
                 protocol_version: str = "2024-11-05"):
        self.proc = subprocess.Popen(
            [command, *(args or [])],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
        )
        self._id = 0
        self._handshake(protocol_version)

    # ---- 底层：发送 + 接收一条 JSON-RPC 消息 ----
    def _send(self, obj):
        self.proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def _recv(self) -> dict:
        line = self.proc.stdout.readline()
        if not line:
            err = self.proc.stderr.read() or "未知原因"
            raise RuntimeError(f"MCP server 提前退出: {err}")
        return json.loads(line)

    def _request(self, method: str, params: dict) -> dict:
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        resp = self._recv()
        if resp.get("error"):
            raise RuntimeError(f"{method} 失败: {resp['error']}")
        return resp.get("result", {})

    # ---- MCP 协议流的几个关键步骤 ----
    def _handshake(self, protocol_version: str):
        self._id += 1
        self._send({
            "jsonrpc": "2.0", "id": self._id, "method": "initialize",
            "params": {"protocolVersion": protocol_version, "capabilities": {},
                       "clientInfo": {"name": "mini-agent", "version": "0.1"}},
        })
        resp = self._recv()
        if resp.get("error"):
            raise RuntimeError(f"initialize 失败: {resp['error']}")
        # 通知 server 我已完成初始化（notification 不需要 id）
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def list_tools(self) -> list[dict]:
        return self._request("tools/list", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> str:
        result = self._request("tools/call", {"name": name, "arguments": arguments or {}})
        texts = [item.get("text", "") for item in result.get("content", [])
                 if item.get("type") == "text"]
        return "\n".join(texts) if texts else json.dumps(result, ensure_ascii=False)

    def close(self):
        try:
            self.proc.kill()
        except Exception:
            pass


def register_mcp_tools(server_command: str, server_args: list[str] | None = None,
                       prefix: str = "mcp_") -> tuple[MCPClient, int]:
    """连上一个 MCP server，把它暴露的工具翻译成本项目 Agent 能用的 Tool 并注册。

    返回 (client, 注册的工具数)。注册后，Agent 的 get_tool_schemas() 就会看到这些工具，
    execute_tool() 也能把它 dispatch 到 MCP server 上执行。
    """
    client = MCPClient(server_command, server_args)

    def _make(name: str):
        def _call(**_kwargs) -> str:
            return client.call_tool(name, _kwargs)
        return _call

    count = 0
    for t in client.list_tools():
        tool_name = f"{prefix}{t['name']}" if prefix else t["name"]
        desc = t.get("description") or t.get("title") or f"MCP 工具 {t['name']}"
        params = t.get("inputSchema") or {"type": "object", "properties": {}}
        tool_module.Tool(tool_name, _make(t["name"]), desc, params)
        count += 1
    return client, count
