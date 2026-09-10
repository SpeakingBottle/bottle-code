from __future__ import annotations

import ast
import datetime
import fnmatch
import json
import math
import operator
import os
import re
import shlex
import subprocess
import sys

from . import knowledge

_REGISTRY: dict[str, "Tool"] = {}

# 工具的风险等级：执行层据此决定「放行」还是「问审批」。
#   read    只读，无副作用 —— 执行层直接放行（读从不越权）
#   write   改磁盘 —— 需要审批
#   execute 跑进程 —— 需要审批
RISK_READ, RISK_WRITE, RISK_EXECUTE = "read", "write", "execute"

# 所有读写都限制在这个目录里，防止 Agent 越权访问系统文件。
BASE_DIR = os.path.abspath(os.environ.get("AGENT_WORKDIR", os.getcwd()))
MEMORY_FILE = os.path.join(BASE_DIR, "memory", "notebook.md")

# run_shell 的"白名单"：只允许执行这几个只读检查程序（最简单的沙箱）。
# 注意：解释器（python/node）会带来任意代码执行（python -c 等于 RCE），已从白名单移除；
# 剩余限制：cat 可读任意文件、git 可做仓库操作——第7课 7A 会用执行层权限检查系统性解决。
# 说明：Windows 下 dir/echo 是 cmd 内置命令，subprocess(shell=False) 找不到；
# 建议用 ls / cat / findstr / git / where 等真实可执行程序。
ALLOWED_COMMANDS = {
    "git", "where", "ls", "cat", "wc", "findstr",
}


class Tool:
    """一个工具 = 函数 + 名字 + 描述 + 参数 JSON Schema + 风险等级。"""

    def __init__(self, name, func, description, parameters, risk=RISK_WRITE):
        self.name = name
        self.func = func
        self.description = description
        self.parameters = parameters
        # 默认 write 是刻意的安全默认：新工具不声明风险就自动进审批，而不是自动放行。
        self.risk = risk
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


def tool(name, description, parameters, risk=RISK_WRITE):
    """装饰器：@tool(...) 一键把普通函数注册成 Agent 可用的工具。"""
    def decorator(func):
        Tool(name, func, description, parameters, risk=risk)
        return func
    return decorator


def _safe_path(path):
    raw = os.path.abspath(os.path.join(BASE_DIR, path))
    if os.path.commonpath([raw, BASE_DIR]) != BASE_DIR:
        raise ValueError(f"路径 {path!r} 超出了工作目录")
    return raw


@tool("get_current_time", "获取当前日期和时间", {"type": "object", "properties": {}}, risk=RISK_READ)
def get_current_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# calculator 的求值白名单：只认这些节点/函数，其余一律拒绝。
_ALLOWED_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_ALLOWED_FUNCS = {
    "abs": abs, "round": round, "min": min, "max": max,
    "pow": pow, "log": math.log, "sqrt": math.sqrt,
}
_MAX_EXPONENT = 1000   # 2**999999999 这类会直接吃光内存/CPU，拦掉


def _eval_node(node):
    """递归求值 AST，只放行白名单内的节点类型。任何越界都抛 ValueError。"""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"不支持的常量: {node.value!r}")
    if isinstance(node, ast.BinOp):
        op = _ALLOWED_BINOPS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
        left, right = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
            raise ValueError(f"指数过大（>{_MAX_EXPONENT}），拒绝计算以防资源耗尽")
        return op(left, right)
    if isinstance(node, ast.UnaryOp):
        op = _ALLOWED_UNARYOPS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的一元运算符: {type(node.op).__name__}")
        return op(_eval_node(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
            raise ValueError("只能调用: " + ", ".join(sorted(_ALLOWED_FUNCS)))
        if node.keywords:
            raise ValueError("不支持关键字参数")
        return _ALLOWED_FUNCS[node.func.id](*[_eval_node(a) for a in node.args])
    raise ValueError(f"不支持的表达式: {type(node).__name__}")


@tool("calculator", "计算一个数学表达式，例如 '2+3*4' 或 'sqrt(16)'。支持 + - * / // % ** 与 abs/round/min/max/pow/log/sqrt", {
    "type": "object",
    "properties": {"expression": {"type": "string", "description": "要计算的数学表达式"}},
    "required": ["expression"],
}, risk=RISK_READ)
def calculator(expression: str):
    """用 AST 白名单求值——**绝不 eval**。

    旧版是 `eval(expr, {"__builtins__": {}}, safe_dict)`，注释里写着"生产环境请用
    AST 白名单"。那个沙箱其实拦不住逃逸：清空 __builtins__ 挡不住从字面量做属性
    遍历——`().__class__.__bases__[0].__subclasses__()` 就能摸到 Popen / os.system，
    实测可以直接执行任意命令。

    而 calculator 是 risk=read、豁免职责边界的工具，任何角色的 Agent 都调得到，
    等于给 prompt injection 留了一条 RCE 通道（旧模型下 allowed_tools 还能挡，
    新模型下挡不住了）。所以从根上关掉：只认白名单节点，属性访问/下标/lambda/
    推导式/import 全部不可表达。
    """
    try:
        result = _eval_node(ast.parse(expression, mode="eval"))
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        return json.dumps({"error": f"无法计算: {exc}"}, ensure_ascii=False)
    return str(result)


@tool("list_dir", "列出指定目录下的文件和子目录", {
    "type": "object",
    "properties": {"path": {"type": "string", "description": "要列出的目录，默认为当前工作目录"}},
}, risk=RISK_READ)
def list_dir(path: str = "."):
    target = _safe_path(path)
    if not os.path.isdir(target):
        return json.dumps({"error": f"不是目录: {target}"})
    entries = []
    for name in sorted(os.listdir(target)):
        full = os.path.join(target, name)
        entries.append({"name": name, "type": "dir" if os.path.isdir(full) else "file"})
    return json.dumps(entries, ensure_ascii=False)


# grep 跳过这些目录：版本控制/虚拟环境/依赖/缓存，它们要么超大要么不是"项目代码"。
# 跳过是为了让结果聚焦在"你要找的那份代码"上，不是为了省时间。
_GREP_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__",
                   "dist", "build", ".mypy_cache", ".pytest_cache", ".idea", ".vscode"}
_GREP_MAX_FILE_BYTES = 1_000_000   # 超 1MB 的文件不搜（多半是数据/产物，不是源码）


@tool("grep", "在项目目录内按正则搜索文件内容，返回 `文件:行号:内容`。找代码/找定义/找用法用它，比逐个 read_file 快得多。找不到时换关键词或缩小 path 再试。", {
    "type": "object",
    "properties": {
        "pattern": {"type": "string", "description": "正则表达式，例如 'def main' 或 'class \\\\w+Agent'"},
        "path": {"type": "string", "description": "搜索起点（目录或文件），默认当前工作目录"},
        "glob": {"type": "string", "description": "可选文件名过滤，如 '*.py'"},
        "ignore_case": {"type": "boolean", "description": "是否忽略大小写，默认 false"},
        "max_results": {"type": "integer", "description": "最多返回多少条命中，默认 60"},
    },
    "required": ["pattern"],
}, risk=RISK_READ)
def grep(pattern: str, path: str = ".", glob: str | None = None,
         ignore_case: bool = False, max_results: int = 60):
    try:
        rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    except re.error as exc:
        return json.dumps({"error": f"正则表达式非法: {exc}"}, ensure_ascii=False)

    root = _safe_path(path)
    if not os.path.exists(root):
        return json.dumps({"error": f"路径不存在: {path}"}, ensure_ascii=False)

    # 起点是文件就直接搜它，是目录就 walk
    if os.path.isfile(root):
        candidates = [root]
    else:
        candidates = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _GREP_SKIP_DIRS]
            for fn in filenames:
                if glob and not fnmatch.fnmatch(fn, glob):
                    continue
                candidates.append(os.path.join(dirpath, fn))

    hits: list[str] = []
    truncated = False
    for full in candidates:
        try:
            if os.path.getsize(full) > _GREP_MAX_FILE_BYTES:
                continue
            with open(full, "rb") as fb:
                if b"\x00" in fb.read(1024):   # 二进制探测：前 1KB 有 NUL 就当二进制跳过
                    continue
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                for lineno, line in enumerate(f, 1):
                    if rx.search(line):
                        rel = os.path.relpath(full, BASE_DIR).replace("\\", "/")
                        hits.append(f"{rel}:{lineno}: {line.rstrip()[:300]}")
                        if len(hits) >= max_results:
                            truncated = True
                            break
        except OSError:
            continue
        if truncated:
            break

    if not hits:
        return json.dumps({"matches": [], "note": f"没有找到匹配 {pattern!r} 的内容"}, ensure_ascii=False)
    body = "\n".join(hits)
    if truncated:
        # 不静默截断：明说还有更多，让模型知道该缩小范围而不是以为"就这些"
        body += f"\n（已达上限 {max_results} 条，可能还有更多命中，请缩小 path 或用更精确的 pattern）"
    return body


# 单行显示上限：一行几万字符（压缩过的 JS/JSON）会把上下文一次撑爆，
# 而它在"看结构"这件事上毫无价值。截断并标注，比原样灌进去好。
_READ_MAX_LINE_CHARS = 2000
_READ_MAX_TOTAL_CHARS = 20000   # 与旧版一致的总体上限


@tool("read_file", "读取文本文件，返回带行号的内容（格式 `行号\\t内容`），首行告知文件总行数与本次显示范围。大文件用 offset/limit 分段读。", {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "要读取的文件路径"},
        "offset": {"type": "integer", "description": "从第几行开始读（从 1 开始），默认 1"},
        "limit": {"type": "integer", "description": "最多读多少行，默认 200"},
    },
    "required": ["path"],
}, risk=RISK_READ)
def read_file(path: str, offset: int = 1, limit: int = 200):
    target = _safe_path(path)
    if not os.path.isfile(target):
        return json.dumps({"error": f"文件不存在: {target}"}, ensure_ascii=False)

    with open(target, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()

    total = len(all_lines)
    start = max(1, int(offset))
    limit = max(1, int(limit))
    window = all_lines[start - 1: start - 1 + limit]

    # 首行告知总量与范围：模型据此知道自己"没看全"，可以再用 offset 续读。
    # 这是治"静默截断"的关键——旧版砍到 20000 字符但不说，模型以为文件就这么长。
    if not window:
        header = f"[{path} 共 {total} 行，显示 0 行（offset 超出文件末尾）]"
    else:
        header = f"[{path} 共 {total} 行，显示 {start}-{start + len(window) - 1} 行]"

    out_lines = [header]
    for i, line in enumerate(window, start):
        body = line.rstrip("\n")
        if len(body) > _READ_MAX_LINE_CHARS:
            body = body[:_READ_MAX_LINE_CHARS] + "…(本行已截断)"
        out_lines.append(f"{i:>6}\t{body}")

    text = "\n".join(out_lines)
    if len(text) > _READ_MAX_TOTAL_CHARS:
        text = text[:_READ_MAX_TOTAL_CHARS] + "\n…(输出过长已截断，请用 offset/limit 分段读取)"
    return text


@tool("edit_file", "精确替换文件中的一段文本：old_string 必须与文件内容逐字符一致（含缩进、空行），且在文件中唯一。改已有文件优先用它——不重写整个文件，出错面小得多。改之前必须先 read_file。", {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "要修改的文件路径"},
        "old_string": {"type": "string", "description": "要被替换的原文（必须与文件内容逐字符一致，且在文件中唯一）"},
        "new_string": {"type": "string", "description": "替换后的新文本"},
        "replace_all": {"type": "boolean", "description": "为 true 时替换所有出现；默认 false，要求 old_string 唯一"},
    },
    "required": ["path", "old_string", "new_string"],
}, risk=RISK_WRITE)
def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False):
    target = _safe_path(path)
    if not os.path.isfile(target):
        return json.dumps({"error": f"文件不存在: {target}"}, ensure_ascii=False)

    with open(target, "r", encoding="utf-8") as f:
        content = f.read()

    count = content.count(old_string)
    if count == 0:
        return json.dumps({
            "error": f"old_string 在 {path} 中未找到。请先用 read_file 确认原文（注意缩进与空行必须完全一致）。"
        }, ensure_ascii=False)
    if count > 1 and not replace_all:
        # 不唯一就拒绝，逼模型多带几行上下文——这是防"改错地方"的核心。
        # 自动挑第一个出现看着方便，实际是静默猜意图，猜错代价远大于多问一轮。
        return json.dumps({
            "error": f"old_string 在 {path} 中出现 {count} 次，不唯一。"
                     f"请扩大 old_string 的范围（多带几行上下文）使其唯一，或用 replace_all=true。"
        }, ensure_ascii=False)

    lines_before = content.count("\n") + 1
    new_content = content.replace(old_string, new_string) if replace_all \
        else content.replace(old_string, new_string, 1)
    with open(target, "w", encoding="utf-8") as f:
        f.write(new_content)
    return json.dumps({
        "ok": True, "path": path, "replaced": count if replace_all else 1,
        "lines_before": lines_before, "lines_after": new_content.count("\n") + 1,
    }, ensure_ascii=False)


@tool("write_file", "把文本写入文件（会覆盖已有内容，自动创建父目录）", {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "要写入的文件路径"},
        "content": {"type": "string", "description": "文件内容"},
    },
    "required": ["path", "content"],
}, risk=RISK_WRITE)
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
}, risk=RISK_WRITE)
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
}, risk=RISK_READ)
def recall(keyword: str):
    if not os.path.isfile(MEMORY_FILE):
        return json.dumps({"matches": []})
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if keyword in ln]
    return json.dumps({"matches": lines}, ensure_ascii=False)


@tool("run_shell", "在白名单内执行一条只读检查命令并返回输出（不支持管道/重定向；用于查看目录、查版本、git 状态等）", {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "要执行的命令，例如 'git status' 或 'ls'"},
    },
    "required": ["command"],
}, risk=RISK_EXECUTE)
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

@tool("run_python", "在项目沙箱内运行一个 Python 脚本，返回退出码与输出（写代码任务用：跑测试/验证结果）。只能运行工作目录内的 .py 文件，30 秒超时，输出自动截断。", {
    "type": "object",
    "properties": {
        "script": {"type": "string", "description": "要运行的 .py 脚本路径（相对或绝对路径，必须在工作目录内）"},
        "args": {"type": "string", "description": "可选命令行参数，用空格分隔，默认空"},
    },
    "required": ["script"],
}, risk=RISK_EXECUTE)
def run_python(script: str, args: str = ""):
    # 1) 脚本必须在工作目录内：run_python 是"沙箱内的执行"，不是任意命令执行
    target = _safe_path(script)
    if not os.path.isfile(target):
        return json.dumps({"error": f"脚本不存在: {target}"})
    # 2) 用当前 Python 解释器（就是项目 .venv 的那个）执行；shell=False 不做任何 shell 解释。
    #    cwd 设为脚本所在目录：脚本内 `from xxx import yyy` 能拿到同目录模块。
    parts = [sys.executable, target, *shlex.split(args)]
    try:
        proc = subprocess.run(
            parts, shell=False, capture_output=True, text=True,
            timeout=30, encoding="utf-8", errors="replace",
            cwd=os.path.dirname(target),
        )
    except subprocess.TimeoutExpired:
        # 死循环/算法太慢是最常见的"非语法失败"，给模型一个可行动的提示
        return json.dumps({"error": "运行超时（>30s）——可能死循环或算法太慢，检查循环终止条件/换更快的算法"})
    except Exception as exc:
        return json.dumps({"error": f"执行失败: {exc}"})
    cap = 4000   # 3) 输出截断：traceback/日志可能很长，不要撑爆模型上下文
    return json.dumps({
        "exit_code": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout": (proc.stdout or "")[:cap],
        "stderr": (proc.stderr or "")[:cap],
    }, ensure_ascii=False)


@tool("final_answer", "任务完成时调用它给出最终答复；把结果填进这些结构化字段。summary 必须包含任务的实际成果，禁止只写'已完成/已了解'这类空话", {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "给用户的最终答复：必须包含任务的实际成果（分析结论/关键发现/具体内容/数据），禁止只写'已完成/已了解/已分析'这类空话"},
        "plan": {"type": "array", "items": {"type": "string"}, "description": "执行前制定的计划步骤"},
        "steps": {"type": "array", "items": {"type": "string"}, "description": "执行步骤"},
        "used_tools": {"type": "array", "items": {"type": "string"}, "description": "用到的工具名"},
        "verdict": {"type": "string", "description": "(评审用) ok 或 retry"},
        "feedback": {"type": "string", "description": "(评审用) 给执行者的改进建议"},
        "result": {"type": "string", "description": "(执行用) 关键结果"},
    },
    "required": ["summary", "plan", "steps"],
}, risk=RISK_READ)
def final_answer(summary: str, steps: list[str], used_tools: list[str] | None = None,
                verdict: str | None = None, feedback: str | None = None,
                result: str | None = None):
    return json.dumps({"summary": summary, "steps": steps,
                       "used_tools": used_tools or [],
                       "verdict": verdict, "feedback": feedback,
                       "result": result}, ensure_ascii=False)


def _rag_search(query: str, top_k: int = 3) -> list[dict]:
    """优先用 embedding 版（第9课：语义 + 混合检索）；没装依赖/没建索引时回退词频版。

    两个后端接口一致（search(query, top_k)），上层无感知——这就是"依赖倒置"。
    """
    try:
        from . import knowledge_embed
        results = knowledge_embed.search(query, top_k=top_k)
        if results:
            return results
    except ImportError:
        pass   # fastembed/chromadb 没装 → 回退词频版
    return knowledge.search(query, top_k=top_k)


@tool("kb_search", "在项目知识库中检索与问题相关的段落（RAG）；当问题涉及项目资料/文档/笔记时使用。返回匹配片段和来源。返回的 text 已包含匹配内容，通常无需再调用 read_file。", {
    "type": "object",
    "properties": {"query": {"type": "string", "description": "检索问题或关键词"}},
    "required": ["query"],
}, risk=RISK_READ)
def kb_search(query: str):
    results = _rag_search(query, top_k=3)
    if not results:
        return json.dumps({"error": "知识库为空或没有匹配内容"}, ensure_ascii=False)
    out = [{"source": r["source"], "score": r["score"], "text": r["text"][:300]} for r in results]
    return json.dumps(out, ensure_ascii=False)


def get_tool_schemas():
    return [t.schema() for t in _REGISTRY.values()]


def get_risk(name: str) -> str:
    """查工具的风险等级。未知工具按最危险的 write 处理（保守默认）。"""
    t = _REGISTRY.get(name)
    return t.risk if t is not None else RISK_WRITE


def execute_tool(name, arguments):
    if name not in _REGISTRY:
        return json.dumps({"error": f"未知工具: {name}"})
    return _REGISTRY[name].execute(arguments)
