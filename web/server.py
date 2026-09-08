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
    # 可选：多轮对话的上下文（user/assistant 文本消息）。
    # 工具调用/结果是每次运行的内部过程，前端不需要回传，Agent 会重新生成。
    history: list[dict] | None = None


def make_app(provider: str = "anthropic") -> FastAPI:
    app = FastAPI(title="CodeOps Agent 网页版", version="0.1.0")

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

    @app.post("/api/chat")
    async def chat(req: ChatRequest):
        agent = build_agent(provider)
        if req.history:
            # 只接受 user/assistant 文本消息；工具消息是内部过程，不接收
            agent.history = [{"role": m["role"], "content": m["content"]}
                             for m in req.history if m.get("role") in ("user", "assistant")]

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
