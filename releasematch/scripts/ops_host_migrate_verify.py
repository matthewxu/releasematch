#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运维机迁移后验收：对照 docs/17 与 2026-07-28 实迁经验做机器检查。

@file scripts/ops_host_migrate_verify.py
@description
  在目标运维机（或已指向该机权威库的环境）运行，输出 PASS/FAIL/WARN 清单。
  不写库、不改 crontab、不 deploy。

用法：
  cd PROJECT_ROOT   # 含 wrangler.toml / .env / .venv
  .venv/bin/python scripts/ops_host_migrate_verify.py
  .venv/bin/python scripts/ops_host_migrate_verify.py --json
  .venv/bin/python scripts/ops_host_migrate_verify.py --expect-host 8.159.152.227

退出码：
  0 = 无 FAIL（允许 WARN）
  1 = 存在 FAIL
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow.config import PROJECT_ROOT, load_dotenv_file  # noqa: E402


# 完整注释：单条检查结果
CheckResult = Dict[str, Any]


def _run(
    cmd: List[str],
    *,
    cwd: Optional[Path] = None,
    timeout: int = 60,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    """
    运行子进程并捕获输出。

    @param cmd: 命令参数列表
    @param cwd: 工作目录
    @param timeout: 超时秒
    @param env: 可选环境
    @returns: (returncode, stdout, stderr)
    """
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError:
        return 127, "", f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def _ok(name: str, detail: str = "") -> CheckResult:
    """构造 PASS 结果。"""
    return {"name": name, "status": "PASS", "detail": detail}


def _fail(name: str, detail: str) -> CheckResult:
    """构造 FAIL 结果。"""
    return {"name": name, "status": "FAIL", "detail": detail}


def _warn(name: str, detail: str) -> CheckResult:
    """构造 WARN 结果。"""
    return {"name": name, "status": "WARN", "detail": detail}


def check_layout() -> List[CheckResult]:
    """检查 PROJECT_ROOT 关键文件布局。"""
    out: List[CheckResult] = []
    out.append(
        _ok("project_root", str(PROJECT_ROOT))
        if PROJECT_ROOT.is_dir()
        else _fail("project_root", f"missing {PROJECT_ROOT}")
    )
    for rel in ("wrangler.toml", ".env", ".venv/bin/python"):
        path = PROJECT_ROOT / rel
        out.append(
            _ok(f"layout:{rel}", str(path))
            if path.exists()
            else _fail(f"layout:{rel}", f"missing {path}")
        )
    # 常见误用：在 git 根（少一层）跑命令
    git_root_guess = PROJECT_ROOT.parent
    if (git_root_guess / ".git").is_dir() and not (PROJECT_ROOT / ".git").is_dir():
        out.append(
            _ok(
                "layout:nested_ok",
                f"git_root={git_root_guess} project={PROJECT_ROOT}（三层路径正确）",
            )
        )
    return out


def check_env_hygiene() -> List[CheckResult]:
    """
    检查 .env 卫生：等号后空格、CF Token、MySQL 指向本机。

    @description
      GitHub Push Protection 禁止把 CLOUDFLARE_API_TOKEN 推入公开扫描；
      运维机本地必须有非空 Token 才能正式 wrangler。
    """
    out: List[CheckResult] = []
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return [_fail("env:file", "无 .env")]

    raw = env_path.read_text(encoding="utf-8")
    bad_space = []
    for i, line in enumerate(raw.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        if key.strip() == "RM_OPS_PASSWORD" and val.startswith(" "):
            bad_space.append(i)
    if bad_space:
        out.append(
            _fail(
                "env:ops_password_space",
                f".env 行 {bad_space}：RM_OPS_PASSWORD= 后勿留空格（bash source 会当命令）",
            )
        )
    else:
        out.append(_ok("env:ops_password_space", "无危险前导空格"))

    load_dotenv_file(overwrite=True)
    token = (os.environ.get("CLOUDFLARE_API_TOKEN") or "").strip()
    if token:
        out.append(_ok("env:cloudflare_token", f"已设置（len={len(token)}）"))
    else:
        out.append(
            _warn(
                "env:cloudflare_token",
                "CLOUDFLARE_API_TOKEN 为空：增量 cron / Ops 正式上传会失败；在服务器本地填写，勿 push",
            )
        )

    host = (os.environ.get("RM_RELEASE_MYSQL_HOST") or "").strip()
    if host in ("127.0.0.1", "localhost"):
        out.append(_ok("env:mysql_host", host))
    elif host:
        out.append(
            _warn(
                "env:mysql_host",
                f"RM_RELEASE_MYSQL_HOST={host}（方案 B 远程库？确认非双写）",
            )
        )
    else:
        out.append(_fail("env:mysql_host", "未设置 RM_RELEASE_MYSQL_HOST"))
    return out


def check_db_status() -> List[CheckResult]:
    """跑 db status 并解析关键计数。"""
    py = PROJECT_ROOT / ".venv" / "bin" / "python"
    code, stdout, stderr = _run(
        [str(py), "-m", "workflow.run", "db", "status"],
        cwd=PROJECT_ROOT,
        timeout=90,
    )
    text = (stdout + "\n" + stderr).strip()
    if code != 0:
        return [_fail("db:status", text[-500:] or f"exit {code}")]
    # 尽量从输出抠数字；失败则至少 PASS 命令成功
    detail = text[-400:].replace("\n", " | ")
    low = text.lower()
    if "0" in text and ("pages" in low or "media_pages" in low):
        # 弱启发：若明显全 0 则 WARN
        if re.search(r"pages[\"'\s:=]+0\b", low) or re.search(r"\bpages\s*=\s*0\b", low):
            return [_warn("db:status", f"命令成功但 pages 似为 0：{detail}")]
    return [_ok("db:status", detail[:300])]


def check_jackett() -> List[CheckResult]:
    """检查 Jackett 配置一致性与可达性。"""
    out: List[CheckResult] = []
    accounts = PROJECT_ROOT / "workflow" / "torrent_sources" / "accounts.local.json"
    servers = PROJECT_ROOT / "workflow" / "torrent_sources" / "servers.local.json"
    if not accounts.is_file():
        return [_fail("jackett:accounts", "缺少 accounts.local.json")]
    if not servers.is_file():
        return [_fail("jackett:servers", "缺少 servers.local.json")]

    try:
        acc = json.loads(accounts.read_text(encoding="utf-8"))
        srv = json.loads(servers.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [_fail("jackett:json", str(exc))]

    base_url = str((acc.get("jackett") or {}).get("base_url") or "").rstrip("/")
    api_key = str((acc.get("jackett") or {}).get("api_key") or "")
    entry = srv.get("jackett_vps_japan") or {}
    host = str(entry.get("host") or "")
    if not base_url or not api_key:
        out.append(_fail("jackett:accounts_fields", "base_url/api_key 缺失"))
    else:
        out.append(_ok("jackett:accounts_fields", base_url))

    parsed = urlparse(base_url)
    url_host = parsed.hostname or ""
    if host and url_host and host != url_host:
        out.append(
            _fail(
                "jackett:host_mismatch",
                f"accounts base_url host={url_host} ≠ servers.host={host}（一键部署后须跑 A4/同步 Key）",
            )
        )
    elif host:
        out.append(_ok("jackett:host_match", host))
    else:
        out.append(_warn("jackett:servers_host", "servers.local.json 无 host"))

    # 可达性：走项目 status CLI
    py = PROJECT_ROOT / ".venv" / "bin" / "python"
    code, stdout, stderr = _run(
        [str(py), "-m", "workflow.torrent_sources.run", "status"],
        cwd=PROJECT_ROOT,
        timeout=120,
    )
    text = stdout + stderr
    if "reachable" in text.lower() and "true" in text.lower():
        out.append(_ok("jackett:reachable", "status 含 reachable=true"))
    elif code == 0:
        out.append(_warn("jackett:reachable", text[-300:].replace("\n", " | ")))
    else:
        out.append(_fail("jackett:reachable", text[-400:] or f"exit {code}"))
    return out


def check_ops_systemd() -> List[CheckResult]:
    """检查 releasematch-ops.service 与 8090 绑定。"""
    out: List[CheckResult] = []
    code, stdout, stderr = _run(
        ["systemctl", "is-active", "releasematch-ops.service"], timeout=15
    )
    state = (stdout or stderr).strip()
    if state == "active":
        out.append(_ok("ops:systemd", "active"))
    else:
        out.append(_fail("ops:systemd", f"is-active={state!r}"))

    code2, out2, _ = _run(["ss", "-ltn"], timeout=15)
    listen = out2 if code2 == 0 else ""
    if "127.0.0.1:8090" in listen:
        out.append(_ok("ops:bind", "127.0.0.1:8090"))
    else:
        out.append(_fail("ops:bind", "未发现 127.0.0.1:8090 监听"))
    if re.search(r"0\.0\.0\.0:8090|:::8090", listen):
        out.append(_fail("ops:public_bind", "8090 对公网监听，立即改回 127.0.0.1"))
    else:
        out.append(_ok("ops:public_bind", "未见 0.0.0.0:8090"))
    return out


def check_crontab() -> List[CheckResult]:
    """检查业务 cron 是否仅在本机且增量未长期 prepare-only。"""
    out: List[CheckResult] = []
    code, stdout, stderr = _run(["crontab", "-l"], timeout=15)
    text = stdout if code == 0 else ""
    if code != 0 and "no crontab" in (stderr + stdout).lower():
        return [_fail("cron:present", "无 crontab")]
    if code != 0:
        return [_fail("cron:present", (stderr or stdout)[-200:])]

    need = {
        "speedtest_batch_worker": "speedtest_batch_worker",
        "incremental_publish_worker": "incremental_publish_worker",
        "tmdb-sync": "ops tmdb-sync",
    }
    for key, needle in need.items():
        if needle in text:
            out.append(_ok(f"cron:{key}", "present"))
        else:
            out.append(_fail(f"cron:{key}", f"crontab 缺少 {needle}"))

    # 正式期不应长期 --prepare-only
    incr_lines = [
        ln
        for ln in text.splitlines()
        if "incremental_publish_worker" in ln and not ln.strip().startswith("#")
    ]
    if any("--prepare-only" in ln for ln in incr_lines):
        out.append(
            _warn(
                "cron:incremental_prepare_only",
                "增量 cron 仍带 --prepare-only：公网不会随脏页更新；正式上线后去掉",
            )
        )
    elif incr_lines:
        out.append(_ok("cron:incremental_upload", "增量 cron 会走 wrangler（无 --prepare-only）"))
    return out


def check_wrangler() -> List[CheckResult]:
    """检查 wrangler 与 Token 认证。"""
    out: List[CheckResult] = []
    load_dotenv_file(overwrite=True)
    from workflow.ops.actions import (  # noqa: WPS433
        cloudflare_token_ready,
        ensure_cloudflare_deploy_env,
        resolve_wrangler_bin,
    )

    env = ensure_cloudflare_deploy_env()
    bin_path = resolve_wrangler_bin(env)
    if not bin_path:
        out.append(_warn("wrangler:bin", "未找到 wrangler（仅 prepare 可不装）"))
        return out
    out.append(_ok("wrangler:bin", bin_path))
    if not cloudflare_token_ready(env):
        out.append(_warn("wrangler:auth", "无 CLOUDFLARE_API_TOKEN，跳过 whoami"))
        return out
    code, stdout, stderr = _run(
        [bin_path, "whoami"],
        cwd=PROJECT_ROOT,
        timeout=60,
        env=env,
    )
    text = (stdout + stderr).strip()
    if code == 0 and "Account" in text:
        out.append(_ok("wrangler:whoami", text.splitlines()[-3:] and "ok" or "ok"))
    else:
        out.append(_fail("wrangler:whoami", text[-300:]))
    return out


def check_dist_sanity() -> List[CheckResult]:
    """粗检 dist，避免空 dist 正式上传误删公网页。"""
    dist = PROJECT_ROOT / "portal" / "dist"
    if not dist.is_dir():
        return [_warn("dist:dir", "portal/dist 不存在（首次全量 generate 前正常）")]
    n_index = sum(1 for _ in dist.rglob("index.html"))
    if n_index < 10:
        return [
            _warn(
                "dist:sparse",
                f"仅 {n_index} 个 index.html：勿对空/稀疏 dist 做正式 wrangler（会删公网缺页）",
            )
        ]
    return [_ok("dist:index_html", f"{n_index} pages")]


def check_expect_host(expect_host: Optional[str]) -> List[CheckResult]:
    """可选：确认当前机器公网 IP（出网探测）。"""
    if not expect_host:
        return []
    public_ip = ""
    try:
        req = Request(
            "https://api.ipify.org",
            headers={"User-Agent": "ReleaseMatch-OpsVerify/1.0"},
        )
        with urlopen(req, timeout=10) as resp:
            public_ip = resp.read().decode("utf-8", errors="ignore").strip()
    except Exception:  # noqa: BLE001
        public_ip = ""
    if public_ip == expect_host:
        return [_ok("host:identity", expect_host)]
    if public_ip:
        return [
            _warn(
                "host:identity",
                f"expect={expect_host} public={public_ip}（确认是否在正确机器上跑验收）",
            )
        ]
    return [
        _warn(
            "host:identity",
            f"expect={expect_host}；无法探测公网 IP（离线/防火墙），请人工确认",
        )
    ]


def run_all(*, expect_host: Optional[str] = None) -> List[CheckResult]:
    """聚合全部检查。"""
    results: List[CheckResult] = []
    results.extend(check_layout())
    results.extend(check_env_hygiene())
    results.extend(check_db_status())
    results.extend(check_jackett())
    results.extend(check_ops_systemd())
    results.extend(check_crontab())
    results.extend(check_wrangler())
    results.extend(check_dist_sanity())
    results.extend(check_expect_host(expect_host))
    return results


def main() -> int:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(description="运维机迁移验收（只读）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument(
        "--expect-host",
        default=os.environ.get("OPS_HOST", ""),
        help="期望运维机公网 IP（可选）",
    )
    args = parser.parse_args()
    results = run_all(expect_host=(args.expect_host or None))
    fails = [r for r in results if r["status"] == "FAIL"]
    warns = [r for r in results if r["status"] == "WARN"]
    payload = {
        "project_root": str(PROJECT_ROOT),
        "pass": sum(1 for r in results if r["status"] == "PASS"),
        "warn": len(warns),
        "fail": len(fails),
        "checks": results,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"PROJECT_ROOT={PROJECT_ROOT}")
        for r in results:
            print(f"[{r['status']}] {r['name']}: {r['detail']}")
        print(
            f"\n汇总: PASS={payload['pass']} WARN={payload['warn']} FAIL={payload['fail']}"
        )
        if fails:
            print("存在 FAIL：对照 docs/17 对应步骤修复后再跑本脚本。")
        elif warns:
            names = ", ".join(r["name"] for r in warns)
            print(f"无 FAIL；WARN={names}（见 docs/17 §0.5 / 故障速查）。")
        else:
            print("验收通过。")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
