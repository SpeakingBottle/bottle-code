from __future__ import annotations

import os
import re


class GuardrailError(Exception):
    """违反安全/权限约束时的异常。"""


# ---- 路径沙箱：Agent 只能读写工作目录之内 ----
def safe_path(path: str, base: str | None = None) -> str:
    """返回规范化后的绝对路径；若越出 base，抛 GuardrailError（拒绝）。"""
    base = os.path.abspath(base or os.environ.get("AGENT_WORKDIR", os.getcwd()))
    raw = os.path.abspath(os.path.join(base, path))
    if os.path.commonpath([raw, base]) != base:
        raise GuardrailError(f"路径 {path!r} 超出工作目录，已拒绝")
    return raw


# ---- 敏感信息检测：防止密钥泄漏进轨迹 / 结果 ----
# 朴素但要够用；真正的生产级会用更全面的规则 + 阈值。
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),      # OpenAI / DeepSeek 风格 key
    re.compile(r"[A-Za-z0-9+/]{32,}={0,2}"),  # 长 base64 令牌
    re.compile(r"(?i)(api[_-]?key|secret|password)\s*=\s*\S+"),  # k=v 形式
]


def find_secrets(text: str) -> list[str]:
    """在给定文本里找出疑似密钥，返回匹配列表（空 = 安全）。"""
    hits: list[str] = []
    for pat in SECRET_PATTERNS:
        for m in pat.finditer(text or ""):
            hits.append(m.group(0))
    return hits


def redact_secrets(text: str) -> str:
    """把疑似密钥替换成 [REDACTED]。"""
    for pat in SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text or "")
    return text
