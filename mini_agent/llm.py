from __future__ import annotations

import json
import os
import re
import time


class LLM:
    """所有“模型后端”的公共接口。Agent 只依赖这个接口，不关心背后是 OpenAI、Qwen 还是 mock。"""

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        raise NotImplementedError

    def chat_stream(self, messages: list[dict], tools: list[dict]):
        """流式版 chat：yield 文本增量；耗尽后 .value 是完整消息 dict（与 chat() 同构）。

        关键洞察：流式只对"最终答复"有意义——工具调用是结构化 JSON，不需要逐字展示。
        但实现上统一走流式更简单：工具调用轮次不 yield 文本，最后 return 完整消息即可。
        """
        raise NotImplementedError


class OpenAIChatLLM(LLM):
    """调用 OpenAI 兼容的 /chat/completions + function calling。"""

    def __init__(self, model=None, base_url=None, api_key=None):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("需要先安装 openai：pip install openai") from exc
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url or os.environ.get("OPENAI_BASE_URL"),
            timeout=60.0,      # 单次请求最长 60s，防网络抖动超时
            max_retries=2,     # 网络错误自动重试 2 次
        )

    def chat(self, messages, tools):
        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        resp = self.client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        data = {"role": msg.role, "content": msg.content}
        calls = getattr(msg, "tool_calls", None)
        if calls:
            data["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.function.name, "arguments": c.function.arguments},
                }
                for c in calls
            ]
        return data

    def chat_stream(self, messages, tools):
        kwargs = {"model": self.model, "messages": messages, "stream": True}
        if tools:
            kwargs["tools"] = tools
        stream = self.client.chat.completions.create(**kwargs)
        content_parts: list[str] = []
        tool_calls: dict[int, dict] = {}   # index → 累积的 tool_call（流式是分片到达的）
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                content_parts.append(delta.content)
                yield delta.content
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    slot = tool_calls.setdefault(tc.index, {
                        "id": "", "type": "function",
                        "function": {"name": "", "arguments": ""},
                    })
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["function"]["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["function"]["arguments"] += tc.function.arguments
        msg = {"role": "assistant", "content": "".join(content_parts) or None}
        if tool_calls:
            msg["tool_calls"] = [tool_calls[i] for i in sorted(tool_calls)]
        return msg


def _to_anthropic_tools(tools):
    """OpenAI 风格工具声明 → Anthropic 风格（input_schema）。"""
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "input_schema": t["function"]["parameters"],
        }
        for t in tools
    ]


def _to_anthropic_messages(messages):
    """OpenAI 风格消息 → Anthropic 消息；system 单独抽出来返回。

    Anthropic 没有 role=system / role=tool，而是：
    - system 提示词放顶层参数
    - 工具调用是 assistant 消息里的 tool_use 块
    - 工具结果是 user 消息里的 tool_result 块

    **关键约束**：同一 assistant 消息里的**所有** tool_use，其 tool_result 必须放在
    紧随其后的**同一条** user 消息里（每个 tool_use 一个 tool_result 块）。
    Agent 的历史是"每个工具结果各占一条 role=tool"（OpenAI 式），这里把**连续的**
    role=tool 合并成一条 user，避免并行/连续调用多个工具时触发
    "tool_use ids found without tool_result blocks" 400。
    """
    system = ""
    out = []
    i, n = 0, len(messages)
    while i < n:
        m = messages[i]
        role = m.get("role")
        if role == "system":
            system += m.get("content", "")
        elif role == "user":
            out.append({"role": "user", "content": [{"type": "text", "text": m.get("content", "")}]})
        elif role == "assistant":
            blocks = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for call in m.get("tool_calls", []):
                blocks.append({
                    "type": "tool_use",
                    "id": call["id"],
                    "name": call["function"]["name"],
                    "input": json.loads(call["function"]["arguments"] or "{}"),
                })
            out.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            # 把这一整段连续的工具结果合并成一条 user，一条里放多个 tool_result 块
            results = []
            while i < n and messages[i].get("role") == "tool":
                t = messages[i]
                results.append({
                    "type": "tool_result",
                    "tool_use_id": t.get("tool_call_id", ""),
                    "content": t.get("content", ""),
                })
                i += 1
            out.append({"role": "user", "content": results})
            continue   # 上面的 while 已推进 i，跳过末尾的步进
        i += 1
    return system, out


def _from_anthropic_response(resp):
    """Anthropic 响应块数组 → OpenAI 风格 dict（content + tool_calls + thinking）。

    text 拼成 content，tool_use 转成 tool_calls。
    thinking 块是模型的推理过程：**不回传**（History 里没有它，多轮工具循环照旧工作、
    也避免了"thinking 块必须带 signature"的校验），只拿出来塞进返回 dict 的 `thinking`，
    供 agent.py 记入轨迹（做「模型思考」展示）。流式 get_final_message() 也会还原 thinking，
    所以流式/非流式共用本函数都能带上。
    """
    content_parts, tool_calls, thinking_parts = [], [], []
    for block in resp.content:
        if block.type == "text":
            content_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "type": "function",
                "function": {
                    "name": block.name,
                    "arguments": json.dumps(block.input, ensure_ascii=False),
                },
            })
        elif block.type == "thinking":
            thinking_parts.append(getattr(block, "thinking", "") or "")
    return {
        "role": "assistant",
        "content": "".join(content_parts) or None,
        "tool_calls": tool_calls or None,
        "thinking": "".join(thinking_parts) or None,
    }


class AnthropicLLM(LLM):
    """调用 Anthropic Messages API（/v1/messages）。

    Agent 内部统一用 OpenAI 风格的消息/工具格式，这里负责双向翻译：
    - 请求：OpenAI 风格 → Anthropic 的 content 块（text / tool_use / tool_result）
    - 响应：Anthropic 的块数组 → OpenAI 风格的 content + tool_calls
    这样 agent.py 完全不用感知后端差异。
    """

    def __init__(self, model=None, base_url=None, api_key=None, max_tokens=2048):
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError("需要先安装 anthropic：pip install anthropic") from exc
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
        self.max_tokens = max_tokens
        # Ollama 云 / Anthropic 官方都接受 Authorization: Bearer，所以统一用 auth_token
        self.client = Anthropic(
            auth_token=api_key or os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"),
            base_url=base_url or os.environ.get("ANTHROPIC_BASE_URL"),
            timeout=60.0,      # 单次请求最长 60s，防网络抖动超时
            max_retries=2,     # 网络错误自动重试 2 次
        )

    def chat(self, messages, tools):
        system, msgs = _to_anthropic_messages(messages)
        kwargs = {"model": self.model, "max_tokens": self.max_tokens, "messages": msgs}
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = _to_anthropic_tools(tools)
        resp = self.client.messages.create(**kwargs)
        return _from_anthropic_response(resp)

    def chat_stream(self, messages, tools):
        system, msgs = _to_anthropic_messages(messages)
        kwargs = {"model": self.model, "max_tokens": self.max_tokens, "messages": msgs}
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = _to_anthropic_tools(tools)
        with self.client.messages.stream(**kwargs) as stream:
            for chunk in stream:
                # 只转发文本增量；tool_use 的 JSON 分片由 SDK 内部累积，最后统一取
                if chunk.type == "content_block_delta" and chunk.delta.type == "text_delta":
                    yield chunk.delta.text
            final = stream.get_final_message()
        # 完整消息（含 tool_calls）复用非流式的转换逻辑
        return _from_anthropic_response(final)


def _extract_expression(text):
    """从用户话里抠出数学表达式：找第一个数字，再向两边扩展合法的数学字符。

    原写法直接匹配"数字+运算符+括号+空格的字符类"，会先抓到表达式前的空格
    （如"计算 (3+5)*2"会抓到 " "），导致 eval("") 报 invalid syntax。
    改成"数字为中心向两边扩"。
    """
    m = re.search(r"[0-9]", text)
    if not m:
        return "2+3"
    start = m.start()
    while start > 0 and text[start - 1] in "()+-*/.":
        start -= 1
    end = m.end()
    while end < len(text) and text[end] in "0123456789()+-*/.":
        end += 1
    return text[start:end].strip()


class MockLLM(LLM):
    """离线、确定性的 mock。不需要 API key，专门用来演示“Agent 循环”长什么样。"""

    def __init__(self):
        self._calls = 0

    def chat(self, messages, tools):
        self._calls += 1
        last = messages[-1]

        # 上一条是工具结果 → 输出最终答复（真实 LLM 会在这里“看到结果后推理”）
        if last.get("role") == "tool":
            return {
                "role": "assistant",
                "content": f"完成！工具返回：{last.get('content')}\n（这是 mock 的固定回复；换成真实 API 后，它会真正推理再作答）",
            }

        user = last.get("content", "")
        if "计算" in user or "calculator" in user.lower():
            expr = _extract_expression(user)
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "mock_call_1",
                        "type": "function",
                        "function": {"name": "calculator", "arguments": json.dumps({"expression": expr})},
                    }
                ],
            }
        if "时间" in user or "几点" in user or "time" in user.lower():
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": "mock_call_2", "type": "function", "function": {"name": "get_current_time", "arguments": "{}"}}
                ],
            }
        return {"role": "assistant", "content": f"（mock）你说的是：{user}"}

    def chat_stream(self, messages, tools):
        resp = self.chat(messages, tools)   # 复用非流式逻辑，保证行为一致
        content = resp.get("content")
        if content:
            for i in range(0, len(content), 2):   # 按 2 字符切块，模拟逐 token
                yield content[i:i + 2]
                time.sleep(0.02)   # 打字机延迟：让"流式"肉眼可见
        return resp
