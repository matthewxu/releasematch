#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
块 A 环境初始化与状态检查（跨平台 Python 版）。

@file scripts/setup_block_a.py
@description
  检查 venv、依赖、accounts.local.json，并打印 workflow status。

  用法：
    python scripts/setup_block_a.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

ACCOUNTS_LOCAL = _ROOT / "workflow" / "torrent_sources" / "accounts.local.json"
ACCOUNTS_EXAMPLE = _ROOT / "workflow" / "torrent_sources" / "accounts.example.json"
VENV_PYTHON = _ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _python_exe() -> str:
    """返回优先使用的 Python 解释器路径。"""
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def main() -> int:
    """执行块 A 检查。"""
    print("=== ReleaseMatch Block A Setup ===\n")

    # A1: venv 提示
    if not VENV_PYTHON.exists():
        print("[A1] .venv not found. Run: python -m venv .venv")
    else:
        print("[A1] .venv exists")

    py = _python_exe()
    try:
        subprocess.run(
            [py, "-m", "pip", "install", "-q", "-r", str(_ROOT / "requirements.txt")],
            check=True,
            cwd=_ROOT,
        )
        subprocess.run([py, "-c", "import requests, yaml; print('[A1] imports OK')"], check=True, cwd=_ROOT)
    except subprocess.CalledProcessError as exc:
        print(f"[A1] pip/import failed: {exc}")
        return 1

    # A2: accounts.local.json
    if not ACCOUNTS_LOCAL.exists():
        shutil.copy(ACCOUNTS_EXAMPLE, ACCOUNTS_LOCAL)
        print(f"[A2] Created {ACCOUNTS_LOCAL.name} — edit api_key")
    else:
        print(f"[A2] {ACCOUNTS_LOCAL.name} exists")

    # A5: status
    print("\n[A5] workflow.run status:")
    subprocess.run([py, "-m", "workflow.run", "status"], cwd=_ROOT)
    print("\n[A5] torrent_sources.run status:")
    subprocess.run([py, "-m", "workflow.torrent_sources.run", "status"], cwd=_ROOT)

    print("\nBlock A done. Remote Jackett: docs/jackett-remote-linode.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
