#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sitemap.xml 生成器 — C2 冷启动首批 URL（内容页上限可配 + Trust 6 + 首页）。

@module portal.generator.sitemap
@description
  按 SEO 决策 D3：优先 validation-pages.json，再补 DB 中 indexable 且有 Recommended 的页。
  排除 Hub、noindex、410/DMCA 路径；``<loc>`` 对非 ASCII 路径做百分号编码。
  Ops 可读写 ``sitemap_config.json``，并单独触发 ``write_sitemap``。
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from xml.dom import minidom

from workflow.config import PROJECT_ROOT, SITE_ORIGIN
from workflow.storage.mysql_store import MySQLStore

# Trust 六页固定路径（trailing slash）；含 Contact、speed-and-grab
TRUST_PATHS: Tuple[str, ...] = (
    "/trust/about/",
    "/trust/contact/",
    "/trust/privacy/",
    "/trust/dmca/",
    "/trust/how-matching-works/",
    "/trust/speed-and-grab/",
)

# D3：内容页上限默认值（不含首页与 Trust）；Ops 可覆盖
DEFAULT_MAX_CONTENT_URLS = 30

# C1 验证集优先顺序（相对 PROJECT_ROOT 的默认路径）
DEFAULT_VALIDATION_JSON_REL = "worklogs/2026-07-03/validation-pages.json"

# C1 验证集绝对路径（兼容旧调用）
DEFAULT_VALIDATION_JSON = PROJECT_ROOT / DEFAULT_VALIDATION_JSON_REL

# Ops / generate 共用的 sitemap 配置文件（相对 PROJECT_ROOT）
SITEMAP_CONFIG_REL = "portal/generator/sitemap_config.json"

# 配置文件绝对路径
SITEMAP_CONFIG_PATH = PROJECT_ROOT / SITEMAP_CONFIG_REL

# 默认静态输出根（与 generate_one.DEFAULT_OUT_ROOT 对齐；本模块不 import generate_one）
DEFAULT_DIST_ROOT: Path = PROJECT_ROOT / "portal" / "dist"

# DMCA / 410 排除路径（dist 不生成 + sitemap 排除）
GONE_CANONICAL_PATHS: Tuple[str, ...] = ()

# 内容页上限硬顶（防止误填过大导致 sitemap 膨胀）
MAX_CONTENT_URLS_HARD_CAP = 5000


def _format_lastmod(updated_at: Optional[str]) -> str:
    """
    将 MySQL updated_at 转为 sitemap ISO8601 lastmod。

    @param updated_at: 如 2026-07-03 12:00:00.000
    @returns: ISO8601 日期或当前 UTC 日期
    """
    text = (updated_at or "").strip()
    if text:
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(text[:26], fmt).replace(tzinfo=timezone.utc)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def encode_sitemap_loc(url: str) -> str:
    """
    将 sitemap ``<loc>`` 规范为百分号编码（非 ASCII 路径必须编码）。

    @param url: 完整 URL（可为未编码 Unicode，或已 percent-encode）
    @returns: path 段已 quote、``/`` 保留的 URL
    @description
      协议见 sitemaps.org：loc 须为可被抓取的编码 URI。
      先 ``unquote`` 再 ``quote``，保证幂等，避免二次编码 ``%``。
      ASCII 路径在 ``quote(..., safe=\"/\")`` 下保持不变。
    """
    parts = urlsplit((url or "").strip())
    raw_path = unquote(parts.path or "/")
    encoded_path = quote(raw_path, safe="/")
    return urlunsplit((parts.scheme, parts.netloc, encoded_path, parts.query, parts.fragment))


def default_sitemap_config() -> Dict[str, Any]:
    """
    返回 sitemap 默认配置字典。

    @returns: max_content_urls / use_validation_priority / validation_json
    """
    return {
        "max_content_urls": DEFAULT_MAX_CONTENT_URLS,
        "use_validation_priority": True,
        "validation_json": DEFAULT_VALIDATION_JSON_REL,
    }


def _clamp_max_content_urls(value: Any) -> int:
    """
    将内容页上限规范为合法正整数。

    @param value: 原始输入
    @returns: 1..MAX_CONTENT_URLS_HARD_CAP
    """
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = DEFAULT_MAX_CONTENT_URLS
    if n < 1:
        n = 1
    if n > MAX_CONTENT_URLS_HARD_CAP:
        n = MAX_CONTENT_URLS_HARD_CAP
    return n


def normalize_sitemap_config(raw: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    规范化 sitemap 配置（缺省填默认、校验字段）。

    @param raw: 原始字典；None 视为空
    @returns: 规范化后的配置
    """
    base = default_sitemap_config()
    src = raw if isinstance(raw, dict) else {}
    max_urls = _clamp_max_content_urls(
        src.get("max_content_urls", base["max_content_urls"])
    )
    use_priority = bool(
        src.get("use_validation_priority", base["use_validation_priority"])
    )
    vj = str(src.get("validation_json") or base["validation_json"]).strip()
    if not vj:
        vj = DEFAULT_VALIDATION_JSON_REL
    # 完整注释：禁止绝对路径越出仓库；仅允许相对 PROJECT_ROOT
    if Path(vj).is_absolute():
        try:
            vj = str(Path(vj).resolve().relative_to(PROJECT_ROOT.resolve()))
        except ValueError:
            vj = DEFAULT_VALIDATION_JSON_REL
    return {
        "max_content_urls": max_urls,
        "use_validation_priority": use_priority,
        "validation_json": vj.replace("\\", "/"),
    }


def load_sitemap_config(path: Path = SITEMAP_CONFIG_PATH) -> Dict[str, Any]:
    """
    从磁盘加载 sitemap 配置；文件缺失时返回默认值（不写盘）。

    @param path: 配置文件路径
    @returns: 规范化配置
    """
    if not path.is_file():
        return default_sitemap_config()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_sitemap_config()
    if not isinstance(raw, dict):
        return default_sitemap_config()
    return normalize_sitemap_config(raw)


def save_sitemap_config(
    raw: Dict[str, Any],
    path: Path = SITEMAP_CONFIG_PATH,
) -> Dict[str, Any]:
    """
    规范化并写入 sitemap 配置文件。

    @param raw: 待保存字段（可部分）
    @param path: 目标路径
    @returns: ok / config / path / error?
    """
    cfg = normalize_sitemap_config({**load_sitemap_config(path), **(raw or {})})
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        return {"ok": False, "error": str(exc), "config": cfg, "path": str(path)}
    return {"ok": True, "config": cfg, "path": str(path)}


def resolve_validation_json_path(
    config: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    根据配置解析验证集 JSON 绝对路径。

    @param config: sitemap 配置；None 时读盘
    @returns: 绝对 Path（文件可不存在）
    """
    cfg = config if isinstance(config, dict) else load_sitemap_config()
    rel = str(cfg.get("validation_json") or DEFAULT_VALIDATION_JSON_REL).strip()
    return (PROJECT_ROOT / rel).resolve()


def resolve_sitemap_options(
    *,
    max_content_urls: Optional[int] = None,
    validation_json: Optional[Path] = None,
    use_validation_priority: Optional[bool] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    合并显式参数与磁盘配置，得到本次生成选项。

    @param max_content_urls: 显式上限；None 用配置
    @param validation_json: 显式验证集路径；None 用配置
    @param use_validation_priority: 是否启用验证集优先；None 用配置
    @param config: 预加载配置；None 时读盘
    @returns: max_content_urls / validation_json Path / use_validation_priority / config
    """
    cfg = normalize_sitemap_config(config if config is not None else load_sitemap_config())
    max_u = (
        _clamp_max_content_urls(max_content_urls)
        if max_content_urls is not None
        else int(cfg["max_content_urls"])
    )
    use_pri = (
        bool(use_validation_priority)
        if use_validation_priority is not None
        else bool(cfg["use_validation_priority"])
    )
    vj_path = (
        Path(validation_json)
        if validation_json is not None
        else resolve_validation_json_path(cfg)
    )
    return {
        "max_content_urls": max_u,
        "validation_json": vj_path,
        "use_validation_priority": use_pri,
        "config": cfg,
    }


def load_validation_priority_ids(
    validation_json: Path = DEFAULT_VALIDATION_JSON,
) -> List[str]:
    """
    读取 validation-pages.json 中的 page_id 优先列表。

    @param validation_json: JSON 路径
    @returns: page_id 列表；文件不存在时返回空列表
    """
    if not validation_json.is_file():
        return []
    raw = json.loads(validation_json.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    ids: List[str] = []
    for item in raw:
        if isinstance(item, dict) and item.get("page_id"):
            ids.append(str(item["page_id"]))
    return ids


def collect_sitemap_entries(
    store: Optional[MySQLStore] = None,
    *,
    max_content_urls: Optional[int] = None,
    validation_json: Optional[Path] = None,
    use_validation_priority: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    收集 sitemap URL 条目（首页 + Trust + indexable 内容页）。

    @param store: MySQLStore；None 时新建
    @param max_content_urls: 内容页上限；None 读 Ops 配置
    @param validation_json: 优先 page_id 清单；None 读配置
    @param use_validation_priority: False 时跳过验证集优先
    @returns: 含 loc_path、lastmod 的字典列表
    """
    opts = resolve_sitemap_options(
        max_content_urls=max_content_urls,
        validation_json=validation_json,
        use_validation_priority=use_validation_priority,
    )
    max_u = int(opts["max_content_urls"])
    vj_path: Path = opts["validation_json"]
    use_pri = bool(opts["use_validation_priority"])

    db = store or MySQLStore()
    priority_ids = load_validation_priority_ids(vj_path) if use_pri else []
    candidates = db.list_sitemap_content_pages()

    by_id = {row["page_id"]: row for row in candidates}
    ordered_content: List[Dict[str, Any]] = []

    for page_id in priority_ids:
        if page_id in by_id and len(ordered_content) < max_u:
            ordered_content.append(by_id.pop(page_id))

    for row in sorted(by_id.values(), key=lambda r: r["page_id"]):
        if len(ordered_content) >= max_u:
            break
        ordered_content.append(row)

    entries: List[Dict[str, Any]] = [
        {"loc_path": "/", "lastmod": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    ]
    for path in TRUST_PATHS:
        entries.append({"loc_path": path, "lastmod": datetime.now(timezone.utc).strftime("%Y-%m-%d")})
    for row in ordered_content:
        path = str(row["canonical_path"])
        if path in GONE_CANONICAL_PATHS:
            continue
        entries.append(
            {
                "loc_path": path,
                "lastmod": _format_lastmod(row.get("updated_at")),
                "page_id": row["page_id"],
            }
        )
    return entries


def build_sitemap_xml(
    entries: List[Dict[str, Any]],
    site_origin: str = SITE_ORIGIN,
) -> str:
    """
    将 URL 条目序列化为 sitemap.xml 字符串。

    @param entries: collect_sitemap_entries 返回值
    @param site_origin: 站点 origin
    @returns: XML 文本
    """
    origin = site_origin.rstrip("/")
    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for item in entries:
        url_el = ET.SubElement(urlset, "url")
        loc = ET.SubElement(url_el, "loc")
        # 非 ASCII slug 必须 percent-encode，否则部分爬虫/校验器拒收
        loc.text = encode_sitemap_loc(f"{origin}{item['loc_path']}")
        lastmod = ET.SubElement(url_el, "lastmod")
        lastmod.text = item.get("lastmod") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rough = ET.tostring(urlset, encoding="unicode")
    return minidom.parseString(rough).toprettyxml(indent="  ", encoding=None)


def write_sitemap(
    out_root: Path,
    site_origin: str = SITE_ORIGIN,
    *,
    max_content_urls: Optional[int] = None,
    validation_json: Optional[Path] = None,
    use_validation_priority: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    写入 portal/dist/sitemap.xml（选项默认读 Ops ``sitemap_config.json``）。

    @param out_root: dist 根目录
    @param site_origin: canonical origin
    @param max_content_urls: 内容页上限；None 用配置
    @param validation_json: 优先 page_id JSON；None 用配置
    @param use_validation_priority: 是否启用验证集优先；None 用配置
    @returns: 生成摘要
    """
    opts = resolve_sitemap_options(
        max_content_urls=max_content_urls,
        validation_json=validation_json,
        use_validation_priority=use_validation_priority,
    )
    max_u = int(opts["max_content_urls"])
    vj_path: Path = opts["validation_json"]
    use_pri = bool(opts["use_validation_priority"])

    entries = collect_sitemap_entries(
        max_content_urls=max_u,
        validation_json=vj_path,
        use_validation_priority=use_pri,
    )
    xml_text = build_sitemap_xml(entries, site_origin=site_origin)
    out_file = out_root / "sitemap.xml"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(xml_text, encoding="utf-8")
    content_count = sum(
        1
        for e in entries
        if e["loc_path"] not in TRUST_PATHS and e["loc_path"] != "/"
    )
    return {
        "ok": True,
        "output_file": str(out_file),
        "url_count": len(entries),
        "content_url_count": content_count,
        "max_content_urls": max_u,
        "use_validation_priority": use_pri,
        "validation_json": str(vj_path),
        "config": opts["config"],
    }


def _count_existing_sitemap_urls(sitemap_file: Path) -> Optional[int]:
    """
    统计已有 sitemap.xml 中的 ``<loc>`` 数量。

    @param sitemap_file: sitemap 路径
    @returns: URL 数；文件不存在或解析失败返回 None
    """
    if not sitemap_file.is_file():
        return None
    try:
        tree = ET.parse(sitemap_file)
    except ET.ParseError:
        return None
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = tree.getroot().findall("sm:url/sm:loc", ns)
    if locs:
        return len(locs)
    # 完整注释：无命名空间时的兜底
    return len(tree.getroot().findall("url/loc"))


def get_sitemap_bundle(
    *,
    out_root: Optional[Path] = None,
    site_origin: str = SITE_ORIGIN,
    preview_limit: int = 40,
) -> Dict[str, Any]:
    """
    Ops 用：配置 + 候选统计 + 将生成预览（不写盘）。

    @param out_root: dist 根；None 时用 portal/dist
    @param site_origin: canonical origin（仅回显）
    @param preview_limit: 预览路径条数上限
    @returns: ok / config / stats / preview / paths
    """
    root = out_root or DEFAULT_DIST_ROOT
    cfg = load_sitemap_config()
    vj_path = resolve_validation_json_path(cfg)
    store = MySQLStore()
    inventory = store.page_inventory_stats()
    eligible = store.list_sitemap_content_pages()
    entries = collect_sitemap_entries(
        store=store,
        max_content_urls=int(cfg["max_content_urls"]),
        validation_json=vj_path,
        use_validation_priority=bool(cfg["use_validation_priority"]),
    )
    content_entries = [
        e for e in entries if e["loc_path"] != "/" and e["loc_path"] not in TRUST_PATHS
    ]
    capped = max(0, len(eligible) - len(content_entries))
    sitemap_file = root / "sitemap.xml"
    existing_count = _count_existing_sitemap_urls(sitemap_file)
    preview = [
        {
            "loc_path": e["loc_path"],
            "page_id": e.get("page_id"),
            "lastmod": e.get("lastmod"),
        }
        for e in entries[: max(0, int(preview_limit))]
    ]
    return {
        "ok": True,
        "config": cfg,
        "config_path": str(SITEMAP_CONFIG_PATH),
        "config_rel": SITEMAP_CONFIG_REL,
        "site_origin": site_origin.rstrip("/"),
        "out_root": str(root),
        "validation_json_path": str(vj_path),
        "validation_json_exists": vj_path.is_file(),
        "trust_count": len(TRUST_PATHS),
        "stats": {
            "media_pages_total": inventory.get("total"),
            "indexable": inventory.get("indexable"),
            "eligible_content": len(eligible),
            "would_include_total": len(entries),
            "would_include_content": len(content_entries),
            "capped_out": capped,
            "existing_sitemap_urls": existing_count,
            "sitemap_exists": sitemap_file.is_file(),
        },
        "preview": preview,
        "preview_truncated": len(entries) > len(preview),
    }
