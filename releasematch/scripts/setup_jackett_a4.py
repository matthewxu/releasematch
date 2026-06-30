#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
块 A4：Jackett 安装后配置与验收（macOS / Linux / Windows 跨平台）。

@file scripts/setup_jackett_a4.py
@description
  检测 9117 端口、写入 accounts.local.json、Torznab 冒烟测试、打印 torrent_sources status。

  用法：
    python scripts/setup_jackett_a4.py
    python scripts/setup_jackett_a4.py --api-key YOUR_KEY
    python scripts/setup_jackett_a4.py --read-config   # 从 Jackett ServerConfig.json 读取 Key
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

ACCOUNTS_PATH = _ROOT / "workflow" / "torrent_sources" / "accounts.local.json"
ACCOUNTS_EXAMPLE = _ROOT / "workflow" / "torrent_sources" / "accounts.example.json"
VENV_PYTHON = _ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _jackett_config_paths() -> list[Path]:
    """
    常见 Jackett ServerConfig.json 路径（按平台）。

    @returns: 候选路径列表
    """
    home = Path.home()
    system = platform.system()
    paths: list[Path] = []
    if system == "Darwin":
        paths.append(home / "Library" / "Application Support" / "Jackett" / "ServerConfig.json")
    elif system == "Windows":
        paths.append(Path(r"C:\ProgramData\Jackett\ServerConfig.json"))
    else:
        paths.append(home / ".config" / "Jackett" / "ServerConfig.json")
    return paths


def _read_api_key_from_jackett_config() -> str:
    """
    从 Jackett 本地 ServerConfig.json 读取 APIKey。

    @returns: API Key 字符串；未找到则返回空串
    """
    for path in _jackett_config_paths():
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            key = str(data.get("APIKey") or "").strip()
            if key:
                return key
        except (OSError, json.JSONDecodeError):
            continue
    return ""


def _port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """
    检测 TCP 端口是否监听。

    @param host: 主机名
    @param port: 端口号
    @param timeout: 超时秒数
    @returns: 端口是否开放
    """
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_probe(url: str, timeout: float = 8.0) -> tuple[bool, str]:
    """
    HTTP 探测 Jackett 根路径。

    @param url: 根 URL
    @param timeout: 超时秒数
    @returns: (是否成功, 详情)
    """
    try:
        with urlopen(url, timeout=timeout) as resp:
            return True, f"HTTP {resp.status}"
    except URLError as exc:
        return False, str(exc.reason if hasattr(exc, "reason") else exc)


def _update_accounts(api_key: str, base_url: str) -> None:
    """
    写入 accounts.local.json 中的 Jackett 配置。

    @param api_key: Jackett API Key
    @param base_url: Jackett 根 URL
    """
    if not ACCOUNTS_PATH.is_file():
        import shutil

        shutil.copy(ACCOUNTS_EXAMPLE, ACCOUNTS_PATH)
    data = json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))
    data.setdefault("jackett", {})
    data["jackett"]["api_key"] = api_key
    data["jackett"]["base_url"] = base_url.rstrip("/")
    ACCOUNTS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _torznab_smoke(base_url: str, api_key: str) -> tuple[bool, str]:
    """
    Torznab 冒烟：Breaking Bad S04E06。

    @param base_url: Jackett 根 URL
    @param api_key: API Key
    @returns: (是否 HTTP 200, 详情)
    """
    url = (
        f"{base_url.rstrip('/')}/api/v2.0/indexers/all/results/torznab/api"
        f"?apikey={api_key}&t=tvsearch&tvdbid=81189&season=4&ep=6&cache=false"
    )
    try:
        with urlopen(url, timeout=45) as resp:
            body = resp.read()
            return True, f"HTTP {resp.status}, bytes={len(body)}"
    except URLError as exc:
        return False, str(exc.reason if hasattr(exc, "reason") else exc)


def _print_install_hints() -> None:
    """打印各平台 Jackett 安装提示。"""
    system = platform.system()
    print("\n[1] Jackett is not running on port 9117. Install/start it first:\n")
    if system == "Darwin":
        print("  brew install jackett")
        print("  brew services start jackett")
    elif system == "Windows":
        print("  winget install --id Jackett.Jackett -e")
        print("  net start Jackett")
    else:
        print("  docker run -d --name jackett -p 9117:9117 \\")
        print("    -v ~/jackett/config:/config linuxserver/jackett:latest")
    print("\n  Dashboard: http://127.0.0.1:9117/UI/Dashboard")


def main(argv: list[str] | None = None) -> int:
    """
    CLI 主入口。

    @param argv: 命令行参数
    @returns: 进程退出码
    """
    parser = argparse.ArgumentParser(description="ReleaseMatch A4 Jackett setup")
    parser.add_argument("--api-key", default="", help="Jackett API Key")
    parser.add_argument("--jackett-url", default="http://127.0.0.1:9117", help="Jackett base URL")
    parser.add_argument(
        "--read-config",
        action="store_true",
        help="从 Jackett ServerConfig.json 自动读取 API Key",
    )
    args = parser.parse_args(argv)

    base_url = args.jackett_url.rstrip("/")
    print("=== ReleaseMatch A4 Jackett Setup ===\n")

    port_ok = _port_open("127.0.0.1", 9117)
    http_ok, http_detail = _http_probe(base_url + "/")
    print(f"[0] Port 9117 : {'OPEN' if port_ok else 'closed'}")
    print(f"    HTTP      : {http_detail if http_ok else 'FAIL - ' + http_detail}")

    if not port_ok:
        _print_install_hints()
        return 1

    api_key = args.api_key.strip()
    if not api_key and args.read_config:
        api_key = _read_api_key_from_jackett_config()
        if api_key:
            print(f"\n[2] Read API Key from Jackett config (len={len(api_key)})")
    if not api_key:
        print("\n[2] Open Dashboard and copy API Key:")
        print(f"    {base_url}/UI/Dashboard")
        api_key = input("Paste Jackett API Key: ").strip()

    if not api_key or api_key == "YOUR_JACKETT_API_KEY":
        print("[FAIL] API Key empty or placeholder.")
        return 1

    _update_accounts(api_key, base_url)
    print(f"[3] Saved API Key to {ACCOUNTS_PATH.name}")

    ok, detail = _torznab_smoke(base_url, api_key)
    print(f"\n[4] Torznab smoke: {'OK ' + detail if ok else 'FAIL ' + detail}")
    if ok:
        print("    Tip: add indexers in Dashboard if items=0")

    py = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    print("\n[5] torrent_sources.run status:")
    subprocess.run([py, "-m", "workflow.torrent_sources.run", "status"], cwd=_ROOT)

    print("\nA4 done. Next: python scripts/poc_phase0.py")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
