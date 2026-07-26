# -*- coding: utf-8 -*-
"""
Ops 长驻进程内重载「静态页生成」相关模块。

@module workflow.ops.generate_reload
@description
  ``ops serve`` 常驻后，磁盘上的 schema/模板逻辑变更不会自动进进程。
  Generate all / Deploy prepare 前调用本模块，避免 bake 出旧 HTML
  （例如缺 ``magnets_updated_*`` / ``rm-badge--updated``）。
"""

from __future__ import annotations

import importlib
import sys
from typing import Any, Dict, List


# 自底向上：先数据模型，再 store / 渲染 / 生成入口
_RELOAD_ORDER: List[str] = [
    "schema.d1_models",
    "portal.generator.i18n",
    "portal.generator.ig_debug",
    "portal.generator.sitemap",
    "portal.generator.static_shell",
    "portal.generator.render_trust",
    "portal.generator.render",
    "workflow.storage.mysql_store",
    "portal.generator.generate_one",
]

# 缺一则视为热重载失败（Context / bake 入口）
_CRITICAL: frozenset = frozenset(
    {
        "schema.d1_models",
        "portal.generator.render",
        "workflow.storage.mysql_store",
        "portal.generator.generate_one",
    }
)


def reload_generate_modules() -> Dict[str, Any]:
    """
    强制 importlib.reload 生成链路模块。

    @returns: { ok, reloaded[], skipped[], errors[] }
    @description
      可选模块缺失只记 skipped；关键模块失败则 ok=False。
    """
    reloaded: List[str] = []
    skipped: List[str] = []
    errors: List[str] = []

    for name in _RELOAD_ORDER:
        try:
            if name in sys.modules:
                importlib.reload(sys.modules[name])
                reloaded.append(name)
            else:
                importlib.import_module(name)
                reloaded.append(f"{name}#import")
        except ModuleNotFoundError:
            skipped.append(name)
        except Exception as exc:  # noqa: BLE001 — 单项失败继续，由 critical 集合决定 ok
            errors.append(f"{name}: {exc}")
            skipped.append(name)

    critical_failed = [
        e for e in errors if any(e.startswith(c + ":") for c in _CRITICAL)
    ] + [s for s in skipped if s in _CRITICAL and not any(r == s or r.startswith(s + "#") for r in reloaded)]

    return {
        "ok": len(critical_failed) == 0,
        "reloaded": reloaded,
        "skipped": skipped,
        "errors": errors,
        "critical_failed": critical_failed,
    }
