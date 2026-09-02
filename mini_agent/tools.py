from __future__ import annotations

import datetime
import json
import os
import shlex
import subprocess

from . import knowledge

_REGISTRY: dict[str, "Tool"] = {}

# 所有读写都限制在这个目录里，防止 Agent 越权访问系统文件。
BASE_DIR = os.path.abspath(os.environ.get("AGENT_WORKDIR", os.getcwd()))
MEMORY_FILE = os.path.join(BASE_DIR, "memory", "notebook.md")

# run_shell 的"白名单"：只允许执行这几个程序（最简单的沙箱）。
# 说明：Windows 下 dir/echo 是 cmd 内置命令，subprocess(shell=False) 找不到；
# 建议用 ls / cat / findstr / python / py / git / where 等真实可执行程序。
ALLOWED_COMMANDS = {
    "python", "python3", "python.exe", "py",
    "git", "node", "where", "ls", "cat", "wc", "findstr",
}


class Tool:
    """一个工具 = 函数 + 名字 + 描述 + 参数 JSON Schema。"""

    def __init__(self, name, func, description, parameters):
        self.name = name
        self.func = func
        self.description = description
        self.parameters = parameters
        _REGISTRY[name] = self

    def schema(self):
        # 这是大模型能“看懂”的工具声明格式（OpenAI function calling）。
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def execute(self, arguments):
        if isinstance(arguments, str):
            arguments = json.loads(arguments) if arguments.strip() else {}
        arguments = arguments or {}
        try:
            result = self.func(**arguments)
        except TypeError as exc:
            return json.dumps({"error": f"参数错误: {exc}"}, ensure_ascii=False)
        except Exception as exc:  # 工具要尽最大努力把错误变成“可读文本”送回给模型
            return json.dumps({"error": str(exc)}, ensure_ascii=False)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)


def tool(name, description, parameters):
    """装饰器：@tool(...) 一键把普通函数注册成 Agent 可用的工具。"""
    def decorator(func):
        Tool(name, func, description, parameters)
        return func
    return decorator


def _safe_path(path):
    raw = os.path.abspath(os.path.join(BASE_DIR, path))
    if os.path.commonpath([raw, BASE_DIR]) != BASE_DIR:
        raise ValueError(f"路径 {path!r} 超出了工作目录")
    return raw


@tool("get_current_time", "获取当前日期和时间", {"type": "object", "properties": {}})
def get_current_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool("calculator", "计算一个数学表达式，例如 '2+3*4' 或 'sqrt(16)'", {
    "type": "object",
    "properties": {"expression": {"type": "string", "description": "要计算的数学表达式"}},
    "required": ["expression"],
})
def calculator(expression: str):
    # 注意：这里的 eval 只做教学演示，生产环境请用 AST + 白名单，或直接接一个计算 API。
    safe_dict = {
        "abs": abs, "round": round, "min": min, "max": max,
        "pow": pow, "log": __import__("math").log, "sqrt": __import__("math").sqrt,
    }
    result = eval(expression, {"__builtins__": {}}, safe_dict)
    return str(result)


@tool("list_dir", "列出指定目录下的文件和子目录", {
    "type": "object",
    "properties": {"path": {"type": "string", "description": "要列出的目录，默认为当前工作目录"}},
})
def list_dir(path: str = "."):
    target = _safe_path(path)
    if not os.path.isdir(target):
        return json.dumps({"error": f"不是目录: {target}"})
    entries = []
    for name in sorted(os.listdir(target)):
        full = os.path.join(target, name)
        entries.append({"name": name, "type": "dir" if os.path.isdir(full) else "file"})
    return json.dumps(entries, ensure_ascii=False)


@tool("read_file", "读取一个文本文件的内容", {
    "type": "object",
    "properties": {"path": {"type": "string", "description": "要读取的文件路径"}},
    "required": ["path"],
})
def read_file(path: str):
    target = _safe_path(path)
    if not os.path.isfile(target):
        return json.dumps({"error": f"文件不存在: {target}"})
    with open(target, "r", encoding="utf-8") as f:
        return f.read(20000)


@tool("write_file", "把文本写入文件（会覆盖已有内容，自动创建父目录）", {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "要写入的文件路径"},
        "content": {"type": "string", "description": "文件内容"},
    },
    "required": ["path", "content"],
})
def write_file(path: str, content: str):
    target = _safe_path(path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return json.dumps({"ok": True, "written": target})


@tool("remember", "把一条信息写入长期记忆笔记，可加一个标签，用于跨会话记住用户偏好或事实", {
    "type": "object",
    "properties": {
        "content": {"type": "string", "description": "要记住的内容"},
        "tag": {"type": "string", "description": "可选标签，如 user/project/note"},
    },
    "required": ["content"],
})
def remember(content: str, tag: str = "general"):
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    line = f"- [{tag}] {content}\n"
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    return json.dumps({"ok": True})


@tool("recall", "在长期记忆里搜索包含关键词的笔记", {
    "type": "object",
    "properties": {"keyword": {"type": "string", "description": "搜索关键词"}},
    "required": ["keyword"],
})
def recall(keyword: str):
    if not os.path.isfile(MEMORY_FILE):
        return json.dumps({"matches": []})
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if keyword in ln]
    return json.dumps({"matches": lines}, ensure_ascii=False)


@tool("run_shell", "在白名单内执行一条系统命令并返回输出（不支持管道/重定向；用于查看目录、运行脚本、查版本等）", {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "要执行的命令，例如 'python --version' 或 'dir'"},
    },
    "required": ["command"],
})
def run_shell(command: str):
    # 1) 拆分命令：把 ';' / '&&' / '|' 等拼接拆成独立参数，避免偷塞子命令
    parts = shlex.split(command)
    if not parts:
        return json.dumps({"error": "命令为空"})

    # 2) 白名单：只允许"第一个词"是白名单程序（这就是最基本的沙箱）
    exe = os.path.basename(parts[0]).lower()
    if exe not in ALLOWED_COMMANDS:
        return json.dumps({
            "error": f"不允许的命令: {parts[0]}；白名单允许: {sorted(ALLOWED_COMMANDS)}"
        })

    # 3) 执行：shell=False 是关键，不解释管道/重定向/环境变量，更安全；加超时防止卡死
    try:
        proc = subprocess.run(
            parts,
            shell=False,
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "命令超时（>10s）"})
    except Exception as exc:
        return json.dumps({"error": f"执行失败: {exc}"})

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return json.dumps({"error": err or f"退出码 {proc.returncode}", "stdout": out})
    return json.dumps({"ok": True, "stdout": out, "stderr": err})

@tool("final_answer", "任务完成时调用它给出最终答复；把结果填进这些结构化字段", {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "给用户的一句话总结"},
        "plan": {"type": "array", "items": {"type": "string"}, "description": "执行前制定的计划步骤"},
        "steps": {"type": "array", "items": {"type": "string"}, "description": "执行步骤"},
        "used_tools": {"type": "array", "items": {"type": "string"}, "description": "用到的工具名"},
    },
    "required": ["summary", "plan", "steps"],
})
def final_answer(summary: str, steps: list[str], used_tools: list[str] | None = None):
    return json.dumps({"summary": summary, "steps": steps,
                       "used_tools": used_tools or []}, ensure_ascii=False)


@tool("kb_search", "在项目知识库中检索与问题相关的段落（RAG）；当问题涉及项目资料/文档/笔记时使用。返回匹配片段和来源。返回的 text 已包含匹配内容，通常无需再调用 read_file。", {
    "type": "object",
    "properties": {"query": {"type": "string", "description": "检索问题或关键词"}},
    "required": ["query"],
})
def kb_search(query: str):
    results = knowledge.search(query, top_k=3)
    if not results:
        return json.dumps({"error": "知识库为空或没有匹配内容"}, ensure_ascii=False)
    out = [{"source": r["source"], "score": r["score"], "text": r["text"][:300]} for r in results]
    return json.dumps(out, ensure_ascii=False)


def get_tool_schemas():
    return [t.schema() for t in _REGISTRY.values()]


def execute_tool(name, arguments):
    if name not in _REGISTRY:
        return json.dumps({"error": f"未知工具: {name}"})
    return _REGISTRY[name].execute(arguments)
