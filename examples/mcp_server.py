from __future__ import annotations

import pathlib

from mcp.server.mcpserver import MCPServer

# 一个自定义 MCP server：对外暴露"仓库统计"相关的能力。
# MCPServer 会自动把带 @server.tool() 的函数注册成 MCP 工具，并把类型注解转成 JSON Schema。
# （mcp 2.x 里 FastMCP 已改名为 MCPServer）
server = MCPServer("repo-stats", description="仓库统计：代码行数 / 文件清单")


@server.tool(description="统计指定目录下所有匹配扩展名的文件，返回文件数与总行数。")
def count_loc(directory: str, ext: str = ".py") -> str:
    total = 0
    files = 0
    for p in pathlib.Path(directory).rglob(f"*{ext}"):
        if p.is_file():
            files += 1
            with open(p, encoding="utf-8", errors="replace") as f:
                total += sum(1 for _ in f)
    return f"共 {files} 个 {ext} 文件，总计 {total} 行"


@server.tool(description="递归列出目录下所有匹配扩展名的文件路径。")
def list_files(directory: str, ext: str = ".py") -> str:
    paths = sorted(str(p) for p in pathlib.Path(directory).rglob(f"*{ext}") if p.is_file())
    return "\n".join(paths) if paths else "(无匹配文件)"


if __name__ == "__main__":
    server.run(transport="stdio")
