#!/usr/bin/env python3
"""扫描仓库，防止把密钥 / 敏感信息写进会被提交的文件。

用法：python scripts/check_secrets.py
退出码：0 = 未发现；1 = 发现疑似敏感信息。
也可以把它挂到 git pre-commit hook：见 .githooks/pre-commit。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

PATTERNS = {
    "OpenAI API Key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "Anthropic API Key": re.compile(r"sk-ant-[A-Za-z0-9]{20,}"),
    "AWS Access Key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub PAT": re.compile(r"ghp_[A-Za-z0-9]{36}"),
    "Slack Token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "Private Key": re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"),
    "Generic Secret": re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}"),
}

IGNORE_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env", "node_modules",
    ".idea", ".vscode", "dist", "build", "htmlcov", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "memory", "data", "chroma", "secrets",
}
IGNORE_SUFFIXES = {
    ".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".exe",
    ".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p12", ".jks",
    ".log", ".woff", ".woff2", ".zip",
}


def scan_text(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    findings = []
    for name, rx in PATTERNS.items():
        for m in rx.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            findings.append(f"{path.relative_to(ROOT)}: {name} @ 第 {line_no} 行")
    return findings


def main() -> int:
    findings: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fn in filenames:
            path = Path(dirpath) / fn
            if path.suffix.lower() in IGNORE_SUFFIXES:
                continue
            if path.name == ".env":
                if path.exists() and path.read_text(encoding="utf-8", errors="ignore").strip():
                    findings.append(f"{path.relative_to(ROOT)}: 检测到非空的 .env 文件（请确认它已被 .gitignore 忽略，不要提交）")
                continue
            findings.extend(scan_text(path))

    if findings:
        print("⚠️ 发现疑似敏感信息，请不要提交到 git：")
        for f in findings:
            print("  -", f)
        print("\n处理建议：把真实密钥放进本地 .env（已 gitignore），提交时只提交 .env.example。")
        return 1
    print("✅ 未发现明文密钥 / 敏感信息。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
