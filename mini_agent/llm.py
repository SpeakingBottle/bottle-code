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
