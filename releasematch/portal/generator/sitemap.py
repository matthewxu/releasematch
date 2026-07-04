#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sitemap.xml 生成器 — C2 冷启动首批 URL（≤30 内容页 + Trust + 首页）。

@module portal.generator.sitemap
@description
  按 SEO 决策 D3：优先 validation-pages.json，再补 DB 中 indexable 且有 Recommended 的页。
  排除 Hub、noindex、410/DMCA 路径。
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.dom import minidom

from workflow.config import PROJECT_ROOT, SITE_ORIGIN
from workflow.storage.mysql_store import MySQLStore

# Trust 四页固定路径（trailing slash）
TRUST_PATHS: Tuple[str, ...] = (
    "/trust/about/",
    "/trust/privacy/",
    "/trust/dmca/",
    "/trust/how-matching-works/",
)

# D3：内容页上限（不含首页与 Trust）
DEFAULT_MAX_CONTENT_URLS = 30

# C1 验证集优先顺序
DEFAULT_VALIDATION_JSON = (
    PROJECT_ROOT / "worklogs" / "2026-07-03" / "validation-pages.json"
)

# DMCA / 410 排除路径（dist 不生成 + sitemap 排除）
GONE_CANONICAL_PATHS: Tuple[str, ...] = ()


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
    max_content_urls: int = DEFAULT_MAX_CONTENT_URLS,
    validation_json: Path = DEFAULT_VALIDATION_JSON,
) -> List[Dict[str, Any]]:
    """
    收集 sitemap URL 条目（首页 + Trust + indexable 内容页）。

    @param store: MySQLStore；None 时新建
    @param max_content_urls: 内容页上限
    @param validation_json: 优先 page_id 清单
    @returns: 含 loc_path、lastmod 的字典列表
    """
    db = store or MySQLStore()
    priority_ids = load_validation_priority_ids(validation_json)
    candidates = db.list_sitemap_content_pages()

    by_id = {row["page_id"]: row for row in candidates}
    ordered_content: List[Dict[str, Any]] = []

    for page_id in priority_ids:
        if page_id in by_id and len(ordered_content) < max_content_urls:
            ordered_content.append(by_id.pop(page_id))

    for row in sorted(by_id.values(), key=lambda r: r["page_id"]):
        if len(ordered_content) >= max_content_urls:
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
        loc.text = f"{origin}{item['loc_path']}"
        lastmod = ET.SubElement(url_el, "lastmod")
        lastmod.text = item.get("lastmod") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rough = ET.tostring(urlset, encoding="unicode")
    return minidom.parseString(rough).toprettyxml(indent="  ", encoding=None)


def write_sitemap(
    out_root: Path,
    site_origin: str = SITE_ORIGIN,
    *,
    max_content_urls: int = DEFAULT_MAX_CONTENT_URLS,
    validation_json: Path = DEFAULT_VALIDATION_JSON,
) -> Dict[str, Any]:
    """
    写入 portal/dist/sitemap.xml。

    @param out_root: dist 根目录
    @param site_origin: canonical origin
    @param max_content_urls: 内容页上限
    @param validation_json: 优先 page_id JSON
    @returns: 生成摘要
    """
    entries = collect_sitemap_entries(
        max_content_urls=max_content_urls,
        validation_json=validation_json,
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
        "max_content_urls": max_content_urls,
    }
