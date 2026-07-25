#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Linode VPS 生命周期 CLI：创建（购买）、查询 IP、列出、删除。

@file workflow/torrent_sources/linode_vps.py
@description
  与 linode.example.json / linode.local.json 同目录的独立 CLI，
  不依赖 ReleaseMatch 业务包（workflow.*），可供外部程序 / cron / CI
  以子进程方式调用。默认人类可读输出；加 --json 时 stdout 仅一行 JSON。

  依赖：
    pip install -r workflow/torrent_sources/requirements-linode.txt

  Token 读取优先级（高 → 低）：
    1. 环境变量 LINODE_TOKEN
    2. --config 指定的 JSON
    3. 自动查找同目录 linode.local.json（见 docs/linode-vps-lifecycle.md）
       模板：workflow/torrent_sources/linode.example.json
       本地：workflow/torrent_sources/linode.local.json（已 gitignore，不上传 GitHub）

  用法示例：
    cd workflow/torrent_sources
    cp linode.example.json linode.local.json   # 编辑填入 token
    python linode_vps.py create --region jp-osa --label demo
    python linode_vps.py create --json --region jp-osa
    python linode_vps.py ip --label demo
    python linode_vps.py list --json
    python linode_vps.py delete --label demo --yes
    python linode_vps.py params                 # 枚举 region/type/image
    python linode_vps.py params --kind region --region-filter jp
    python linode_vps.py params --kind type --type-filter nanode
    python linode_vps.py params --kind image --vendor debian --json
    python linode_vps.py defaults --json          # 输出配置中的 label/规格

  文档：docs/linode-vps-lifecycle.md
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import string
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 退出码约定（外部调用方应依赖这些码，勿解析文案）
# ---------------------------------------------------------------------------
EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

# 默认规格：日本大阪 + Debian 12 + Nanode 1GB（约 $5/月，Linode 最低档）
DEFAULT_TYPE = "g6-nanode-1"  # 1 vCPU / 1GB RAM / 25GB SSD / 1TB 流量
DEFAULT_REGION = "jp-osa"  # Japan, Osaka
DEFAULT_IMAGE = "linode/debian12"
DEFAULT_WAIT_SECONDS = 240  # 与 linode_api4 PollingGroup 默认 timeout 对齐
# create/list 未配置 http_timeout 时的默认（秒）；仅约束「单次 HTTP」，不等待 provisioning
DEFAULT_HTTP_TIMEOUT = 120.0
# Event / status 轮询间隔（秒）；与 SDK PollingGroup 默认 interval 对齐
DEFAULT_POLL_INTERVAL = 5

# 本脚本与配置同目录：workflow/torrent_sources/
_SCRIPT_DIR = Path(__file__).resolve().parent
# 推荐本地配置路径（与脚本同目录；已在 .gitignore）
_DEFAULT_LOCAL_CONFIG = _SCRIPT_DIR / "linode.local.json"
_EXAMPLE_CONFIG = _SCRIPT_DIR / "linode.example.json"
_REQUIREMENTS = _SCRIPT_DIR / "requirements-linode.txt"


def _emit(payload: dict[str, Any], *, as_json: bool, human_lines: list[str] | None = None) -> None:
    """
    向 stdout 输出结果。

    @param payload: 结构化结果（--json 时整包打印）
    @param as_json: True 时只打印一行 JSON
    @param human_lines: 人类可读行；None 时用 payload 的 key=value
    """
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return
    if human_lines is not None:
        for line in human_lines:
            print(line)
        return
    for key, value in payload.items():
        if key in ("ok", "action"):
            continue
        print(f"{key}={value}")


def _err(message: str) -> None:
    """将诊断信息写到 stderr，避免污染 --json 的 stdout（立即 flush 供 Ops 轮询）。"""
    print(message, file=sys.stderr, flush=True)


def candidate_config_paths(explicit: str | None = None) -> list[Path]:
    """
    按优先级列出待查找的 linode.local.json 路径。

    @param explicit: --config 指定的路径；若给出则仅尝试该路径
    @return: Path 列表（已展开为绝对路径）
    """
    if explicit:
        return [Path(explicit).expanduser().resolve()]
    paths: list[Path] = [
        _DEFAULT_LOCAL_CONFIG,  # 与脚本同目录（优先）
        Path.cwd() / "linode.local.json",
    ]
    # 去重并保持顺序
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(resolved)
    return ordered


def load_config_file(path: Path) -> dict[str, Any]:
    """
    读取并解析 linode 本地 JSON 配置。

    @param path: 配置文件路径
    @return: 字典；文件非法时抛出 RuntimeError
    """
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except FileNotFoundError as exc:
        raise RuntimeError(f"配置文件不存在: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"配置文件 JSON 无效: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"配置文件根节点须为对象: {path}")
    return data


def resolve_config(explicit: str | None = None) -> tuple[dict[str, Any], Path | None]:
    """
    加载本地配置（若存在）。

    @param explicit: --config 路径；显式指定时文件必须存在
    @return: (配置字典, 实际使用的路径或 None)
    """
    paths = candidate_config_paths(explicit)
    if explicit:
        path = paths[0]
        return load_config_file(path), path

    for path in paths:
        if path.is_file():
            return load_config_file(path), path
    return {}, None


def extract_token(config: dict[str, Any]) -> str:
    """
    从配置字典提取 token（支持 token / LINODE_TOKEN 字段名）。

    @param config: 已加载的配置
    @return: 去空白后的 token；无则空串
    """
    for key in ("token", "LINODE_TOKEN", "linode_token"):
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def extract_http_timeout(config: dict[str, Any]) -> float | None:
    """
    解析 HTTP 超时：环境变量 LINODE_HTTP_TIMEOUT 优先，其次配置 http_timeout。

    配置为 null / 缺省时返回 ``DEFAULT_HTTP_TIMEOUT``（避免 create 在 API 已成功后
    仍无限阻塞在 HTTP 读上）。显式 ``0`` 表示不设超时（不推荐）。

    @param config: 已加载的配置
    @return: 秒数；显式 0 时为 None（无超时）
    """
    env = (os.environ.get("LINODE_HTTP_TIMEOUT") or "").strip()
    if env:
        try:
            val = float(env)
            return None if val <= 0 else val
        except ValueError:
            _err(f"忽略无效 LINODE_HTTP_TIMEOUT={env!r}")
    raw = config.get("http_timeout")
    if raw is None or raw == "":
        return DEFAULT_HTTP_TIMEOUT
    try:
        val = float(raw)
        return None if val <= 0 else val
    except (TypeError, ValueError):
        _err(f"忽略无效 http_timeout={raw!r}")
        return DEFAULT_HTTP_TIMEOUT


def require_token(config: dict[str, Any], config_path: Path | None) -> str:
    """
    解析 Token：环境变量 > 本地 config；均无则 USAGE 退出。

    @param config: 本地配置字典
    @param config_path: 实际加载的配置路径（用于报错提示）
    @return: Token 字符串
    """
    token = (os.environ.get("LINODE_TOKEN") or "").strip()
    if token:
        return token

    token = extract_token(config)
    if token and token not in (
        "YOUR_LINODE_PERSONAL_ACCESS_TOKEN",
        "YOUR_TOKEN",
    ):
        return token

    example = _EXAMPLE_CONFIG
    local = _DEFAULT_LOCAL_CONFIG
    _err(
        "未找到 Linode Token。请任选其一：\n"
        "  1) export LINODE_TOKEN=...\n"
        f"  2) cp {example} {local}\n"
        "     编辑 linode.local.json 填入 token（该文件已 gitignore，不会上传 GitHub）\n"
        "  3) python workflow/torrent_sources/linode_vps.py --config /path/to/linode.local.json ..."
    )
    if config_path and extract_token(config):
        _err(f"提示: 已读到 {config_path}，但 token 仍是占位符，请替换为真实值")
    raise SystemExit(EXIT_USAGE)


def _import_sdk():
    """
    延迟导入 linode_api4，给出可操作的安装提示。

    @return: (LinodeClient 类, Instance 类)
    """
    try:
        from linode_api4 import Instance, LinodeClient
    except ImportError:
        _err(
            "未安装 linode_api4。请执行：\n"
            f"  pip install -r {_REQUIREMENTS}\n"
            "  或：pip install 'linode_api4>=5.0.0'"
        )
        raise SystemExit(EXIT_USAGE) from None
    return LinodeClient, Instance


def get_client(config: dict[str, Any], config_path: Path | None):
    """
    构造已认证的 LinodeClient。

    先校验 Token（便于提示本地 config），再导入 SDK。

    @param config: 本地配置
    @param config_path: 配置文件路径
    @return: LinodeClient 实例
    """
    token = require_token(config, config_path)
    LinodeClient, _Instance = _import_sdk()
    timeout = extract_http_timeout(config)
    if timeout is not None:
        try:
            return LinodeClient(token, timeout=timeout)
        except TypeError:
            # 旧版 SDK 可能无 timeout 参数
            return LinodeClient(token)
    return LinodeClient(token)


def create_defaults_from_config(config: dict[str, Any]) -> dict[str, str]:
    """
    从 config.defaults 读取 create 默认 label/region/type/image。

    @param config: 本地配置
    @return: 仅含非空字符串字段的字典
    """
    raw = config.get("defaults")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key in ("label", "region", "type", "image"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            out[key] = value.strip()
    return out


def effective_create_defaults(config: dict[str, Any]) -> dict[str, str]:
    """
    合并配置与内置默认，得到 create 实际将使用的参数（供 defaults 子命令输出）。

    @param config: 本地配置
    @return: 含 label/region/type/image 的字典
    """
    cfg = create_defaults_from_config(config)
    return {
        "label": cfg.get("label") or "",
        "region": cfg.get("region") or DEFAULT_REGION,
        "type": cfg.get("type") or DEFAULT_TYPE,
        "image": cfg.get("image") or DEFAULT_IMAGE,
    }


def _status_text(instance) -> str:
    """
    规范化实例 status 为小写字符串（兼容枚举/对象）。

    @param instance: linode_api4 Instance
    @return: 如 running / provisioning / booting
    """
    raw = getattr(instance, "status", "")
    if raw is None:
        return ""
    # 部分 SDK 版本 status 为枚举
    text = getattr(raw, "value", None) or getattr(raw, "name", None) or raw
    return str(text).strip().lower()


def _refresh_instance(client, instance):
    """
    用 ``client.load`` 刷新实例（官方推荐显式 load，避免惰性对象过期）。

    @param client: LinodeClient
    @param instance: 已有 Instance（至少含 id）
    @return: 刷新后的 Instance
    """
    _, Instance = _import_sdk()
    try:
        return client.load(Instance, instance.id)
    except Exception:  # noqa: BLE001
        try:
            instance.invalidate()
        except Exception:  # noqa: BLE001
            pass
        return instance


def wait_until_ready(client, instance, timeout: int, *, interval: int = DEFAULT_POLL_INTERVAL) -> None:
    """
    等待新建实例就绪（官方推荐流程）。

    依据：
    - Akamai Linode API：``POST /linode/instances`` 立即返回，status 常为
      ``provisioning``；需随后查询直至 ``running``
      （https://techdocs.akamai.com/linode-api/reference/post-linode-instance）。
    - linode_api4：长耗时操作用 Account Events +
      ``client.polling.wait_for_entity_free("linode", id)``
      （https://linode-api4.readthedocs.io/en/latest/guides/event_polling.html）。
    - 无百分比进度；可用 status 映射粗进度（社区官方答复）。

    步骤：
    1. ``wait_for_entity_free``：该 Linode 上无 ``scheduled``/``started`` 事件；
    2. 再 ``load`` 确认 ``status == running``（``booted=false`` 时 entity free
       也可能是 offline，故必须二次校验）；
    3. 若无 Events 权限 / SDK 过旧，回退为按 interval 轮询 GET instance。

    @param client: LinodeClient
    @param instance: create 返回的 Instance
    @param timeout: 最长等待秒数
    @param interval: 轮询间隔秒数
    """
    entity_id = int(instance.id)
    deadline = time.time() + max(1, int(timeout))
    interval = max(1, int(interval))

    _err(
        f"wait_ready: id={entity_id} 开始等待 "
        f"(timeout={timeout}s interval={interval}s)"
    )

    # ── 1) 官方 Event 轮询：等该实体无进行中事件 ─────────────
    polling_group = getattr(client, "polling", None)
    wait_free = getattr(polling_group, "wait_for_entity_free", None) if polling_group else None
    if callable(wait_free):
        remaining = max(1, int(deadline - time.time()))
        _err(
            f"wait_ready: wait_for_entity_free(linode, {entity_id}) "
            f"timeout={remaining}s"
        )
        try:
            wait_free("linode", entity_id, timeout=remaining, interval=interval)
            _err(f"wait_ready: id={entity_id} entity events 已空闲")
        except Exception as exc:  # noqa: BLE001 — 超时或缺 events 权限
            _err(f"wait_ready: wait_for_entity_free 未完成（将改用 status 轮询）: {exc}")
    else:
        _err("wait_ready: SDK 无 polling.wait_for_entity_free，改用 status 轮询")

    # ── 2) 确认 status=running（GET instance）────────────────
    last = ""
    while time.time() < deadline:
        instance = _refresh_instance(client, instance)
        status = _status_text(instance)
        if status != last:
            # 粗进度：与 Linode 社区建议一致（无官方 % API）
            rough = {
                "provisioning": "约 0–40%",
                "booting": "约 40–90%",
                "running": "100%",
                "offline": "offline（若未 booted）",
            }.get(status, "")
            extra = f" ({rough})" if rough else ""
            _err(f"wait_ready: id={entity_id} status={status or '?'}{extra}")
            last = status
        if status == "running":
            _err(f"wait_ready: id={entity_id} 已 running")
            return
        if status in ("stopped", "offline") and last:
            # booted=false 的合法终态；create 默认 booted=true，此处视为异常提示
            raise RuntimeError(
                f"实例 id={entity_id} 事件已结束但 status={status!r} "
                f"（若创建时 booted=false 属预期；否则检查磁盘/配置）"
            )
        time.sleep(interval)

    raise RuntimeError(
        f"等待 running 超时（{timeout}s），当前 status={_status_text(instance)!r}"
    )


def wait_running(instance, timeout: int) -> None:
    """
    兼容旧调用：仅有 instance 时按 status 轮询（无 client 则无法走 Events）。

    @param instance: linode_api4 Instance
    @param timeout: 最长等待秒数
    """
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            instance.invalidate()
        except Exception as exc:  # noqa: BLE001
            _err(f"wait_running: invalidate 失败: {exc}")
        status = _status_text(instance)
        if status != last:
            _err(f"wait_running: id={getattr(instance, 'id', '?')} status={status or '?'}")
            last = status
        if status == "running":
            _err(f"wait_running: id={getattr(instance, 'id', '?')} 已 running")
            return
        time.sleep(DEFAULT_POLL_INTERVAL)
    raise RuntimeError(
        f"等待 running 超时（{timeout}s），当前 status={_status_text(instance)!r}"
    )


def resolve_instance(client, Instance, *, instance_id: int | None, label: str | None):
    """
    按 id 或 label 解析唯一实例。

    @param client: LinodeClient
    @param Instance: Instance 模型类（用于过滤）
    @param instance_id: 数字 ID
    @param label: 实例标签
    @return: Instance
    """
    if instance_id is not None:
        try:
            return client.load(Instance, instance_id)
        except Exception as exc:  # noqa: BLE001 — SDK 错误类型因版本而异
            raise RuntimeError(f"无法加载 id={instance_id}: {exc}") from exc

    if not label:
        raise RuntimeError("必须提供 --id 或 --label")

    matches = list(client.linode.instances(Instance.label == label))
    if not matches:
        raise RuntimeError(f"未找到 label={label!r}")
    if len(matches) > 1:
        ids = ", ".join(str(m.id) for m in matches)
        raise RuntimeError(f"label={label!r} 匹配到多台实例（id: {ids}），请改用 --id")
    return matches[0]


def primary_ipv4(instance) -> str:
    """
    取实例主公网 IPv4（列表第一项）。

    @param instance: Instance
    @return: IPv4 字符串，无则空串
    """
    addrs = list(instance.ipv4 or [])
    return addrs[0] if addrs else ""


def generate_root_pass(length: int = 24) -> str:
    """
    生成符合 Linode 复杂度要求的随机 root 密码。

    Linode 要求足够长度与复杂度；未传 --root-pass / --ssh-key 时自动生成。

    @param length: 密码长度（默认 24）
    @return: 随机密码字符串
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    # 保证至少各类各 1 个，避免偶发过弱
    parts = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*-_=+"),
    ]
    parts += [secrets.choice(alphabet) for _ in range(max(0, length - len(parts)))]
    # 打乱顺序
    for i in range(len(parts) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        parts[i], parts[j] = parts[j], parts[i]
    return "".join(parts)


def resolve_create_root_pass(config: dict[str, Any], cli_root_pass: str | None) -> str | None:
    """
    解析 create 使用的 root 密码。

    优先级（高 → 低）：
      1. CLI --root-pass
      2. defaults.root_pass（兼容旧字段）
      3. defaults.ssh.password（与 servers.local.json 的 ssh.password 同结构）

    @param config: 本地 linode 配置
    @param cli_root_pass: 命令行传入的密码
    @return: 密码字符串；皆无则 None（由调用方自动生成）
    """
    if isinstance(cli_root_pass, str) and cli_root_pass.strip():
        return cli_root_pass.strip()

    defaults = config.get("defaults")
    if not isinstance(defaults, dict):
        return None

    legacy = defaults.get("root_pass")
    if isinstance(legacy, str) and legacy.strip():
        return legacy.strip()

    ssh = defaults.get("ssh")
    if isinstance(ssh, dict):
        password = ssh.get("password")
        if isinstance(password, str) and password.strip():
            # 跳过 example 占位符
            if password.strip() not in ("YOUR_SSH_PASSWORD", "YOUR_PASSWORD"):
                return password.strip()
    return None


def resolve_create_ssh_key(config: dict[str, Any], cli_ssh_key: str | None) -> str | None:
    """
    解析 create 使用的 SSH 公钥。

    优先级：CLI --ssh-key → defaults.ssh_key → defaults.ssh.authorized_key

    @param config: 本地 linode 配置
    @param cli_ssh_key: 命令行公钥
    @return: 公钥字符串或 None
    """
    if isinstance(cli_ssh_key, str) and cli_ssh_key.strip():
        return cli_ssh_key.strip()

    defaults = config.get("defaults")
    if not isinstance(defaults, dict):
        return None

    legacy = defaults.get("ssh_key")
    if isinstance(legacy, str) and legacy.strip():
        return legacy.strip()

    ssh = defaults.get("ssh")
    if isinstance(ssh, dict):
        key = ssh.get("authorized_key") or ssh.get("public_key")
        if isinstance(key, str) and key.strip():
            return key.strip()
    return None


def cmd_create(args: argparse.Namespace) -> int:
    """
    创建（购买）一台 Linode，可选等待 ready，输出 id/ip/root_pass。

    官方语义（POST /linode/instances）：
    - HTTP 成功即返回实例对象，status 多为 ``provisioning``；
    - 镜像部署默认 ``booted=true``，后台继续装系统/启动；
    - 就绪判定：Events 空闲 + ``status=running``（见 ``wait_until_ready``）。

    @param args: argparse 命名空间
    @return: 退出码
    """
    config: dict[str, Any] = args.linode_config
    client = get_client(config, args.linode_config_path)
    _, Instance = _import_sdk()
    cfg_defaults = create_defaults_from_config(config)

    ltype = args.type or cfg_defaults.get("type") or DEFAULT_TYPE
    region = args.region or cfg_defaults.get("region") or DEFAULT_REGION
    image = args.image or cfg_defaults.get("image") or DEFAULT_IMAGE

    # label：CLI → config.defaults.label → 时间戳兜底（仅无配置时）
    label = args.label or cfg_defaults.get("label")
    if not label:
        label = f"rm-linode-{int(time.time())}"

    create_kwargs: dict[str, Any] = {
        "ltype": ltype,
        "region": region,
        "image": image,
        "label": label,
        # 官方：从 Image 创建时默认 booted=true；显式写出避免歧义
        "booted": True,
    }
    root_pass_arg = resolve_create_root_pass(config, args.root_pass)
    ssh_key = resolve_create_ssh_key(config, args.ssh_key)

    # API 要求：从 Image 创建时必须提供 root_pass / authorized_keys / authorized_users 之一
    if root_pass_arg:
        create_kwargs["root_pass"] = root_pass_arg
    if ssh_key:
        create_kwargs["authorized_keys"] = [ssh_key]
    if "root_pass" not in create_kwargs and "authorized_keys" not in create_kwargs:
        create_kwargs["root_pass"] = generate_root_pass()

    # 记录将使用的 root 密码（新版 SDK 的 instance_create 只返回 Instance）
    used_root_pass = create_kwargs.get("root_pass") or ""

    _err(
        f"create: POST /linode/instances label={label} region={region} "
        f"type={ltype} image={image} booted=true"
    )
    instance = None
    try:
        created = client.linode.instance_create(**create_kwargs)
    except Exception as exc:  # noqa: BLE001
        # HTTP 超时等：控制台可能已受理创建 → 按 label 找回后继续 wait
        _err(f"create: instance_create 异常: {exc}")
        try:
            instance = resolve_instance(
                client, Instance, instance_id=None, label=label
            )
            _err(
                f"create: 已按 label 找回 id={instance.id} "
                f"status={_status_text(instance)}，继续等待就绪"
            )
        except Exception:  # noqa: BLE001
            payload = {"ok": False, "action": "create", "error": str(exc)}
            _emit(payload, as_json=args.json, human_lines=[f"error={exc}"])
            return EXIT_FAIL
    else:
        # 兼容旧版 SDK 可能返回 (Instance, root_pass)
        if isinstance(created, tuple) and len(created) >= 1:
            instance = created[0]
            if len(created) > 1 and created[1]:
                used_root_pass = created[1] or used_root_pass
        else:
            instance = created

    assert instance is not None
    root_pass = used_root_pass
    _err(
        f"create: API 对象已就绪 id={instance.id} label={instance.label} "
        f"status={_status_text(instance)}（随后用 Events/status 等待 running）"
    )

    if not args.no_wait:
        try:
            wait_until_ready(client, instance, args.wait_seconds)
        except Exception as exc:  # noqa: BLE001
            _err(str(exc))
            instance = _refresh_instance(client, instance)
            ipv4 = primary_ipv4(instance)
            payload = {
                "ok": False,
                "action": "create",
                "error": str(exc),
                "id": instance.id,
                "label": instance.label,
                "status": _status_text(instance),
                "ipv4": ipv4,
                "root_pass": root_pass,
            }
            _emit(payload, as_json=args.json)
            return EXIT_FAIL

    instance = _refresh_instance(client, instance)
    ipv4 = primary_ipv4(instance)
    ipv4_list = list(instance.ipv4 or [])
    status = _status_text(instance)
    payload = {
        "ok": True,
        "action": "create",
        "id": instance.id,
        "label": instance.label,
        "region": str(getattr(instance.region, "id", instance.region)),
        "type": ltype,
        "status": status,
        "ipv4": ipv4,
        "ipv4_list": ipv4_list,
        "root_pass": root_pass,
        "ssh": f"ssh root@{ipv4}" if ipv4 else "",
    }
    _emit(
        payload,
        as_json=args.json,
        human_lines=[
            f"id={payload['id']}",
            f"label={payload['label']}",
            f"region={payload['region']}",
            f"status={payload['status']}",
            f"ipv4={payload['ipv4']}",
            f"root_pass={payload['root_pass']}",
            f"ssh={payload['ssh']}",
        ],
    )
    return EXIT_OK


def cmd_ip(args: argparse.Namespace) -> int:
    """
    按 id 或 label 打印公网 IPv4。

    @param args: argparse 命名空间
    @return: 退出码
    """
    _LinodeClient, Instance = _import_sdk()
    client = get_client(args.linode_config, args.linode_config_path)
    try:
        instance = resolve_instance(client, Instance, instance_id=args.id, label=args.label)
    except RuntimeError as exc:
        _err(str(exc))
        _emit({"ok": False, "action": "ip", "error": str(exc)}, as_json=args.json)
        return EXIT_FAIL

    ipv4 = primary_ipv4(instance)
    payload = {
        "ok": True,
        "action": "ip",
        "id": instance.id,
        "label": instance.label,
        "status": instance.status,
        "ipv4": ipv4,
        "ipv4_list": list(instance.ipv4 or []),
    }
    # 人类模式仅输出 IP 一行，便于 $(python ... ip --label x) 捕获
    _emit(payload, as_json=args.json, human_lines=[ipv4])
    return EXIT_OK


def cmd_list(args: argparse.Namespace) -> int:
    """
    列出账号下全部实例。

    @param args: argparse 命名空间
    @return: 退出码
    """
    client = get_client(args.linode_config, args.linode_config_path)
    try:
        instances = list(client.linode.instances())
    except Exception as exc:  # noqa: BLE001
        _err(f"列出失败: {exc}")
        _emit({"ok": False, "action": "list", "error": str(exc)}, as_json=args.json)
        return EXIT_FAIL

    rows = []
    for inst in instances:
        rows.append(
            {
                "id": inst.id,
                "label": inst.label,
                "region": str(getattr(inst.region, "id", inst.region)),
                "status": inst.status,
                "ipv4": primary_ipv4(inst),
            }
        )

    payload = {"ok": True, "action": "list", "count": len(rows), "instances": rows}
    if args.json:
        _emit(payload, as_json=True)
    else:
        for row in rows:
            print(f"{row['id']}\t{row['label']}\t{row['region']}\t{row['status']}\t{row['ipv4']}")
        if not rows:
            _err("(无实例)")
    return EXIT_OK


def cmd_delete(args: argparse.Namespace) -> int:
    """
    按 id 或 label 删除实例；必须带 --yes。

    @param args: argparse 命名空间
    @return: 退出码
    """
    if not args.yes:
        _err("删除不可恢复，请显式传入 --yes")
        return EXIT_USAGE

    _LinodeClient, Instance = _import_sdk()
    client = get_client(args.linode_config, args.linode_config_path)
    try:
        instance = resolve_instance(client, Instance, instance_id=args.id, label=args.label)
    except RuntimeError as exc:
        _err(str(exc))
        _emit({"ok": False, "action": "delete", "error": str(exc)}, as_json=args.json)
        return EXIT_FAIL

    iid, label, ipv4 = instance.id, instance.label, primary_ipv4(instance)
    try:
        instance.delete()
    except Exception as exc:  # noqa: BLE001
        _err(f"删除失败: {exc}")
        _emit(
            {"ok": False, "action": "delete", "error": str(exc), "id": iid, "label": label},
            as_json=args.json,
        )
        return EXIT_FAIL

    payload = {
        "ok": True,
        "action": "delete",
        "id": iid,
        "label": label,
        "ipv4": ipv4,
        "deleted": True,
    }
    _emit(
        payload,
        as_json=args.json,
        human_lines=[f"deleted id={iid} label={label} ipv4={ipv4}"],
    )
    return EXIT_OK


def _region_row(region) -> dict[str, Any]:
    """
    将 Region 对象转为可序列化行。

    @param region: linode_api4 Region
    @return: 字典
    """
    caps = getattr(region, "capabilities", None) or []
    return {
        "id": str(getattr(region, "id", region)),
        "label": getattr(region, "label", "") or "",
        "country": getattr(region, "country", "") or "",
        "status": getattr(region, "status", "") or "",
        "capabilities": list(caps) if caps else [],
    }


def _type_row(ltype) -> dict[str, Any]:
    """
    将 Type（机型）对象转为可序列化行。

    @param ltype: linode_api4 Type
    @return: 字典
    """
    price = getattr(ltype, "price", None)
    hourly = monthly = None
    if price is not None:
        hourly = getattr(price, "hourly", None)
        monthly = getattr(price, "monthly", None)
        if isinstance(price, dict):
            hourly = price.get("hourly", hourly)
            monthly = price.get("monthly", monthly)
    return {
        "id": str(getattr(ltype, "id", ltype)),
        "label": getattr(ltype, "label", "") or "",
        "vcpus": getattr(ltype, "vcpus", None),
        "memory_mb": getattr(ltype, "memory", None),
        "disk_mb": getattr(ltype, "disk", None),
        "transfer_gb": getattr(ltype, "transfer", None),
        "price_hourly": hourly,
        "price_monthly": monthly,
    }


def _image_row(image) -> dict[str, Any]:
    """
    将 Image 对象转为可序列化行。

    @param image: linode_api4 Image
    @return: 字典
    """
    return {
        "id": str(getattr(image, "id", image)),
        "label": getattr(image, "label", "") or "",
        "vendor": getattr(image, "vendor", "") or "",
        "size_mb": getattr(image, "size", None),
        "is_public": bool(getattr(image, "is_public", False)),
        "deprecated": bool(getattr(image, "deprecated", False)),
    }


def cmd_params(args: argparse.Namespace) -> int:
    """
    枚举 create 可用参数：region / type / image（来自 Linode API 实时列表）。

    @param args: argparse 命名空间
    @return: 退出码
    """
    client = get_client(args.linode_config, args.linode_config_path)
    kind = (args.kind or "all").lower()
    if kind not in ("all", "region", "regions", "type", "types", "image", "images"):
        _err(f"未知 --kind={args.kind!r}，可选: all | region | type | image")
        return EXIT_USAGE

    want_regions = kind in ("all", "region", "regions")
    want_types = kind in ("all", "type", "types")
    want_images = kind in ("all", "image", "images")

    regions_out: list[dict[str, Any]] = []
    types_out: list[dict[str, Any]] = []
    images_out: list[dict[str, Any]] = []

    try:
        if want_regions:
            for region in client.regions():
                row = _region_row(region)
                if args.region_filter:
                    needle = args.region_filter.lower()
                    blob = f"{row['id']} {row['label']} {row['country']}".lower()
                    if needle not in blob:
                        continue
                regions_out.append(row)
            regions_out.sort(key=lambda r: r["id"])

        if want_types:
            for ltype in client.linode.types():
                row = _type_row(ltype)
                if args.type_filter:
                    needle = args.type_filter.lower()
                    blob = f"{row['id']} {row['label']}".lower()
                    if needle not in blob:
                        continue
                types_out.append(row)
            types_out.sort(key=lambda t: (t.get("price_monthly") is None, t.get("price_monthly") or 0, t["id"]))

        if want_images:
            for image in client.images():
                row = _image_row(image)
                if not args.all_images:
                    # 默认：公开且未废弃，适合 create --image
                    if not row["is_public"] or row["deprecated"]:
                        continue
                if args.vendor:
                    if (row["vendor"] or "").lower() != args.vendor.lower():
                        continue
                if args.image_filter:
                    needle = args.image_filter.lower()
                    blob = f"{row['id']} {row['label']} {row['vendor']}".lower()
                    if needle not in blob:
                        continue
                images_out.append(row)
            images_out.sort(key=lambda i: i["id"])
    except Exception as exc:  # noqa: BLE001
        _err(f"枚举参数失败: {exc}")
        _emit({"ok": False, "action": "params", "error": str(exc)}, as_json=args.json)
        return EXIT_FAIL

    payload: dict[str, Any] = {
        "ok": True,
        "action": "params",
        "kind": kind if kind != "all" else "all",
        "create_hints": {
            "region": "--region <id>",
            "type": "--type <id>",
            "image": "--image <id>",
            "example": (
                "python workflow/torrent_sources/linode_vps.py create "
                f"--region {DEFAULT_REGION} --type {DEFAULT_TYPE} --image {DEFAULT_IMAGE}"
            ),
        },
    }
    if want_regions:
        payload["regions"] = regions_out
        payload["regions_count"] = len(regions_out)
    if want_types:
        payload["types"] = types_out
        payload["types_count"] = len(types_out)
    if want_images:
        payload["images"] = images_out
        payload["images_count"] = len(images_out)

    if args.json:
        _emit(payload, as_json=True)
        return EXIT_OK

    # 人类可读：分块表格，首列即为 create 可传入的 id
    if want_regions:
        print("# regions  →  create --region <id>")
        print("id\tcountry\tstatus\tlabel")
        for row in regions_out:
            print(f"{row['id']}\t{row['country']}\t{row['status']}\t{row['label']}")
        print(f"# count={len(regions_out)}\n")

    if want_types:
        print("# types  →  create --type <id>")
        print("id\tvcpus\tmemory_mb\tdisk_mb\ttransfer_gb\t$/mo\t$/hr\tlabel")
        for row in types_out:
            print(
                f"{row['id']}\t{row['vcpus']}\t{row['memory_mb']}\t{row['disk_mb']}\t"
                f"{row['transfer_gb']}\t{row['price_monthly']}\t{row['price_hourly']}\t{row['label']}"
            )
        print(f"# count={len(types_out)}\n")

    if want_images:
        print("# images  →  create --image <id>")
        print("id\tvendor\tsize_mb\tpublic\tdeprecated\tlabel")
        for row in images_out:
            print(
                f"{row['id']}\t{row['vendor']}\t{row['size_mb']}\t"
                f"{row['is_public']}\t{row['deprecated']}\t{row['label']}"
            )
        print(f"# count={len(images_out)}\n")

    return EXIT_OK


def cmd_defaults(args: argparse.Namespace) -> int:
    """
    输出 linode.local.json 合并后的 create 默认参数（label/region/type/image）。

    不调用 Linode API，也不要求 Token 有效；供一键脚本等外部程序读取配置。

    @param args: argparse 命名空间
    @return: 退出码
    """
    config: dict[str, Any] = args.linode_config
    effective = effective_create_defaults(config)
    ssh_user = "root"
    ssh_port = 22
    has_ssh_password = False
    defaults = config.get("defaults")
    if isinstance(defaults, dict):
        ssh = defaults.get("ssh")
        if isinstance(ssh, dict):
            if isinstance(ssh.get("user"), str) and ssh["user"].strip():
                ssh_user = ssh["user"].strip()
            try:
                ssh_port = int(ssh.get("port") or 22)
            except (TypeError, ValueError):
                ssh_port = 22
            pwd = ssh.get("password")
            has_ssh_password = isinstance(pwd, str) and bool(pwd.strip()) and pwd.strip() not in (
                "YOUR_SSH_PASSWORD",
                "YOUR_PASSWORD",
            )

    payload = {
        "ok": True,
        "action": "defaults",
        "config_path": str(args.linode_config_path) if args.linode_config_path else None,
        "label": effective["label"],
        "region": effective["region"],
        "type": effective["type"],
        "image": effective["image"],
        "ssh_user": ssh_user,
        "ssh_port": ssh_port,
        "has_ssh_password": has_ssh_password,
    }
    if args.json:
        _emit(payload, as_json=True)
    else:
        _emit(
            payload,
            as_json=False,
            human_lines=[
                f"config_path={payload['config_path'] or ''}",
                f"label={payload['label']}",
                f"region={payload['region']}",
                f"type={payload['type']}",
                f"image={payload['image']}",
                f"ssh_user={payload['ssh_user']}",
                f"ssh_port={payload['ssh_port']}",
                f"has_ssh_password={payload['has_ssh_password']}",
            ],
        )
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """
    构建 CLI 参数解析器。

    --json / --config 仅挂在子命令上（避免 parent+sub 双挂导致
    「子命令前的 --config」被默认 None 覆盖）。

    @return: ArgumentParser
    """
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json",
        action="store_true",
        help="stdout 输出单行 JSON（供外部程序解析）",
    )
    common.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="linode.local.json 路径（默认自动查找；已 gitignore）",
    )

    parser = argparse.ArgumentParser(
        description="Linode VPS 自动化：create / ip / list / delete / params / defaults（可供外部调用）",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    create_p = sub.add_parser(
        "create",
        help="购买并创建 VPS（可用参数见子命令 params）",
        parents=[common],
    )
    # default=None：未传 CLI 时再回落到 config.defaults / 内置默认
    create_p.add_argument(
        "--type",
        default=None,
        help=f"机型 id（默认 {DEFAULT_TYPE}；枚举：params --kind type）",
    )
    create_p.add_argument(
        "--region",
        default=None,
        help=f"区域 id（默认 {DEFAULT_REGION}；枚举：params --kind region）",
    )
    create_p.add_argument(
        "--image",
        default=None,
        help=f"镜像 id（默认 {DEFAULT_IMAGE}；枚举：params --kind image）",
    )
    create_p.add_argument(
        "--label",
        default=None,
        help="实例标签；省略则用 config.defaults.label，再否则 rm-linode-<unix_ts>",
    )
    create_p.add_argument(
        "--root-pass",
        default=None,
        dest="root_pass",
        help="root 密码；省略则用 config defaults.ssh.password，再否则自动生成",
    )
    create_p.add_argument("--ssh-key", default=None, dest="ssh_key", help="SSH 公钥字符串")
    create_p.add_argument(
        "--wait-seconds",
        type=int,
        default=DEFAULT_WAIT_SECONDS,
        dest="wait_seconds",
        help=f"等待就绪超时秒数（默认 {DEFAULT_WAIT_SECONDS}；官方 Events 轮询 + status=running）",
    )
    create_p.add_argument("--no-wait", action="store_true", help="仅 POST，不等待 Events/running")
    create_p.set_defaults(func=cmd_create)

    ip_p = sub.add_parser("ip", help="查询公网 IPv4", parents=[common])
    ip_p.add_argument("--id", type=int, default=None, help="实例 ID")
    ip_p.add_argument("--label", default=None, help="实例 label")
    ip_p.set_defaults(func=cmd_ip)

    list_p = sub.add_parser("list", help="列出全部实例", parents=[common])
    list_p.set_defaults(func=cmd_list)

    del_p = sub.add_parser("delete", help="删除实例（需 --yes）", parents=[common])
    del_p.add_argument("--id", type=int, default=None, help="实例 ID")
    del_p.add_argument("--label", default=None, help="实例 label")
    del_p.add_argument("--yes", action="store_true", help="确认删除（必填）")
    del_p.set_defaults(func=cmd_delete)

    params_p = sub.add_parser(
        "params",
        help="枚举 create 可用参数（region / type / image）",
        parents=[common],
    )
    params_p.add_argument(
        "--kind",
        default="all",
        choices=["all", "region", "regions", "type", "types", "image", "images"],
        help="枚举类别（默认 all）",
    )
    params_p.add_argument(
        "--region-filter",
        default=None,
        dest="region_filter",
        help="区域关键字过滤（匹配 id/label/country，如 jp / osaka）",
    )
    params_p.add_argument(
        "--type-filter",
        default=None,
        dest="type_filter",
        help="机型关键字过滤（匹配 id/label，如 nanode / dedicated）",
    )
    params_p.add_argument(
        "--image-filter",
        default=None,
        dest="image_filter",
        help="镜像关键字过滤（匹配 id/label/vendor，如 debian12）",
    )
    params_p.add_argument(
        "--vendor",
        default=None,
        help="仅列出指定 vendor 的镜像（如 debian / ubuntu）",
    )
    params_p.add_argument(
        "--all-images",
        action="store_true",
        dest="all_images",
        help="镜像包含私有/已废弃（默认仅公开且未废弃）",
    )
    params_p.set_defaults(func=cmd_params)

    defaults_p = sub.add_parser(
        "defaults",
        help="输出 linode.local.json 中的 create 默认参数（含 label，不调 API）",
        parents=[common],
    )
    defaults_p.set_defaults(func=cmd_defaults)

    return parser


def _normalize_argv(argv: list[str]) -> list[str]:
    """
    将写在子命令之前的全局选项挪到子命令之后，避免 argparse 丢弃。

    支持：
      linode_vps.py --json --config f.json list
      linode_vps.py list --json --config f.json

    @param argv: 不含程序名的参数列表
    @return: 规范化后的参数列表
    """
    if not argv:
        return argv

    globals_opts = {"--json"}
    globals_with_value = {"--config"}
    leading: list[str] = []
    rest = list(argv)
    while rest:
        tok = rest[0]
        if tok in globals_opts:
            leading.append(rest.pop(0))
            continue
        if tok in globals_with_value:
            if len(rest) < 2:
                break
            leading.append(rest.pop(0))
            leading.append(rest.pop(0))
            continue
        if tok.startswith("--config="):
            leading.append(rest.pop(0))
            continue
        break

    if not leading or not rest:
        return argv
    # rest[0] 应为子命令名
    return [rest[0], *leading, *rest[1:]]


def main(argv: list[str] | None = None) -> int:
    """
    CLI 入口。

    @param argv: 参数列表；None 表示使用 sys.argv
    @return: 进程退出码
    """
    raw = list(sys.argv[1:] if argv is None else argv)
    normalized = _normalize_argv(raw)
    parser = build_parser()
    args = parser.parse_args(normalized)

    if args.cmd in ("ip", "delete") and args.id is None and not args.label:
        _err(f"{args.cmd}: 请指定 --id 或 --label")
        return EXIT_USAGE

    try:
        config, config_path = resolve_config(args.config)
    except RuntimeError as exc:
        _err(str(exc))
        return EXIT_USAGE

    args.linode_config = config
    args.linode_config_path = config_path

    try:
        return int(args.func(args))
    except SystemExit as exc:
        # require_token / _import_sdk 可能以 SystemExit(EXIT_USAGE) 抛出
        code = exc.code
        if code is None:
            return EXIT_OK
        if isinstance(code, int):
            return code
        return EXIT_FAIL
    except KeyboardInterrupt:
        _err("已中断")
        return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
