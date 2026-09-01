#!/usr/bin/env python3
"""扫描"会被 git 提交的文件"，防止密钥 / 敏感信息入库。

只扫描 git 跟踪的文件，所以本地 .env（已被 gitignore）不会被误报。
用法：python scripts/check_secrets.py   （退出码 0=通过；1=发现问题）
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PATTERNS = {
    "OpenAI API Key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "Anthropic API Key": re.compile(r"sk-ant-[A-Za-z0-9]{20,}"),
    "AWS Access Key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub PAT": re.compile(r"ghp_[A-Za-z0-9]{36}"),
    "Slack Token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "Private Key": re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"),
    "Generic Secret": re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}"),
}

IGNORE_SUFFIXES = {
    ".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".exe",
    ".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p12", ".jks",
    ".log", ".woff", ".woff2", ".zip",
}

TEMPLATE_HINTS = ("sk-...", "<your", "REPLACE", "example", "xxxx")


def scan_text(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    findings = []
    for name, rx in PATTERNS.items():
        for m in rx.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            snippet = text[max(0, m.start() - 4): m.end() + 6]
            if any(h in snippet for h in TEMPLATE_HINTS):
                continue
            findings.append(f"{path.relative_to(ROOT)}: {name} @ 第 {line_no} 行")
    return findings


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
        return [ROOT / p for p in out.splitlines() if p]
    except Exception:
        return []


def main() -> int:
    files = tracked_files()
    if not files:
        print("⚠️ 无法获取 git 跟踪文件（可能未初始化仓库）。请先 git init。")
        return 1
    findings: list[str] = []
    for path in files:
        if path.suffix.lower() in IGNORE_SUFFIXES:
            continue
        findings.extend(scan_text(path))
    if findings:
        print("⚠️ 发现疑似敏感信息，请不要提交到 git：")
        for f in findings:
            print("  -", f)
        print("\n真实 key 请放本地 .env（已 gitignore）；只提交 .env.example 占位符。")
        return 1
    print("✅ 未发现明文密钥 / 敏感信息。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
