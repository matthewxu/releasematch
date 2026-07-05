#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压制组信誉库加载器。

@module workflow.recommended.groups_registry
@description 从 data/groups.yaml 加载 L0~L4 档位与 scene_compliant，供 scorer 查询组名与别名。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

# yaml 元数据索引：canonical_lower -> {scene_compliant, notes}
_MetaByCanonical = Dict[str, Dict[str, Any]]


@dataclass(frozen=True)
class GroupLookup:
    """
    压制组 yaml 查询结果。

    @var canonical: 规范组名；未命中为空串
    @var tier: L0~L4
    @var scene_compliant: Scene 合规标记；未入库为 None
    @var notes: yaml 备注
    """

    canonical: str
    tier: str
    scene_compliant: Optional[bool] = None
    notes: str = ""


@lru_cache(maxsize=4)
def _load_index(
    yaml_path: str,
) -> Tuple[Dict[str, str], Dict[str, str], _MetaByCanonical]:
    """
    加载 groups.yaml 并构建查找索引。

    @param yaml_path: YAML 文件绝对路径字符串
    @returns: (canonical_lower -> tier, alias_lower -> canonical_name, canonical_lower -> meta)
    """
    path = Path(yaml_path)
    if not path.is_file():
        return {}, {}, {}

    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    tier_by_canonical: Dict[str, str] = {}
    alias_to_canonical: Dict[str, str] = {}
    meta_by_canonical: _MetaByCanonical = {}

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
        meta_by_canonical[canonical_key] = {
            "scene_compliant": bool(row.get("scene_compliant", False)),
            "notes": str(row.get("notes") or ""),
        }

        for alias in row.get("aliases") or []:
            alias_str = str(alias).strip()
            if alias_str:
                alias_to_canonical[alias_str.lower()] = name

    return tier_by_canonical, alias_to_canonical, meta_by_canonical


def clear_groups_cache() -> None:
    """清除 yaml 索引 LRU 缓存（单测或热更新 yaml 后调用）。"""
    _load_index.cache_clear()


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


def _resolve_canonical(
    release_group: str,
    tier_by_canonical: Dict[str, str],
    alias_to_canonical: Dict[str, str],
    meta_by_canonical: _MetaByCanonical,
) -> GroupLookup:
    """
    在已加载索引上解析 release_group。

    @param release_group: ResourceItem.release_group
    @param tier_by_canonical: canonical -> tier
    @param alias_to_canonical: alias -> canonical
    @param meta_by_canonical: canonical -> meta
    @returns: GroupLookup；未命中 tier=L4、scene_compliant=None
    """
    if not tier_by_canonical:
        return GroupLookup("", "L4", None, "")

    def _pack(canonical: str) -> GroupLookup:
        key = canonical.lower()
        meta = meta_by_canonical.get(key, {})
        return GroupLookup(
            canonical=canonical,
            tier=tier_by_canonical.get(key, "L4"),
            scene_compliant=bool(meta.get("scene_compliant", False)),
            notes=str(meta.get("notes") or ""),
        )

    whole = release_group.strip().lower()
    if whole in alias_to_canonical:
        return _pack(alias_to_canonical[whole])

    tokens = _tokenize_group(release_group)
    tokens_sorted = sorted(tokens, key=len, reverse=True)
    for token in tokens_sorted:
        key = token.lower()
        if key in alias_to_canonical:
            return _pack(alias_to_canonical[key])

    return GroupLookup("", "L4", None, "")


def lookup_group_detail(
    release_group: str,
    yaml_path: Optional[str] = None,
) -> GroupLookup:
    """
    查询压制组 canonical、tier 与 scene_compliant（X-07 / X-08）。

    @param release_group: ResourceItem.release_group
    @param yaml_path: 可选自定义 groups.yaml 路径
    @returns: GroupLookup；未知组 canonical 为空、tier L4、scene_compliant None
    """
    if not release_group or not release_group.strip():
        return GroupLookup("", "L4", None, "")

    path = str(Path(yaml_path) if yaml_path else _DEFAULT_YAML)
    tier_by_canonical, alias_to_canonical, meta_by_canonical = _load_index(path)
    result = _resolve_canonical(
        release_group,
        tier_by_canonical,
        alias_to_canonical,
        meta_by_canonical,
    )
    if result.canonical:
        return result
    return GroupLookup("", "L4", None, "")


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
    detail = lookup_group_detail(release_group, yaml_path=yaml_path)
    return detail.canonical, detail.tier


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
    @returns: 含 name、tier、scene_compliant 的字典列表
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
                    "scene_compliant": str(bool(row.get("scene_compliant", False))),
                }
            )
    return rows
