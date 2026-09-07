from __future__ import annotations

import json
import os
import re


class LLM:
    """所有“模型后端”的公共接口。Agent 只依赖这个接口，不关心背后是 OpenAI、Qwen 还是 mock。"""

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
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
    """
    system = ""
    out = []
    for m in messages:
        role = m["role"]
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
            out.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id", ""),
                    "content": m.get("content", ""),
                }],
            })
    return system, out


def _from_anthropic_response(resp):
    """Anthropic 响应块数组 → OpenAI 风格 dict（content + tool_calls）。

    thinking 块是模型的推理过程，跳过不展示；text 拼成 content，tool_use 转成 tool_calls。
    """
    content_parts, tool_calls = [], []
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
    return {
        "role": "assistant",
        "content": "".join(content_parts) or None,
        "tool_calls": tool_calls or None,
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


def _extract_expression(text):
    match = re.search(r"([0-9+\-*/().\s]+)", text)
    return match.group(1).strip() if match else "2+3"


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
