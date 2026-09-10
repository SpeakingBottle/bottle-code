"""第10课 · Bottle Code 网页版后端 —— FastAPI + SSE 流式接口

把第10A 的流式事件协议（delta/tool/result）暴露成 HTTP 接口：
前端 POST /api/chat，后端把 Agent 的事件逐个转成 SSE 推给前端。

SSE（Server-Sent Events）协议格式：
  data: <json>\n\n
每条事件以 data: 开头、空行结尾。浏览器 EventSource 原生支持
（但 EventSource 只支持 GET，POST 要用 fetch + ReadableStream，见 web/test.html）。

事件协议（与 run(stream=True) 一致，多一个 done）：
  {"type": "delta", "text": ...}     —— 文本增量
  {"type": "tool", "name": ..., "args": ...}    —— 工具调用开始
  {"type": "result", "name": ..., "text": ...}  —— 工具结果
  {"type": "done", "text": ...}      —— 最终答复（后端从 StopIteration.value 拿到后补发）
  {"type": "error", "text": ...}     —— 运行出错（API 挂了等）

用法：
  .venv/Scripts/python.exe web/server.py --provider mock --port 8000
  .venv/Scripts/python.exe web/server.py --provider anthropic --port 8000
  # 或（uvicorn 方式，provider 用环境变量 AGENT_PROVIDER 控制）
  .venv/Scripts/python.exe -m uvicorn web.server:app --port 8000
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Windows 控制台默认可能是 cp936，导致中文输出乱码；强制用 UTF-8 输出更通用。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 让 `python web/server.py` 和 `uvicorn web.server:app` 都能 import mini_agent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from mini_agent.agent import Agent
from mini_agent.llm import AnthropicLLM, MockLLM, OpenAIChatLLM

# 加载 .env（真实 API key）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# 网页版给更宽的步数上限（④）：命令行默认也调到 24，但"分析整个项目"这类的宽任务
# 要逐文件 read_file，24 步仍可能不够就 timeout。网页交互放宽到 48，
# 让 Agent 能走完一个较真实的码读+归纳流程。代价是单任务更长/更多 token——教学演示可接受。
WEB_MAX_STEPS = 48


# ---- 会话持久化（⑤）：把会话列表/展示记录/模型上下文/轨迹落盘，重启后保留 ----
# 为什么存四样？
#   session_meta  会话列表要展示的元信息（名字/创建时间/最近活动）
#   chat_logs     人看的对话记录（user 提问 + 最终答复，10C 刷新恢复用）
#   histories     模型上下文（Agent.history）——重启后内存 Agent 没了，
#                 靠它重建 Agent，才能"回到之前的对话继续聊"而不是失忆。
#   traces        会话轨迹（Agent.trace）——重启后旧会话的轨迹也能在轨迹面板看到。
#                 代价：轨迹含每步的提示词快照（_render_messages 截断到 2000 字），
#                 长会话会让 sessions.json 变大；单文件全量读写，会话多了会慢，
#                 生产换 SQLite/Redis（与 AGENTS.md 已知代价一致）。
SESSION_STORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions.json")


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _load_store() -> tuple[dict, dict, dict, dict]:
    """启动时读磁盘会话存储；文件不存在/损坏则空启动（不崩）。"""
    try:
        with open(SESSION_STORE, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}, {}, {}, {}
    sessions_data = data.get("sessions", {})
    meta = {sid: s.get("meta", {}) for sid, s in sessions_data.items()}
    chat_logs = {sid: s.get("chat_logs", []) for sid, s in sessions_data.items()}
    histories = {sid: s.get("history", []) for sid, s in sessions_data.items()}
    traces = {sid: s.get("trace", []) for sid, s in sessions_data.items()}
    return meta, chat_logs, histories, traces


def _save_store(meta: dict, chat_logs: dict, histories: dict, traces: dict) -> None:
    """把四个内存 dict 写回磁盘。先写临时文件再 os.replace 原子替换：
    写一半崩溃不会留下半个 JSON（要么旧文件完整，要么新文件完整）。"""
    data = {"version": 1, "sessions": {}}
    for sid, m in meta.items():
        data["sessions"][sid] = {
            "meta": m,
            "chat_logs": chat_logs.get(sid, []),
            "history": histories.get(sid, []),
            "trace": traces.get(sid, []),
        }
    tmp = SESSION_STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SESSION_STORE)


def build_agent(provider: str) -> Agent:
    """按 provider 构造 Agent（与 main.py 的 build_agent 同构）。"""
    if provider == "mock":
        return Agent(MockLLM(), max_steps=WEB_MAX_STEPS)
    if provider == "anthropic":
        if not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")):
            raise SystemExit("请在 .env 中设置 ANTHROPIC_AUTH_TOKEN（或 ANTHROPIC_API_KEY）")
        return Agent(AnthropicLLM(), max_steps=WEB_MAX_STEPS)
    if provider in ("openai", "openai-compatible"):
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("请在 .env 中设置 OPENAI_API_KEY")
        return Agent(OpenAIChatLLM(), max_steps=WEB_MAX_STEPS)
    raise SystemExit(f"不支持的 provider: {provider}")


def clean_final_answer(raw: str) -> str:
    """把 final_answer 的结构化 JSON 变成人看的干净答复。

    Agent 的最终答复是 final_answer 参数的完整 JSON dump（summary/plan/steps/
    used_tools/verdict/feedback/result），直接展示会"输出一堆 summary 等"。
    这里只提取 summary（模型通常把答案写在这里，如 "100/4 = 25"）；
    若 result 存在且没被 summary 包含（如 summary="计算完成"、result="5"），
    再补一行 result。解析失败（纯文本答复）原样返回。

    注意：只改"展示层"，不动 Agent 核心——多 Agent 的 Orchestrator 还要
    解析完整 JSON（verdict/feedback/steps）做评审，改了会破坏它。
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
    if not isinstance(data, dict) or not data.get("summary"):
        return raw
    summary = data["summary"]
    result = data.get("result")
    if result and str(result) not in summary:
        summary += "\n\n" + str(result)
    return summary


class ChatRequest(BaseModel):
    prompt: str
    # 会话记忆：同一 session_id 复用同一个 Agent 实例（history 跨请求保留），
    # 前端不用每次回传 history，上下文自动续上。
    session_id: str | None = None
    # 可选：无 session_id 时的一次性上下文（user/assistant 文本消息）。
    # 工具调用/结果是每次运行的内部过程，前端不需要回传，Agent 会重新生成。
    history: list[dict] | None = None


class RenameRequest(BaseModel):
    # ⑤ 会话改名请求体。注意：必须定义在模块级，不能嵌在 make_app 里——
    # 文件顶部有 from __future__ import annotations，注解是惰性字符串，
    # FastAPI 靠 get_type_hints 在"模块命名空间"按名字解析；函数内的局部类
    # 模块级查不到，会退化成 ForwardRef（PATCH 被当成 query 参数 + OpenAPI 500）。
    name: str


def make_app(provider: str = "anthropic") -> FastAPI:
    app = FastAPI(title="Bottle Code 网页版", version="0.1.0")

    # 会话存储（⑤）：四份数据 + 内存 Agent 实例。
    #   session_meta  sid → {name, created_at, updated_at}（会话列表展示用）
    #   chat_logs     sid → [{role, content}]（人看的对话记录，10C 刷新恢复用）
    #   histories     sid → [消息]（模型上下文，重启后重建 Agent 用）
    #   traces        sid → [轨迹事件]（Agent.trace，重启后轨迹面板仍可见）
    #   sessions      sid → Agent 实例（内存态；重启后为空，命中 histories 时重建）
    # 为什么不复用 Agent.history 当展示记录？因为 history 是"模型上下文"——含
    # tool_calls、content=null 的工具轮、无最终答复（final_answer 直接 return
    # 不写回）。它服务推理，不是人看的对话。展示记录只存 user 提问 + 最终答复。
    session_meta, chat_logs, histories, traces = _load_store()
    sessions: dict[str, Agent] = {}

    # CORS：开发期放开所有来源（Vue 前端跑在另一个端口，跨域访问后端）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root():
        return {"name": "Bottle Code 网页版", "provider": provider,
                "endpoints": ["POST /api/chat（SSE 流式）", "GET /test.html（浏览器测试页）"]}

    @app.get("/test.html")
    def test_page():
        # 浏览器测试页：直接消费 SSE 流，验证事件协议（10C 的 Vue 前端用同样方式）
        return FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "test.html"))

    @app.get("/api/sessions")
    def list_sessions():
        # ⑤ 会话列表：从元信息 + 展示记录组装，按最近活动倒序。
        # 消息数用 chat_logs（人看的记录）而不是 Agent.history（模型上下文）——
        # 后者含工具轮，数出来不是"聊了几轮"。
        items = []
        for sid, m in session_meta.items():
            logs = chat_logs.get(sid, [])
            items.append({
                "sid": sid,
                "name": m.get("name") or "未命名会话",
                "turns": len(logs) // 2,          # 一轮 = 一问一答
                "messages": len(logs),
                "created_at": m.get("created_at", ""),
                "updated_at": m.get("updated_at", ""),
            })
        items.sort(key=lambda x: x["updated_at"], reverse=True)
        return {"count": len(items), "sessions": items}

    @app.patch("/api/sessions/{sid}")
    def rename_session(sid: str, req: RenameRequest):
        # ⑤ 改名：只改元信息，不动对话内容/模型上下文
        if sid not in session_meta:
            return JSONResponse(status_code=404, content={"error": "会话不存在"})
        name = req.name.strip()
        if not name:
            return JSONResponse(status_code=400, content={"error": "名称不能为空"})
        session_meta[sid]["name"] = name
        session_meta[sid]["updated_at"] = _now()
        _save_store(session_meta, chat_logs, histories, traces)
        return {"ok": True, "sid": sid, "name": name}

    @app.delete("/api/sessions/{sid}")
    def delete_session(sid: str):
        # ⑤ 删除：四份数据一起清（内存 Agent 实例也释放）
        if sid not in session_meta:
            return JSONResponse(status_code=404, content={"error": "会话不存在"})
        sessions.pop(sid, None)
        chat_logs.pop(sid, None)
        histories.pop(sid, None)
        traces.pop(sid, None)
        session_meta.pop(sid, None)
        _save_store(session_meta, chat_logs, histories, traces)
        return {"ok": True, "sid": sid}

    @app.get("/api/sessions/{sid}/history")
    def get_history(sid: str):
        # 读会话的展示用对话记录：前端刷新后恢复聊天记录用（10C）。
        # 读 chat_logs（user 提问 + 最终答复），不读 Agent.history——
        # 后者含 tool 消息 / content=null / 无最终答复，是人不可读的模型上下文。
        return {"sid": sid, "messages": chat_logs.get(sid, [])}

    @app.get("/api/sessions/{sid}/trace")
    def get_trace(sid: str):
        # ④ 会话轨迹展示入口：读该会话 Agent 实例的内存轨迹（第7课 format_trace 的数据源）。
        # 为什么读 trace 而不是 logs/agent.jsonl？trace 天然按会话隔离
        #（sessions[sid] → Agent.trace），而 JSONL 是全局 append-only、事件里没有
        # session_id，按会话过滤得额外加字段；web 后端也没接 audit，读它更直接。
        # 重启后内存 Agent 没了：回退到落盘的 traces（⑤ 持久化）。
        agent = sessions.get(sid)
        if agent:
            return {"sid": sid, "trace": agent.trace}
        return {"sid": sid, "trace": traces.get(sid, [])}

    @app.post("/api/chat")
    async def chat(req: ChatRequest):
        if req.session_id and req.session_id in sessions:
            # 会话命中：复用 Agent，history 已经在里面，忽略请求里的 history
            agent = sessions[req.session_id]
        elif req.session_id and req.session_id in histories:
            # ⑤ 重启后恢复：内存 Agent 没了，用落盘的模型上下文重建（记忆还在），
            # 轨迹也一并恢复（重启后旧会话的轨迹面板仍可见）
            agent = build_agent(provider)
            agent.history = list(histories[req.session_id])
            agent.trace = list(traces.get(req.session_id, []))
            sessions[req.session_id] = agent
        else:
            agent = build_agent(provider)
            if req.history:
                # 只接受 user/assistant 文本消息；工具消息是内部过程，不接收
                agent.history = [{"role": m["role"], "content": m["content"]}
                                 for m in req.history if m.get("role") in ("user", "assistant")]
            if req.session_id:
                sessions[req.session_id] = agent   # 新会话，存起来供下次复用
                chat_logs[req.session_id] = []     # 并建立它的展示记录（10C）
                histories[req.session_id] = []     # ⑤ 模型上下文落盘副本
                traces[req.session_id] = []        # ⑤ 轨迹落盘副本
                # ⑤ 自动命名：用第一条消息截断（用户之后可手动改名，不再覆盖）
                session_meta[req.session_id] = {
                    "name": req.prompt[:20] + ("…" if len(req.prompt) > 20 else ""),
                    "created_at": _now(),
                    "updated_at": _now(),
                }
                _save_store(session_meta, chat_logs, histories, traces)

        def event_stream():
            gen = agent.run(req.prompt, stream=True, verbose=False)
            try:
                while True:
                    event = next(gen)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except StopIteration as e:
                # 生成器 return 值 = 最终答复，补发一个 done 事件（前端不用抓 StopIteration）。
                # 先 clean：final_answer 的 JSON dump 只留 summary（+ 必要的 result），
                # 前端和 chat_logs 拿到的都是人看的干净答复。
                final = clean_final_answer(e.value)
                yield f"data: {json.dumps({'type': 'done', 'text': final}, ensure_ascii=False)}\n\n"
                # 完成时把 user 提问 + 最终答复记入展示记录（供刷新恢复）；
                # 工具事件不记——重新对话时会重新产生。无 session_id 则不记（无状态模式）。
                if req.session_id:
                    chat_logs[req.session_id].extend([
                        {"role": "user", "content": req.prompt},
                        {"role": "assistant", "content": final},
                    ])
                    # ⑤ 模型上下文/轨迹同步到落盘副本 + 刷新活动时间，然后写盘。
                    # 注意：只在 done（运行成功）时同步——运行中途出错（API 挂等）
                    # 时 history 里只有 user 消息没有答复，同步一个半截上下文没意义。
                    histories[req.session_id] = list(agent.history)
                    traces[req.session_id] = list(agent.trace)
                    session_meta[req.session_id]["updated_at"] = _now()
                    _save_store(session_meta, chat_logs, histories, traces)
            except Exception as e:   # API 超时/网络错误等：转成 error 事件，前端能展示
                yield f"data: {json.dumps({'type': 'error', 'text': str(e)}, ensure_ascii=False)}\n\n"
            finally:
                gen.close()   # 客户端断开时，顺手关掉内部生成器，不留悬挂

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return app


def main():
    parser = argparse.ArgumentParser(description="Bottle Code 网页版后端")
    parser.add_argument("--provider", default="anthropic", choices=["mock", "anthropic", "openai"])
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(make_app(args.provider), host="127.0.0.1", port=args.port)


# uvicorn web.server:app 用的全局实例；provider 可用环境变量 AGENT_PROVIDER 覆盖
app = make_app(os.environ.get("AGENT_PROVIDER", "anthropic"))

if __name__ == "__main__":
    main()
