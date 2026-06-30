#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压制组信誉库加载器。

@module workflow.recommended.groups_registry
@description 从 data/groups.yaml 加载 L0~L4 档位，供 scorer 查询组名与别名。
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

# 默认 YAML 路径（与 scorer 同包下的 data 目录）
_DEFAULT_YAML = Path(__file__).resolve().parent / "data" / "groups.yaml"

# 从 release_group 字段剥离的后缀（indexer / 站点标记，非压制组名）
_STRIP_SUFFIXES = frozenset(
    {
        "eztv",
        "eztvx",
        "yts",
        "yify",
        "rarbg",
        "ettv",
        "ettvx",
    }
)


@lru_cache(maxsize=4)
def _load_index(yaml_path: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    加载 groups.yaml 并构建查找索引。

    @param yaml_path: YAML 文件绝对路径字符串
    @returns: (canonical_lower -> tier, alias_lower -> canonical_name)
    """
    path = Path(yaml_path)
    if not path.is_file():
        return {}, {}

    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    tier_by_canonical: Dict[str, str] = {}
    alias_to_canonical: Dict[str, str] = {}

    for row in data.get("groups") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        tier = str(row.get("tier") or "L4").strip().upper()
        if not name:
            continue
        if tier not in ("L0", "L1", "L2", "L3", "L4"):
            tier = "L4"

        canonical_key = name.lower()
        tier_by_canonical[canonical_key] = tier
        alias_to_canonical[canonical_key] = name

        for alias in row.get("aliases") or []:
            alias_str = str(alias).strip()
            if alias_str:
                alias_to_canonical[alias_str.lower()] = name

    return tier_by_canonical, alias_to_canonical


def _tokenize_group(release_group: str) -> List[str]:
    """
    将 release_group 拆分为候选 token。

    @param release_group: 原始组名字段
    @returns: 去重后的 token 列表（保持顺序）
    """
    raw = release_group.strip()
    if not raw:
        return []

    parts = re.split(r"[\s._\-]+", raw)
    tokens: List[str] = []
    seen: set[str] = set()
    for part in parts:
        key = part.lower()
        if not key or key in _STRIP_SUFFIXES or key in seen:
            continue
        seen.add(key)
        tokens.append(part)
    return tokens


def lookup_group(
    release_group: str,
    yaml_path: Optional[str] = None,
) -> Tuple[str, str]:
    """
    查询压制组 canonical 名与 tier。

    @param release_group: ResourceItem.release_group
    @param yaml_path: 可选自定义 groups.yaml 路径
    @returns: (canonical_name, tier)；未知时 ("", "L4")
    """
    if not release_group or not release_group.strip():
        return "", "L4"

    path = str(Path(yaml_path) if yaml_path else _DEFAULT_YAML)
    tier_by_canonical, alias_to_canonical = _load_index(path)

    if not tier_by_canonical:
        return "", "L4"

    # 1) 整串精确匹配
    whole = release_group.strip().lower()
    if whole in alias_to_canonical:
        canonical = alias_to_canonical[whole]
        return canonical, tier_by_canonical.get(canonical.lower(), "L4")

    # 2) 按 token 匹配（优先较长 token）
    tokens = _tokenize_group(release_group)
    tokens_sorted = sorted(tokens, key=len, reverse=True)
    for token in tokens_sorted:
        key = token.lower()
        if key in alias_to_canonical:
            canonical = alias_to_canonical[key]
            return canonical, tier_by_canonical.get(canonical.lower(), "L4")

    return "", "L4"


def infer_group_tier(release_group: str, yaml_path: Optional[str] = None) -> str:
    """
    推断压制组信誉档位。

    @param release_group: 组名
    @param yaml_path: 可选 YAML 路径
    @returns: L0~L4
    """
    _, tier = lookup_group(release_group, yaml_path=yaml_path)
    return tier


def list_groups(yaml_path: Optional[str] = None) -> List[Dict[str, str]]:
    """
    返回全部组条目（调试 / CLI 用）。

    @param yaml_path: 可选 YAML 路径
    @returns: 含 name、tier 的字典列表
    """
    path = Path(yaml_path) if yaml_path else _DEFAULT_YAML
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    rows: List[Dict[str, str]] = []
    for row in data.get("groups") or []:
        if isinstance(row, dict) and row.get("name"):
            rows.append(
                {
                    "name": str(row["name"]),
                    "tier": str(row.get("tier") or "L4"),
                }
            )
    return rows
