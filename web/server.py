"""第10课 · CodeOps 网页版后端 —— FastAPI + SSE 流式接口

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

# Windows 控制台默认可能是 cp936，导致中文输出乱码；强制用 UTF-8 输出更通用。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 让 `python web/server.py` 和 `uvicorn web.server:app` 都能 import mini_agent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from mini_agent.agent import Agent
from mini_agent.llm import AnthropicLLM, MockLLM, OpenAIChatLLM

# 加载 .env（真实 API key）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def build_agent(provider: str) -> Agent:
    """按 provider 构造 Agent（与 main.py 的 build_agent 同构）。"""
    if provider == "mock":
        return Agent(MockLLM())
    if provider == "anthropic":
        if not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")):
            raise SystemExit("请在 .env 中设置 ANTHROPIC_AUTH_TOKEN（或 ANTHROPIC_API_KEY）")
        return Agent(AnthropicLLM())
    if provider in ("openai", "openai-compatible"):
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("请在 .env 中设置 OPENAI_API_KEY")
        return Agent(OpenAIChatLLM())
    raise SystemExit(f"不支持的 provider: {provider}")


class ChatRequest(BaseModel):
    prompt: str
    # 会话记忆：同一 session_id 复用同一个 Agent 实例（history 跨请求保留），
    # 前端不用每次回传 history，上下文自动续上。
    session_id: str | None = None
    # 可选：无 session_id 时的一次性上下文（user/assistant 文本消息）。
    # 工具调用/结果是每次运行的内部过程，前端不需要回传，Agent 会重新生成。
    history: list[dict] | None = None


def make_app(provider: str = "anthropic") -> FastAPI:
    app = FastAPI(title="CodeOps Agent 网页版", version="0.1.0")

    # 会话记忆：session_id → Agent 实例（history 跨请求保留）。
    # 已知代价：dict 无限增长 + Agent 持有 LLM 客户端，演示够用；
    # 生产要换 Redis 存储 / 加过期清理 / 按会话加锁（并发写 history 会竞争）。
    sessions: dict[str, Agent] = {}
    # 展示用对话记录：session_id → [{role, content}, ...]（10C 刷新恢复历史用）。
    # 为什么不复用 Agent.history？因为 history 是"模型上下文"——含 tool_calls、
    # content=null 的工具轮、无最终答复（final_answer 直接 return 不写回）。
    # 它服务推理，不是人看的对话。展示记录只存 user 提问 + 最终答复，成对出现。
    chat_logs: dict[str, list[dict]] = {}

    # CORS：开发期放开所有来源（Vue 前端跑在另一个端口，跨域访问后端）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root():
        return {"name": "CodeOps Agent 网页版", "provider": provider,
                "endpoints": ["POST /api/chat（SSE 流式）", "GET /test.html（浏览器测试页）"]}

    @app.get("/test.html")
    def test_page():
        # 浏览器测试页：直接消费 SSE 流，验证事件协议（10C 的 Vue 前端用同样方式）
        return FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "test.html"))

    @app.get("/api/sessions")
    def list_sessions():
        # 调试/教学用：看每个会话的上下文长度（验证会话记忆是否真的生效）。
        # mock 不真推理，输出看不出"记住了"，但 history 长度会随轮次增长。
        return {"count": len(sessions),
                "sessions": {sid: len(a.history) for sid, a in sessions.items()}}

    @app.get("/api/sessions/{sid}/history")
    def get_history(sid: str):
        # 读会话的展示用对话记录：前端刷新后恢复聊天记录用（10C）。
        # 读 chat_logs（user 提问 + 最终答复），不读 Agent.history——
        # 后者含 tool 消息 / content=null / 无最终答复，是人不可读的模型上下文。
        return {"sid": sid, "messages": chat_logs.get(sid, [])}

    @app.post("/api/chat")
    async def chat(req: ChatRequest):
        if req.session_id and req.session_id in sessions:
            # 会话命中：复用 Agent，history 已经在里面，忽略请求里的 history
            agent = sessions[req.session_id]
        else:
            agent = build_agent(provider)
            if req.history:
                # 只接受 user/assistant 文本消息；工具消息是内部过程，不接收
                agent.history = [{"role": m["role"], "content": m["content"]}
                                 for m in req.history if m.get("role") in ("user", "assistant")]
            if req.session_id:
                sessions[req.session_id] = agent   # 新会话，存起来供下次复用
                chat_logs[req.session_id] = []     # 并建立它的展示记录（10C）

        def event_stream():
            gen = agent.run(req.prompt, stream=True, verbose=False)
            try:
                while True:
                    event = next(gen)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except StopIteration as e:
                # 生成器 return 值 = 最终答复，补发一个 done 事件（前端不用抓 StopIteration）
                final = e.value
                yield f"data: {json.dumps({'type': 'done', 'text': final}, ensure_ascii=False)}\n\n"
                # 完成时把 user 提问 + 最终答复记入展示记录（供刷新恢复）；
                # 工具事件不记——重新对话时会重新产生。无 session_id 则不记（无状态模式）。
                if req.session_id:
                    chat_logs[req.session_id].extend([
                        {"role": "user", "content": req.prompt},
                        {"role": "assistant", "content": final},
                    ])
            except Exception as e:   # API 超时/网络错误等：转成 error 事件，前端能展示
                yield f"data: {json.dumps({'type': 'error', 'text': str(e)}, ensure_ascii=False)}\n\n"
            finally:
                gen.close()   # 客户端断开时，顺手关掉内部生成器，不留悬挂

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return app


def main():
    parser = argparse.ArgumentParser(description="CodeOps Agent 网页版后端")
    parser.add_argument("--provider", default="anthropic", choices=["mock", "anthropic", "openai"])
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(make_app(args.provider), host="127.0.0.1", port=args.port)


# uvicorn web.server:app 用的全局实例；provider 可用环境变量 AGENT_PROVIDER 覆盖
app = make_app(os.environ.get("AGENT_PROVIDER", "anthropic"))

if __name__ == "__main__":
    main()
