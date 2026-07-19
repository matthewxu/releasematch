# -*- coding: utf-8 -*-
"""
Ops 配置读写服务 — ``.env`` 与 ``accounts.local.json``。

@module workflow.ops.config_service
@description
  供本地 Ops 控制台加载 / 修改 / 热加载运行配置。
  仅本机使用；写入路径限定在项目根 ``.env`` 与 torrent_sources 账户文件。
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from workflow.config import (
    PROJECT_ROOT,
    release_mysql_configured,
    reload_runtime_config,
)
from workflow.torrent_sources.config import (
    ACCOUNTS_EXAMPLE,
    ACCOUNTS_LOCAL,
    is_jackett_api_key_configured,
    load_accounts_config,
    probe_jackett_http,
    resolve_accounts_config_path,
)

# 环境变量模板（无 .env 时用于初始化）
ENV_EXAMPLE_PATH: Path = PROJECT_ROOT / "config.env.example"
# 实际运行使用的 dotenv 文件
ENV_PATH: Path = PROJECT_ROOT / ".env"

# 允许 Ops UI 编辑的键名白名单（防止写入任意环境变量）
_ENV_KEY_RE: re.Pattern[str] = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _rel_to_project(path: Path) -> str:
    """
    将路径转为相对项目根的展示字符串；不在根下时返回绝对路径。

    @param path: 任意 Path
    @returns: 相对或绝对路径字符串
    """
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


@dataclass(frozen=True)
class EnvFieldDef:
    """
    单个 `.env` 表单字段定义。

    @param key: 环境变量名
    @param group: 分组标题（UI 分区）
    @param label: 短标签
    @param secret: 是否为密钥类（UI 用 password 输入）
    @param hint: 补充说明
    @param default: 模板默认值（文件无键时展示）
    """

    # 环境变量名，如 RM_RELEASE_MYSQL_HOST
    key: str
    # UI 分组名
    group: str
    # 表单标签
    label: str
    # 是否按密钥输入框展示
    secret: bool = False
    # 字段说明
    hint: str = ""
    # 缺省展示值
    default: str = ""


# Ops 配置页可编辑字段（与 config.env.example 对齐的常用项）
ENV_FIELD_DEFS: tuple[EnvFieldDef, ...] = (
    EnvFieldDef("RM_STORAGE_BACKEND", "存储", "存储后端", hint="mysql | d1", default="mysql"),
    EnvFieldDef("RM_RELEASE_MYSQL_HOST", "Release MySQL", "主机", default="127.0.0.1"),
    EnvFieldDef("RM_RELEASE_MYSQL_PORT", "Release MySQL", "端口", default="3306"),
    EnvFieldDef("RM_RELEASE_MYSQL_DB", "Release MySQL", "数据库名", default="releasematch"),
    EnvFieldDef("RM_RELEASE_MYSQL_USER", "Release MySQL", "用户名", default="root"),
    EnvFieldDef("RM_RELEASE_MYSQL_PASSWORD", "Release MySQL", "密码", secret=True),
    EnvFieldDef(
        "RM_TMDB_DATA_MODE",
        "TMDB 元数据",
        "数据模式",
        hint="standalone | mysql",
        default="standalone",
    ),
    EnvFieldDef("RM_MYSQL_HOST", "TMDB 元数据", "MySQL 主机", default="127.0.0.1"),
    EnvFieldDef("RM_MYSQL_PORT", "TMDB 元数据", "MySQL 端口", default="3306"),
    EnvFieldDef("RM_MYSQL_DB", "TMDB 元数据", "MySQL 库名", default="test"),
    EnvFieldDef("RM_MYSQL_USER", "TMDB 元数据", "MySQL 用户"),
    EnvFieldDef("RM_MYSQL_PASSWORD", "TMDB 元数据", "MySQL 密码", secret=True),
    EnvFieldDef("RM_TMDB_API_KEY", "TMDB API", "API Key", secret=True),
    EnvFieldDef(
        "RM_TMDB_CORS_PROXY",
        "TMDB API",
        "CORS Proxy",
        default="https://api.weidaohang.org/cp/",
    ),
    EnvFieldDef(
        "RM_TMDB_API_BASE",
        "TMDB API",
        "API Base",
        default="https://api.themoviedb.org/3",
    ),
    EnvFieldDef(
        "RM_CRAWLER_TMDB_ROOT",
        "TMDB API",
        "crawler_tmdb 根目录",
        hint="Ops TV 季集依赖 sibling crawler_tmdb",
    ),
    EnvFieldDef(
        "RM_SITE_ORIGIN",
        "站点",
        "Site Origin",
        default="https://releasematch.io",
    ),
    EnvFieldDef(
        "RM_SHOW_IG_DEBUG",
        "站点",
        "IG Debug",
        hint="0/1；生产务必 0",
        default="0",
    ),
    EnvFieldDef("RM_SITE_I18N_ENABLED", "站点", "I18N 开关", hint="0/1", default="0"),
    EnvFieldDef("RM_SITE_LOCALE", "站点", "默认语言", hint="en | zh", default="en"),
    EnvFieldDef("RM_D1_DATABASE_NAME", "Cloudflare D1", "D1 库名", default="releasematch"),
    EnvFieldDef("RM_D1_BINDING", "Cloudflare D1", "Binding", default="DB"),
    EnvFieldDef(
        "JACKETT_BASE_URL",
        "数据源",
        "Jackett URL",
        default="http://127.0.0.1:9117",
    ),
    EnvFieldDef("JACKETT_API_KEY", "数据源", "Jackett API Key", secret=True),
    EnvFieldDef("EZTV_BASE_URL", "数据源", "EZTV", default="https://eztvx.to"),
    EnvFieldDef("YTS_BASE_URL", "数据源", "YTS", default="https://yts.mx"),
    EnvFieldDef("NYAA_BASE_URL", "数据源", "Nyaa", default="https://nyaa.si"),
    EnvFieldDef("DMHY_BASE_URL", "数据源", "DMHy", default="https://share.dmhy.org"),
    EnvFieldDef(
        "TORRENT_PROXY",
        "数据源",
        "Torrent Proxy",
        hint="如 socks5h://127.0.0.1:1080",
    ),
    EnvFieldDef(
        "TORRENT_MIN_INTERVAL_SEC",
        "数据源",
        "最小请求间隔(秒)",
        default="2.0",
    ),
    EnvFieldDef(
        "TORRENT_SEEDERS_TTL_HOURS",
        "数据源",
        "Seeders 缓存 TTL(小时)",
        default="6",
    ),
)

# 白名单键集合（快速校验）
ALLOWED_ENV_KEYS: frozenset[str] = frozenset(f.key for f in ENV_FIELD_DEFS)


def parse_dotenv_text(text: str) -> Dict[str, str]:
    """
    解析 dotenv 文本为键值字典（忽略注释与空行）。

    @param text: 文件全文
    @returns: key → value（已去首尾引号）
    """
    out: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            out[key] = value
    return out


def read_dotenv_map(path: Optional[Path] = None) -> Dict[str, str]:
    """
    读取磁盘 `.env`（或指定路径）为字典。

    @param path: 文件路径；默认项目根 `.env`
    @returns: 键值；文件不存在返回空 dict
    """
    target = path or ENV_PATH
    if not target.is_file():
        return {}
    return parse_dotenv_text(target.read_text(encoding="utf-8"))


def _quote_env_value(value: str) -> str:
    """
    将值写成适合 dotenv 的形式（含空白或 # 时加双引号）。

    @param value: 原始字符串
    @returns: 可写入 `KEY=...` 右侧的文本
    """
    if value == "":
        return ""
    if any(ch in value for ch in (' ', '\t', '#', '"', "'", "\n")):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def merge_dotenv_updates(
    existing_text: str,
    updates: Dict[str, str],
    *,
    keys_order: Sequence[str],
) -> str:
    """
    在保留原注释/顺序的前提下合并更新键值；缺失键追加到文末。

    @param existing_text: 当前文件内容（可为空）
    @param updates: 要写入的键值（仅白名单）
    @param keys_order: 追加新键时的推荐顺序
    @returns: 新文件全文
    """
    lines = existing_text.splitlines()
    # 已在文件中出现过的键
    seen: set[str] = set()
    new_lines: List[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(raw)
            continue
        key, _, _ = stripped.partition("=")
        key = key.strip()
        if key in updates:
            new_lines.append(f"{key}={_quote_env_value(updates[key])}")
            seen.add(key)
        else:
            new_lines.append(raw)
            seen.add(key)

    missing = [k for k in keys_order if k in updates and k not in seen]
    # 其余 updates 中未在 order 的键
    missing.extend(k for k in updates if k not in seen and k not in missing)
    if missing:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append("# ── Ops 控制台追加 / 更新 ────────────────────────────")
        for key in missing:
            new_lines.append(f"{key}={_quote_env_value(updates[key])}")
            seen.add(key)

    body = "\n".join(new_lines)
    if body and not body.endswith("\n"):
        body += "\n"
    return body


def ensure_env_file_from_example() -> Dict[str, Any]:
    """
    若 `.env` 不存在，从 ``config.env.example`` 复制一份。

    @returns: ok / path / created
    """
    if ENV_PATH.is_file():
        return {
            "ok": True,
            "created": False,
            "path": _rel_to_project(ENV_PATH),
        }
    if not ENV_EXAMPLE_PATH.is_file():
        return {"ok": False, "error": f"缺少模板: {ENV_EXAMPLE_PATH.name}"}
    shutil.copyfile(ENV_EXAMPLE_PATH, ENV_PATH)
    return {
        "ok": True,
        "created": True,
        "path": _rel_to_project(ENV_PATH),
    }


def ensure_accounts_local_from_example() -> Dict[str, Any]:
    """
    若 ``accounts.local.json`` 不存在，从 example 复制。

    @returns: ok / path / created
    """
    if ACCOUNTS_LOCAL.is_file():
        return {
            "ok": True,
            "created": False,
            "path": _rel_to_project(ACCOUNTS_LOCAL),
        }
    if not ACCOUNTS_EXAMPLE.is_file():
        return {"ok": False, "error": f"缺少模板: {ACCOUNTS_EXAMPLE.name}"}
    shutil.copyfile(ACCOUNTS_EXAMPLE, ACCOUNTS_LOCAL)
    return {
        "ok": True,
        "created": True,
        "path": _rel_to_project(ACCOUNTS_LOCAL),
    }


def _env_fields_payload(disk_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    组装 UI 字段列表（磁盘值优先，其次进程 environ，再默认）。

    @param disk_map: 已解析的 `.env` 字典
    @returns: 字段 dict 列表
    """
    rows: List[Dict[str, Any]] = []
    for field in ENV_FIELD_DEFS:
        # 展示优先级：磁盘 → 当前进程 → 模板默认
        if field.key in disk_map:
            value = disk_map[field.key]
            source = "disk"
        elif field.key in os.environ:
            value = os.environ[field.key]
            source = "process"
        else:
            value = field.default
            source = "default"
        rows.append(
            {
                "key": field.key,
                "group": field.group,
                "label": field.label,
                "secret": field.secret,
                "hint": field.hint,
                "default": field.default,
                "value": value,
                "source": source,
            }
        )
    return rows


def _accounts_disk_raw() -> Dict[str, Any]:
    """
    读取磁盘上的 accounts JSON（不做 env 覆盖合并）。

    @returns: path / exists / using_example / data
    """
    path = resolve_accounts_config_path()
    exists_local = ACCOUNTS_LOCAL.is_file()
    with open(path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    return {
        "path": _rel_to_project(path),
        "exists_local": exists_local,
        "using_example": path.resolve() == ACCOUNTS_EXAMPLE.resolve(),
        "data": data,
    }


def _status_snapshot() -> Dict[str, Any]:
    """
    汇总配置就绪状态（供 UI 徽章）。

    @returns: mysql / jackett / 文件存在性等
    """
    disk = read_dotenv_map()
    jackett_url = (
        disk.get("JACKETT_BASE_URL")
        or os.environ.get("JACKETT_BASE_URL")
        or "http://127.0.0.1:9117"
    )
    jackett_key = disk.get("JACKETT_API_KEY") or os.environ.get("JACKETT_API_KEY") or ""
    # 合并 accounts 内 key（若 env 未设）
    try:
        acc = load_accounts_config()
        if not jackett_key:
            jackett_key = str((acc.get("jackett") or {}).get("api_key") or "")
        if (acc.get("jackett") or {}).get("base_url"):
            jackett_url = str(acc["jackett"]["base_url"])
    except Exception:  # noqa: BLE001
        pass

    probe: Dict[str, Any] = {"reachable": False, "skipped": True}
    if is_jackett_api_key_configured(jackett_key):
        probe = probe_jackett_http(jackett_url)
        probe["skipped"] = False

    return {
        "env_exists": ENV_PATH.is_file(),
        "accounts_local_exists": ACCOUNTS_LOCAL.is_file(),
        "release_mysql_configured": release_mysql_configured(),
        "jackett_key_configured": is_jackett_api_key_configured(jackett_key),
        "jackett_probe": probe,
        "storage_backend": os.environ.get("RM_STORAGE_BACKEND")
        or disk.get("RM_STORAGE_BACKEND")
        or "mysql",
    }


def get_config_bundle() -> Dict[str, Any]:
    """
    加载完整配置包（磁盘 + 字段定义 + accounts + 状态）。

    @returns: ok 与 UI 所需全部数据
    """
    disk_map = read_dotenv_map()
    accounts = _accounts_disk_raw()
    return {
        "ok": True,
        "env": {
            "path": _rel_to_project(ENV_PATH),
            "exists": ENV_PATH.is_file(),
            "example_path": _rel_to_project(ENV_EXAMPLE_PATH),
            "fields": _env_fields_payload(disk_map),
            "raw": ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.is_file() else "",
        },
        "accounts": accounts,
        "status": _status_snapshot(),
    }


def save_env_values(values: Dict[str, Any], *, reload: bool = True) -> Dict[str, Any]:
    """
    将表单键值合并写入 ``.env``，可选热加载到当前进程。

    @param values: key→value；仅白名单键生效
    @param reload: 写盘后是否 ``reload_runtime_config``
    @returns: ok / updated_keys / path / runtime
    """
    if not isinstance(values, dict):
        return {"ok": False, "error": "values 须为对象"}

    updates: Dict[str, str] = {}
    rejected: List[str] = []
    for raw_key, raw_val in values.items():
        key = str(raw_key).strip()
        if key not in ALLOWED_ENV_KEYS or not _ENV_KEY_RE.match(key):
            rejected.append(key)
            continue
        if raw_val is None:
            continue
        updates[key] = str(raw_val)

    if not updates:
        return {"ok": False, "error": "没有可写入的合法键", "rejected": rejected}

    if not ENV_PATH.is_file():
        init = ensure_env_file_from_example()
        if not init.get("ok"):
            # 无模板则从空文件开始
            ENV_PATH.write_text("", encoding="utf-8")

    existing = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.is_file() else ""
    order = [f.key for f in ENV_FIELD_DEFS]
    new_text = merge_dotenv_updates(existing, updates, keys_order=order)
    ENV_PATH.write_text(new_text, encoding="utf-8")

    runtime: Optional[Dict[str, Any]] = None
    if reload:
        runtime = apply_runtime_reload()

    return {
        "ok": True,
        "path": _rel_to_project(ENV_PATH),
        "updated_keys": sorted(updates.keys()),
        "rejected": rejected,
        "runtime": runtime,
    }


def save_env_raw(text: str, *, reload: bool = True) -> Dict[str, Any]:
    """
    以全文方式覆盖写入 ``.env``（高级编辑）。

    @param text: 完整 dotenv 文本
    @param reload: 写盘后是否热加载
    @returns: ok / path / key_count / runtime
    """
    if not isinstance(text, str):
        return {"ok": False, "error": "raw 须为字符串"}
    # 粗校验：每条赋值行的键须匹配命名规则
    parsed = parse_dotenv_text(text)
    for key in parsed:
        if not _ENV_KEY_RE.match(key):
            return {"ok": False, "error": f"非法环境变量名: {key}"}

    ENV_PATH.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    runtime = apply_runtime_reload() if reload else None
    return {
        "ok": True,
        "path": _rel_to_project(ENV_PATH),
        "key_count": len(parsed),
        "runtime": runtime,
    }


def save_accounts_data(data: Any, *, reload: bool = True) -> Dict[str, Any]:
    """
    校验并写入 ``accounts.local.json``。

    @param data: JSON 对象（dict）
    @param reload: 写盘后是否热加载 env（accounts 每次 fetch 会重读文件）
    @returns: ok / path / runtime
    """
    if not isinstance(data, dict):
        return {"ok": False, "error": "accounts 须为 JSON 对象"}
    # 序列化一轮以确认可 JSON 化
    try:
        serialized = json.dumps(data, ensure_ascii=False, indent=2)
        json.loads(serialized)
    except (TypeError, ValueError) as exc:
        return {"ok": False, "error": f"JSON 无效: {exc}"}

    ACCOUNTS_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_LOCAL.write_text(serialized + "\n", encoding="utf-8")

    runtime = apply_runtime_reload() if reload else None
    return {
        "ok": True,
        "path": _rel_to_project(ACCOUNTS_LOCAL),
        "runtime": runtime,
    }


def apply_runtime_reload() -> Dict[str, Any]:
    """
    从磁盘 ``.env`` 覆盖加载到 ``os.environ`` 并刷新 ``workflow.config`` 常量。

    @returns: ok / env_path / release_mysql_configured / 摘要字段
    """
    env_path = reload_runtime_config(overwrite_environ=True)
    from workflow import config as cfg

    return {
        "ok": True,
        "env_path": _rel_to_project(env_path) if env_path else None,
        "release_mysql_configured": release_mysql_configured(),
        "storage_backend": cfg.STORAGE_BACKEND,
        "site_origin": cfg.SITE_ORIGIN,
        "jackett_base_url": cfg.JACKETT_BASE_URL,
        "jackett_key_configured": is_jackett_api_key_configured(cfg.JACKETT_API_KEY),
    }
