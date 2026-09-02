from __future__ import annotations

import pathlib
import subprocess

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

@server.tool(description="查询当前 git 仓库的分支和未提交改动（只读）。")
def git_status() -> str:
    # 只读命令：--short 给出紧凑的改动列表，--branch 额外把当前分支/跟踪信息放在第一行
    proc = subprocess.run(
        ["git", "status", "--short", "--branch"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        return f"(git 查询失败) {proc.stderr.strip() or f'退出码 {proc.returncode}'}"

    lines = proc.stdout.strip().splitlines()
    if not lines:
        return "当前仓库干净：没有未提交改动。"

    # 第一行形如 "## master" 或 "## master...origin/master [ahead 1]"
    branch_desc = lines[0].replace("## ", "", 1)
    changes = [ln for ln in lines[1:] if ln.strip()]
    if changes:
        return (f"当前分支: {branch_desc}\n有未提交改动:\n" + "\n".join(changes))
    return f"当前分支: {branch_desc}\n仓库干净，没有未提交改动。"

if __name__ == "__main__":
    server.run(transport="stdio")
