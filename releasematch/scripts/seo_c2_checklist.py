#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C2 SEO 本地检查 — 自动化 §6.1～6.3（GSC 提交前 dist 验收）。

@file scripts/seo_c2_checklist.py
@description
  针对 ``portal/dist/`` 静态产物执行 [页面SEO分析与优化方向.md](../worklogs/2026-07-03/页面SEO分析与优化方向.md) §六
  中可在本地完成的检查项；§6.4 GSC 与 HTTPS/HSTS 标记为 SKIP。

  用法::
    python scripts/seo_c2_checklist.py
    python scripts/seo_c2_checklist.py --prepare   # 先 generate all + 同步静态壳
    python scripts/seo_c2_checklist.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple
from urllib.parse import urlparse

# 保证从 releasematch/ 根目录可 import workflow / portal
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from portal.generator.sitemap import (  # noqa: E402
    DEFAULT_MAX_CONTENT_URLS,
    TRUST_PATHS,
)
from workflow.config import PROJECT_ROOT, SHOW_IG_DEBUG, SITE_ORIGIN  # noqa: E402

CheckStatus = Literal["pass", "fail", "warn", "skip"]

# dist 默认路径
DEFAULT_DIST = PROJECT_ROOT / "portal" / "dist"

# §6.2 内容页（episode/movie）要求的 Open Graph 字段
REQUIRED_OG_PROPERTIES: Tuple[str, ...] = (
    "og:title",
    "og:description",
    "og:url",
    "og:type",
    "og:site_name",
)

# §6.3 疑似托管视频 / 冒牌播放器片段（小写匹配）
FORBIDDEN_MEDIA_SNIPPETS: Tuple[str, ...] = (
    "<video",
    "jwplayer",
    "video.js",
    "youtube.com/embed",
    "vimeo.com/video",
    "dailymotion.com/embed",
)

# Magnet 链接应含 nofollow、新窗口打开与安全 rel
MAGNET_HREF_PATTERN = re.compile(
    r'<a\b[^>]*href=["\']magnet:[^"\']*["\'][^>]*>',
    re.IGNORECASE,
)

# 出站 http(s) 链接（排除本站 releasematch.io 与相对路径）
EXTERNAL_HTTP_HREF_PATTERN = re.compile(
    r'<a\b[^>]*href=["\']https?://[^"\']+["\'][^>]*>',
    re.IGNORECASE,
)


def _outbound_link_tag_issues(tag: str, *, label: str) -> List[str]:
    """
    校验单个出站 <a> 标签是否含 nofollow、target=_blank、noopener。

    @param tag: 完整 <a ...> 开标签字符串
    @param label: 问题前缀，如路径或链接类型
    @returns: 问题描述列表（空表示通过）
    """
    lower = tag.lower()
    issues: List[str] = []
    if "nofollow" not in lower:
        issues.append(f"{label}: 出站链接缺 rel=nofollow")
    if 'target="_blank"' not in lower and "target='_blank'" not in lower:
        issues.append(f"{label}: 出站链接缺 target=_blank")
    if "noopener" not in lower:
        issues.append(f"{label}: 出站链接缺 rel=noopener")
    return issues


def _is_same_site_http_href(href: str, site_origin: str) -> bool:
    """
    判断 http(s) href 是否为本站 origin（不算外出链）。

    @param href: a 标签 href 属性值
    @param site_origin: 如 https://releasematch.io
    @returns: True 表示站内链，跳过出站校验
    """
    try:
        parsed = urlparse(href)
    except ValueError:
        return False
    if not parsed.netloc:
        return True
    origin_host = urlparse(site_origin).netloc.lower()
    return parsed.netloc.lower() == origin_host


@dataclass
class CheckItem:
    """
    单项检查结果。

    @var section: 所属章节，如 ``6.1``
    @var check_id: 稳定 ID，如 ``6.1.robots_txt``
    @var title: 人类可读标题
    @var status: pass | fail | warn | skip
    @var detail: 说明或失败原因
    @var evidence: 可选附加数据（JSON 输出用）
    """

    section: str
    check_id: str
    title: str
    status: CheckStatus
    detail: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckReport:
    """
    完整检查报告。

    @var items: 全部检查项
    @var dist_root: 检查的 dist 目录
    @var site_origin: 期望的 canonical origin
    """

    items: List[CheckItem] = field(default_factory=list)
    dist_root: str = ""
    site_origin: str = ""

    def add(self, item: CheckItem) -> None:
        """追加一条结果。"""
        self.items.append(item)

    @property
    def fail_count(self) -> int:
        """失败项数量。"""
        return sum(1 for i in self.items if i.status == "fail")

    @property
    def warn_count(self) -> int:
        """警告项数量。"""
        return sum(1 for i in self.items if i.status == "warn")

    @property
    def pass_count(self) -> int:
        """通过项数量。"""
        return sum(1 for i in self.items if i.status == "pass")

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 友好字典。"""
        return {
            "ok": self.fail_count == 0,
            "dist_root": self.dist_root,
            "site_origin": self.site_origin,
            "summary": {
                "pass": self.pass_count,
                "fail": self.fail_count,
                "warn": self.warn_count,
                "skip": sum(1 for i in self.items if i.status == "skip"),
            },
            "items": [asdict(i) for i in self.items],
        }


def _canonical_path_to_dist_file(dist_root: Path, canonical_path: str) -> Path:
    """
    将 canonical 路径映射为 dist 下 HTML 文件路径。

    @param dist_root: portal/dist 根目录
    @param canonical_path: 如 ``/breaking-bad/s4e6/``
    @returns: 如 ``dist/breaking-bad/s4e6/index.html``
    """
    parts = [p for p in canonical_path.strip("/").split("/") if p]
    if not parts:
        return dist_root / "index.html"
    return dist_root / Path(*parts) / "index.html"


def _path_from_sitemap_loc(loc: str, site_origin: str) -> str:
    """
    从 sitemap ``<loc>`` 提取 canonical 路径（含 trailing slash）。

    @param loc: 完整 URL
    @param site_origin: 期望 origin
    @returns: 如 ``/breaking-bad/s4e6/``
    """
    parsed = urlparse(loc)
    path = parsed.path or "/"
    if not path.endswith("/"):
        path = f"{path}/"
    return path


def parse_sitemap_locs(sitemap_file: Path, site_origin: str) -> List[str]:
    """
    解析 sitemap.xml，返回 canonical 路径列表。

    @param sitemap_file: sitemap 文件路径
    @param site_origin: 用于校验 loc 前缀
    @returns: canonical 路径列表
    """
    tree = ET.parse(sitemap_file)
    root = tree.getroot()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs: List[str] = []
    for url_el in root.findall("sm:url", ns):
        loc_el = url_el.find("sm:loc", ns)
        if loc_el is not None and loc_el.text:
            locs.append(_path_from_sitemap_loc(loc_el.text.strip(), site_origin))
    return locs


def extract_head_fields(html: str) -> Dict[str, Any]:
    """
    从 HTML 提取 head 关键字段（正则，无第三方依赖）。

    @param html: 完整 HTML 文本
    @returns: title、meta、canonical、og 等字典
    """
    def _meta(name: str) -> Optional[str]:
        pattern = rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]*)"'
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            return m.group(1)
        pattern2 = rf'<meta\s+content="([^"]*)"\s+name="{re.escape(name)}"'
        m2 = re.search(pattern2, html, re.IGNORECASE)
        return m2.group(1) if m2 else None

    def _og(property_name: str) -> Optional[str]:
        pattern = rf'<meta\s+property="{re.escape(property_name)}"\s+content="([^"]*)"'
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            return m.group(1)
        pattern2 = rf'<meta\s+content="([^"]*)"\s+property="{re.escape(property_name)}"'
        m2 = re.search(pattern2, html, re.IGNORECASE)
        return m2.group(1) if m2 else None

    title_m = re.search(r"<title>([^<]*)</title>", html, re.IGNORECASE)
    canon_m = re.search(
        r'<link\s+rel="canonical"\s+href="([^"]*)"',
        html,
        re.IGNORECASE,
    )
    lang_m = re.search(r'<html\s+lang="([^"]*)"', html, re.IGNORECASE)
    favicon_m = re.search(
        r'<link\s+rel="(?:icon|shortcut icon)"\s+href="([^"]*)"',
        html,
        re.IGNORECASE,
    )

    og: Dict[str, str] = {}
    for prop in REQUIRED_OG_PROPERTIES:
        val = _og(prop)
        if val:
            og[prop] = val

    return {
        "title": title_m.group(1).strip() if title_m else None,
        "description": _meta("description"),
        "robots": _meta("robots"),
        "canonical": canon_m.group(1) if canon_m else None,
        "lang": lang_m.group(1) if lang_m else None,
        "favicon_href": favicon_m.group(1) if favicon_m else None,
        "og": og,
        "has_tv_episode_schema": '"@type": "TVEpisode"' in html
        or '"@type":"TVEpisode"' in html,
        "has_movie_schema": '"@type": "Movie"' in html or '"@type":"Movie"' in html,
    }


def _load_page_db_row(canonical_path: str) -> Optional[Dict[str, Any]]:
    """
    按 canonical_path 查询 media_pages 行（含 has_recommended）。

    @param canonical_path: 页面路径
    @returns: 字典或 None（无 DB / 无行）
    """
    try:
        from workflow.storage.mysql_store import MySQLStore

        store = MySQLStore()
        conn = store._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.page_id, p.page_type, p.magnet_count, p.robots_noindex,
                       p.page_status,
                       EXISTS (
                         SELECT 1 FROM download_resources d
                         WHERE d.page_id = p.page_id AND d.is_recommended = 1
                       ) AS has_recommended
                FROM media_pages p
                WHERE p.canonical_path = %s
                LIMIT 1
                """,
                (canonical_path,),
            )
            row = cur.fetchone()
        conn.close()
        return row
    except Exception:
        return None


def run_prepare_only() -> Tuple[bool, str]:
    """
    执行 ``deploy_cf_pages.sh --prepare-only`` 生成 dist。

    @returns: (成功与否, 输出摘要)
    """
    script = PROJECT_ROOT / "scripts" / "deploy_cf_pages.sh"
    if not script.is_file():
        return False, f"脚本不存在: {script}"
    try:
        proc = subprocess.run(
            ["bash", str(script), "--prepare-only"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode == 0, output.strip()[-2000:]
    except subprocess.TimeoutExpired:
        return False, "generate 超时（>600s）"
    except OSError as exc:
        return False, str(exc)


def check_6_1_technical(report: CheckReport, dist_root: Path, site_origin: str) -> None:
    """
    §6.1 技术 SEO 检查。

    @param report: 报告对象（就地追加）
    @param dist_root: dist 根目录
    @param site_origin: RM_SITE_ORIGIN
    """
    # robots.txt + Sitemap 指向
    robots_candidates = [
        dist_root / "static" / "robots.txt",
        dist_root / "robots.txt",
        PROJECT_ROOT / "portal" / "static" / "robots.txt",
    ]
    robots_file = next((p for p in robots_candidates if p.is_file()), None)
    if not robots_file:
        report.add(
            CheckItem(
                "6.1",
                "6.1.robots_txt",
                "robots.txt 存在且声明 Sitemap",
                "fail",
                "未找到 robots.txt（请先 --prepare 或 generate all）",
            )
        )
    else:
        text = robots_file.read_text(encoding="utf-8")
        sitemap_lines = [ln for ln in text.splitlines() if ln.strip().lower().startswith("sitemap:")]
        expected_sitemap = f"{site_origin.rstrip('/')}/sitemap.xml"
        if not sitemap_lines:
            report.add(
                CheckItem(
                    "6.1",
                    "6.1.robots_txt",
                    "robots.txt 存在且声明 Sitemap",
                    "fail",
                    "robots.txt 缺少 Sitemap: 行",
                    {"file": str(robots_file)},
                )
            )
        elif not any(expected_sitemap in ln for ln in sitemap_lines):
            report.add(
                CheckItem(
                    "6.1",
                    "6.1.robots_txt",
                    "robots.txt 存在且声明 Sitemap",
                    "warn",
                    f"Sitemap 行与 RM_SITE_ORIGIN 不完全一致，期望含 {expected_sitemap}",
                    {"lines": sitemap_lines},
                )
            )
        else:
            report.add(
                CheckItem(
                    "6.1",
                    "6.1.robots_txt",
                    "robots.txt 存在且声明 Sitemap",
                    "pass",
                    str(robots_file),
                )
            )

    # sitemap.xml 结构与 URL 规则
    sitemap_file = dist_root / "sitemap.xml"
    if not sitemap_file.is_file():
        report.add(
            CheckItem(
                "6.1",
                "6.1.sitemap",
                "sitemap.xml 存在且 URL 规则符合 D3",
                "fail",
                f"缺少 {sitemap_file}",
            )
        )
        sitemap_paths: List[str] = []
    else:
        sitemap_paths = parse_sitemap_locs(sitemap_file, site_origin)
        trust_set = set(TRUST_PATHS)
        content_paths = [
            p for p in sitemap_paths if p != "/" and p not in trust_set
        ]
        hub_in_sitemap = [p for p in sitemap_paths if p.count("/") == 2 and p.endswith("/")]
        # Hub 形如 /breaking-bad/ — 单段 slug；内容页至少两段或 movie 单段带 slug
        issues: List[str] = []
        if "/" not in sitemap_paths or sitemap_paths[0] != "/":
            issues.append("sitemap 应含首页 /")
        for tp in TRUST_PATHS:
            if tp not in sitemap_paths:
                issues.append(f"缺少 Trust 页 {tp}")
        if len(content_paths) > DEFAULT_MAX_CONTENT_URLS:
            issues.append(
                f"内容页 {len(content_paths)} 超过上限 {DEFAULT_MAX_CONTENT_URLS}"
            )

        status: CheckStatus = "fail" if issues else "pass"
        report.add(
            CheckItem(
                "6.1",
                "6.1.sitemap",
                "sitemap.xml 存在且 URL 规则符合 D3",
                status,
                "; ".join(issues) if issues else f"{len(sitemap_paths)} URL（内容 {len(content_paths)}）",
                {
                    "url_count": len(sitemap_paths),
                    "content_count": len(content_paths),
                    "file": str(sitemap_file),
                },
            )
        )

    # 抽查 canonical + trailing slash
    sample_paths = [p for p in sitemap_paths if p != "/"][:10]
    canon_issues: List[str] = []
    for path in sample_paths:
        html_file = _canonical_path_to_dist_file(dist_root, path)
        if not html_file.is_file():
            canon_issues.append(f"缺 HTML: {path}")
            continue
        fields = extract_head_fields(html_file.read_text(encoding="utf-8"))
        canon = fields.get("canonical") or ""
        if not canon:
            canon_issues.append(f"{path}: 无 canonical")
            continue
        if not canon.endswith("/"):
            canon_issues.append(f"{path}: canonical 无 trailing slash")
        expected_prefix = site_origin.rstrip("/")
        if not canon.startswith(expected_prefix):
            canon_issues.append(f"{path}: canonical origin 非 {expected_prefix}")

    report.add(
        CheckItem(
            "6.1",
            "6.1.canonical_sample",
            f"抽查 {len(sample_paths)} 页 canonical 唯一且 trailing slash",
            "fail" if canon_issues else ("pass" if sample_paths else "warn"),
            "; ".join(canon_issues[:5]) if canon_issues else f"已抽查 {len(sample_paths)} 页",
            {"sample_size": len(sample_paths), "issues": canon_issues},
        )
    )

    # 404 / 410
    for name, expect_noindex in (("404.html", True), ("410.html", True)):
        err_file = dist_root / name
        if not err_file.is_file():
            report.add(
                CheckItem(
                    "6.1",
                    f"6.1.{name}",
                    f"{name} 存在",
                    "fail",
                    f"缺少 {err_file}",
                )
            )
            continue
        robots = extract_head_fields(err_file.read_text(encoding="utf-8")).get("robots") or ""
        if expect_noindex and "noindex" not in robots.lower():
            report.add(
                CheckItem(
                    "6.1",
                    f"6.1.{name}",
                    f"{name} 含 noindex",
                    "fail",
                    f"robots={robots!r}",
                )
            )
        else:
            report.add(
                CheckItem(
                    "6.1",
                    f"6.1.{name}",
                    f"{name} 存在且 noindex",
                    "pass",
                    robots,
                )
            )

    report.add(
        CheckItem(
            "6.1",
            "6.1.410_http",
            "410 返回 HTTP 410 状态码",
            "skip",
            "需 Cloudflare Pages 路由配置；本地静态文件仅可验 HTML 内容",
        )
    )

    # RM_SHOW_IG_DEBUG
    if SHOW_IG_DEBUG:
        report.add(
            CheckItem(
                "6.1",
                "6.1.ig_debug",
                "RM_SHOW_IG_DEBUG 生产应为 false",
                "fail",
                "当前 RM_SHOW_IG_DEBUG=true，生成页可能全站 noindex",
            )
        )
    else:
        report.add(
            CheckItem(
                "6.1",
                "6.1.ig_debug",
                "RM_SHOW_IG_DEBUG 应为 false",
                "pass",
                "RM_SHOW_IG_DEBUG=false",
            )
        )

    # 生成页不应含 IG debug 全站 noindex（抽查首页）
    home_file = dist_root / "index.html"
    if home_file.is_file():
        home_html = home_file.read_text(encoding="utf-8")
        if 'content="noindex,nofollow"' in home_html and SHOW_IG_DEBUG:
            report.add(
                CheckItem(
                    "6.1",
                    "6.1.ig_debug_html",
                    "首页无 IG debug 全站 noindex",
                    "fail",
                    "首页含 noindex,nofollow",
                )
            )
        elif 'content="noindex,nofollow"' in home_html:
            report.add(
                CheckItem(
                    "6.1",
                    "6.1.ig_debug_html",
                    "首页无意外 noindex,nofollow",
                    "warn",
                    "首页含 noindex,nofollow（请确认非 IG debug）",
                )
            )

    report.add(
        CheckItem(
            "6.1",
            "6.1.https_hsts",
            "HTTPS + HSTS",
            "skip",
            "仅生产域名 releasematch.io 可验；本地 dist 检查不涉及",
        )
    )


def check_6_2_page_head(
    report: CheckReport,
    dist_root: Path,
    site_origin: str,
    sitemap_paths: Sequence[str],
) -> None:
    """
    §6.2 页面 head 检查。

    @param report: 报告对象
    @param dist_root: dist 根
    @param site_origin: origin
    @param sitemap_paths: sitemap 中的 canonical 路径
    """
    trust_set = set(TRUST_PATHS)
    content_paths = [p for p in sitemap_paths if p != "/" and p not in trust_set]

    content_issues: List[str] = []
    for path in content_paths[:15]:
        html_file = _canonical_path_to_dist_file(dist_root, path)
        if not html_file.is_file():
            content_issues.append(f"{path}: 缺 HTML")
            continue
        fields = extract_head_fields(html_file.read_text(encoding="utf-8"))
        if not fields.get("title"):
            content_issues.append(f"{path}: 缺 title")
        if not fields.get("description"):
            content_issues.append(f"{path}: 缺 meta description")
        robots = (fields.get("robots") or "").lower()
        if "noindex" in robots:
            content_issues.append(f"{path}: sitemap 页不应 noindex")
        if not fields.get("canonical"):
            content_issues.append(f"{path}: 缺 canonical")
        missing_og = [k for k in REQUIRED_OG_PROPERTIES if k not in fields.get("og", {})]
        if missing_og:
            content_issues.append(f"{path}: 缺 OG {missing_og}")

    report.add(
        CheckItem(
            "6.2",
            "6.2.content_head",
            "单集/电影：title、description、robots、canonical、OG",
            "fail" if content_issues else "pass",
            "; ".join(content_issues[:8]) if content_issues else f"已验 {min(len(content_paths), 15)} 个内容页",
            {"checked": min(len(content_paths), 15), "issues": content_issues},
        )
    )

    # Hub 页（dist 内 show_hub，不在 sitemap）
    hub_candidates: List[Path] = []
    for child in dist_root.iterdir():
        if not child.is_dir() or child.name in ("static", "trust"):
            continue
        index = child / "index.html"
        if index.is_file():
            # 有子目录 s*e* 则视为 show hub 根
            has_episodes = any(
                sub.is_dir() and re.match(r"s\d+e\d+", sub.name, re.I)
                for sub in child.iterdir()
                if sub.is_dir()
            )
            if has_episodes:
                hub_candidates.append(index)

    hub_issues: List[str] = []
    for hub_file in hub_candidates[:3]:
        fields = extract_head_fields(hub_file.read_text(encoding="utf-8"))
        if not fields.get("description"):
            hub_issues.append(f"{hub_file.parent.name}: 缺 description")
        robots = (fields.get("robots") or "").lower()
        if "noindex" not in robots:
            hub_issues.append(f"{hub_file.parent.name}: 应为 noindex（D2）")

    if not hub_candidates:
        report.add(
            CheckItem(
                "6.2",
                "6.2.hub_head",
                "Hub：description + noindex,follow（D2）",
                "warn",
                "dist 中未找到 Hub 页（可先 generate all）",
            )
        )
    else:
        report.add(
            CheckItem(
                "6.2",
                "6.2.hub_head",
                "Hub：description + noindex,follow（D2）",
                "fail" if hub_issues else "pass",
                "; ".join(hub_issues) if hub_issues else f"已验 {len(hub_candidates[:3])} 个 Hub",
            )
        )

    # Trust 四页 description
    trust_issues: List[str] = []
    for tp in TRUST_PATHS:
        rel = tp.strip("/")
        trust_html = dist_root / rel / "index.html"
        if not trust_html.is_file():
            trust_issues.append(f"{tp}: 缺 HTML")
            continue
        fields = extract_head_fields(trust_html.read_text(encoding="utf-8"))
        if not fields.get("description"):
            trust_issues.append(f"{tp}: 缺 meta description")

    report.add(
        CheckItem(
            "6.2",
            "6.2.trust_description",
            "Trust 五页均有 description",
            "fail" if trust_issues else "pass",
            "; ".join(trust_issues) if trust_issues else f"{len(TRUST_PATHS)}/{len(TRUST_PATHS)} OK",
        )
    )

    # favicon
    favicon_paths = [
        dist_root / "static" / "favicon.ico",
        PROJECT_ROOT / "portal" / "static" / "favicon.ico",
    ]
    favicon_exists = any(p.is_file() for p in favicon_paths)
    home_fields = {}
    home_file = dist_root / "index.html"
    if home_file.is_file():
        home_fields = extract_head_fields(home_file.read_text(encoding="utf-8"))

    if favicon_exists and home_fields.get("favicon_href"):
        report.add(
            CheckItem("6.2", "6.2.favicon", "favicon 文件 + head 声明", "pass", home_fields["favicon_href"])
        )
    elif favicon_exists:
        report.add(
            CheckItem(
                "6.2",
                "6.2.favicon",
                "favicon 文件 + head 声明",
                "warn",
                "有 favicon.ico 但首页未 link rel=icon",
            )
        )
    else:
        report.add(
            CheckItem(
                "6.2",
                "6.2.favicon",
                "favicon 可加载",
                "fail",
                "缺少 static/favicon.ico 与 head link（T-SEO-05 未做）",
            )
        )


def check_6_3_content_ig(
    report: CheckReport,
    dist_root: Path,
    sitemap_paths: Sequence[str],
    *,
    use_db: bool,
) -> None:
    """
    §6.3 内容与 IG 检查。

    @param report: 报告对象
    @param dist_root: dist 根
    @param sitemap_paths: sitemap 路径
    @param use_db: 是否交叉验证 MySQL
    """
    trust_set = set(TRUST_PATHS)
    content_paths = [p for p in sitemap_paths if p != "/" and p not in trust_set]

    db_issues: List[str] = []
    if use_db and content_paths:
        for path in content_paths:
            row = _load_page_db_row(path)
            if row is None:
                db_issues.append(f"{path}: DB 无行或连接失败")
                continue
            magnet = int(row.get("magnet_count") or 0)
            if magnet < 2:
                db_issues.append(f"{path}: magnet_count={magnet} < 2")
            if not row.get("has_recommended"):
                db_issues.append(f"{path}: 无 Recommended")
            if int(row.get("robots_noindex") or 0):
                db_issues.append(f"{path}: robots_noindex=1 不应在 sitemap")
    elif not use_db:
        report.add(
            CheckItem(
                "6.3",
                "6.3.db_magnet_recommended",
                "sitemap 页 magnet≥2 且有 Recommended",
                "skip",
                "已 --no-db，跳过 MySQL 交叉验证",
            )
        )

    if use_db:
        report.add(
            CheckItem(
                "6.3",
                "6.3.db_magnet_recommended",
                "sitemap 页 magnet≥2 且有 Recommended",
                "fail" if db_issues else "pass",
                "; ".join(db_issues[:6]) if db_issues else f"DB 交叉验证 {len(content_paths)} 页",
                {"issues": db_issues},
            )
        )

    # magnet / 外出 http(s) 链：nofollow + 新窗口 + noopener
    magnet_issues: List[str] = []
    external_http_issues: List[str] = []
    for path in content_paths[:20]:
        html_file = _canonical_path_to_dist_file(dist_root, path)
        if not html_file.is_file():
            continue
        html = html_file.read_text(encoding="utf-8")
        for tag in MAGNET_HREF_PATTERN.findall(html):
            magnet_issues.extend(_outbound_link_tag_issues(tag, label=f"{path}: magnet"))
            if magnet_issues:
                break
        for tag in EXTERNAL_HTTP_HREF_PATTERN.findall(html):
            href_match = re.search(r'href=["\']([^"\']+)["\']', tag, re.IGNORECASE)
            if not href_match:
                continue
            href = href_match.group(1)
            if _is_same_site_http_href(href, SITE_ORIGIN):
                continue
            external_http_issues.extend(
                _outbound_link_tag_issues(tag, label=f"{path}: 外出 http")
            )
            if external_http_issues:
                break

    outbound_issues = magnet_issues + external_http_issues
    report.add(
        CheckItem(
            "6.3",
            "6.3.magnet_nofollow",
            "Magnet 链接均为 rel=nofollow",
            "fail" if magnet_issues else "pass",
            "; ".join(magnet_issues[:5]) if magnet_issues else f"已扫 {min(len(content_paths), 20)} 页",
        )
    )
    report.add(
        CheckItem(
            "6.3",
            "6.3.outbound_link_policy",
            "外出链接 target=_blank 且 rel 含 nofollow noopener",
            "fail" if outbound_issues else "pass",
            "; ".join(outbound_issues[:6]) if outbound_issues else f"已扫 {min(len(content_paths), 20)} 页",
        )
    )

    # 无托管视频 / 冒牌播放器
    media_issues: List[str] = []
    scan_paths = list(content_paths[:20]) + ["/"]
    for path in scan_paths:
        html_file = _canonical_path_to_dist_file(dist_root, path)
        if not html_file.is_file():
            continue
        lower = html_file.read_text(encoding="utf-8").lower()
        for snippet in FORBIDDEN_MEDIA_SNIPPETS:
            if snippet in lower:
                media_issues.append(f"{path}: 含 {snippet!r}")
                break

    report.add(
        CheckItem(
            "6.3",
            "6.3.no_video_hosting",
            "无冒牌播放器 / 托管视频",
            "fail" if media_issues else "pass",
            "; ".join(media_issues) if media_issues else "未发现 video/iframe 嵌入",
        )
    )

    report.add(
        CheckItem(
            "6.3",
            "6.3.gsc",
            "GSC 属性验证与 sitemap 提交",
            "skip",
            "§6.4 仅公网 + Google Search Console 可执行",
        )
    )


def run_checks(
    dist_root: Path,
    site_origin: str,
    *,
    use_db: bool = True,
) -> CheckReport:
    """
    执行全部 §6.1～6.3 检查。

    @param dist_root: portal/dist
    @param site_origin: RM_SITE_ORIGIN
    @param use_db: 是否连接 MySQL 做交叉验证
    @returns: CheckReport
    """
    report = CheckReport(dist_root=str(dist_root), site_origin=site_origin)

    if not dist_root.is_dir():
        report.add(
            CheckItem(
                "6.1",
                "6.1.dist",
                "dist 目录存在",
                "fail",
                f"缺少 {dist_root}，请运行: python scripts/seo_c2_checklist.py --prepare",
            )
        )
        return report

    sitemap_file = dist_root / "sitemap.xml"
    sitemap_paths: List[str] = []
    if sitemap_file.is_file():
        sitemap_paths = parse_sitemap_locs(sitemap_file, site_origin)

    check_6_1_technical(report, dist_root, site_origin)
    check_6_2_page_head(report, dist_root, site_origin, sitemap_paths)
    check_6_3_content_ig(report, dist_root, sitemap_paths, use_db=use_db)
    return report


def print_report(report: CheckReport) -> None:
    """
    人类可读输出。

    @param report: 检查报告
    """
    icons = {"pass": "✅", "fail": "❌", "warn": "⚠️", "skip": "⏭️"}
    current_section = ""
    print(f"C2 SEO 本地检查 — dist={report.dist_root}")
    print(f"site_origin={report.site_origin}\n")
    for item in report.items:
        if item.section != current_section:
            current_section = item.section
            print(f"§{current_section}")
        icon = icons.get(item.status, "?")
        line = f"  {icon} [{item.check_id}] {item.title}"
        if item.detail:
            line += f" — {item.detail}"
        print(line)
    print()
    print(
        f"汇总: pass={report.pass_count} fail={report.fail_count} "
        f"warn={report.warn_count} skip="
        f"{sum(1 for i in report.items if i.status == 'skip')}"
    )
    if report.fail_count == 0:
        print("结论: 本地 §6.1～6.3 无 FAIL（仍须上线后验 HTTPS 与 GSC）")
    else:
        print("结论: 存在 FAIL，请修复后再部署 / GSC 提交")


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(
        description="C2 SEO 本地检查（§6.1～6.3，对应 worklogs SEO 文档 §六）",
    )
    parser.add_argument(
        "--dist",
        default=str(DEFAULT_DIST),
        help=f"dist 目录，默认 {DEFAULT_DIST}",
    )
    parser.add_argument(
        "--site-origin",
        default=SITE_ORIGIN,
        help=f"期望 canonical origin，默认 RM_SITE_ORIGIN={SITE_ORIGIN}",
    )
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="检查前先执行 deploy_cf_pages.sh --prepare-only",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="跳过 MySQL 交叉验证（无库环境）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 报告",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """
    CLI 入口。

    @param argv: 命令行参数
    @returns: 0=无 fail；1=有 fail；2=prepare 失败
    """
    args = build_parser().parse_args(argv)
    dist_root = Path(args.dist).resolve()

    if args.prepare:
        ok, detail = run_prepare_only()
        if not ok:
            print(json.dumps({"ok": False, "step": "prepare", "error": detail}, ensure_ascii=False))
            return 2

    report = run_checks(
        dist_root,
        args.site_origin,
        use_db=not args.no_db,
    )

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print_report(report)

    return 1 if report.fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
