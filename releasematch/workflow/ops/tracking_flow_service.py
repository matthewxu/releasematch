# -*- coding: utf-8 -*-
"""
Ops 跟踪 JS「保存并同步到 dist」后台任务与分步进度。

@module workflow.ops.tracking_flow_service
@description
  将编辑器内容写入 ``portal/static/js/tracking.js``、同步到 dist，
  并扫描 dist HTML 是否已引用 tracking.js，供 UI 分步进度条展示。
"""

from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from portal.generator.tracking import (
    TRACKING_JS_HREF,
    sync_tracking_js_to_dist,
    tracking_js_static_path,
    write_tracking_js,
)
from workflow.config import PROJECT_ROOT

# portal / dist 根
_PORTAL_ROOT: Path = PROJECT_ROOT / "portal"
_DIST_ROOT: Path = _PORTAL_ROOT / "dist"

# 进度：idle | running | done | error
_PROGRESS: Dict[str, Any] = {
    "status": "idle",
    "phase": "",
    "percent": 0,
    "message": "",
    "current_step_id": None,
    "steps": [],
    "summary": None,
    "error": None,
    "started_at": None,
    "finished_at": None,
    "ok": None,
    "mode": "",
}
_PROGRESS_LOCK = threading.Lock()
_WORKER: Optional[threading.Thread] = None


def _set_progress(**kwargs: Any) -> None:
    """
    合并更新进度字典。

    @param kwargs: 要覆盖的字段
    """
    with _PROGRESS_LOCK:
        _PROGRESS.update(kwargs)


def get_progress() -> Dict[str, Any]:
    """
    返回跟踪 JS 保存/同步进度快照。

    @returns: status / steps / percent / summary / …
    """
    with _PROGRESS_LOCK:
        return dict(_PROGRESS)


def _init_steps(mode: str) -> List[Dict[str, Any]]:
    """
    按模式初始化分步列表。

    @param mode: save_sync | sync_only
    @returns: steps 列表（status=pending）
    """
    # 完整注释：每步含 id/title/status/detail，供 opsProgressDetail 渲染
    if mode == "sync_only":
        defs = [
            ("ensure", "确认真相源存在"),
            ("sync_dist", "复制到 dist/static/js/tracking.js"),
            ("verify", "校验 static ↔ dist 一致"),
            ("scan_html", "扫描 dist HTML 引用情况"),
            ("done", "汇总"),
        ]
    else:
        defs = [
            ("validate", "校验编辑器内容"),
            ("write_static", "写入 portal/static/js/tracking.js"),
            ("sync_dist", "同步到 dist/static/js/tracking.js"),
            ("verify", "校验 static ↔ dist 一致"),
            ("scan_html", "扫描 dist HTML 引用情况"),
            ("done", "汇总"),
        ]
    return [
        {"step_id": sid, "title": title, "status": "pending", "detail": ""}
        for sid, title in defs
    ]


def _update_step(
    steps: List[Dict[str, Any]],
    step_id: str,
    *,
    status: str,
    detail: str = "",
) -> List[Dict[str, Any]]:
    """
    更新某一步的状态与说明。

    @param steps: 步骤列表
    @param step_id: 步骤 id
    @param status: pending | running | ok | failed | skipped | warn
    @param detail: 人类可读说明
    @returns: 新 steps 副本
    """
    out: List[Dict[str, Any]] = []
    for step in steps:
        item = dict(step)
        if item.get("step_id") == step_id:
            item["status"] = status
            item["detail"] = detail
        out.append(item)
    return out


def _step_percent(steps: List[Dict[str, Any]], current_index: int) -> int:
    """
    按当前步骤序号估算百分比。

    @param steps: 步骤列表
    @param current_index: 0-based 正在执行的步骤下标
    @returns: 1–99
    """
    total = max(1, len(steps))
    return int(min(99, max(1, round((current_index / total) * 100))))


def _analyze_content(content: str) -> Dict[str, Any]:
    """
    粗判跟踪脚本特征（供进度明细解读）。

    @param content: JS 全文
    @returns: 特征摘要
    """
    text = content or ""
    lines = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
    bytes_n = len(text.encode("utf-8"))
    has_ga4 = "googletagmanager.com" in text or "gtag(" in text or "gtag '" in text
    # 完整注释：以 Clarity 官方 tag URL 判定，避免误伤普通注释里的 clarity 一词
    has_clarity = "clarity.ms/tag/" in text
    has_measurement = "G-" in text
    is_stub = "tracking disabled" in text or (
        "在此填写跟踪代码" in text and "gtag" not in text and "clarity.ms" not in text
    )
    return {
        "bytes": bytes_n,
        "lines": lines,
        "has_ga4": has_ga4,
        "has_clarity": has_clarity,
        "has_measurement_id_like": has_measurement,
        "looks_like_stub": is_stub,
        "empty": not text.strip(),
    }


def _file_sha16(path: Path) -> str:
    """
    计算文件内容 SHA256 前 16 位。

    @param path: 文件路径
    @returns: hex 短摘要；失败返回空串
    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def _scan_dist_html_refs(
    dist_root: Path,
    *,
    href: str = TRACKING_JS_HREF,
    sample_limit: int = 8,
) -> Dict[str, Any]:
    """
    扫描 dist 下 HTML 是否包含 tracking.js 引用。

    @param dist_root: dist 根目录
    @param href: 期望出现的 script 路径片段
    @param sample_limit: 缺失引用样例最多条数
    @returns: 统计与样例
    """
    if not dist_root.is_dir():
        return {
            "ok": False,
            "error": f"dist 不存在: {dist_root}",
            "html_total": 0,
            "html_with_ref": 0,
            "html_missing_ref": 0,
            "missing_samples": [],
            "with_samples": [],
        }

    total = 0
    with_ref = 0
    missing = 0
    missing_samples: List[str] = []
    with_samples: List[str] = []
    marker = href
    for path in dist_root.rglob("*.html"):
        total += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            missing += 1
            if len(missing_samples) < sample_limit:
                missing_samples.append(str(path.relative_to(dist_root)) + " (读失败)")
            continue
        rel = str(path.relative_to(dist_root))
        if marker in text:
            with_ref += 1
            if len(with_samples) < sample_limit:
                with_samples.append(rel)
        else:
            missing += 1
            if len(missing_samples) < sample_limit:
                missing_samples.append(rel)

    return {
        "ok": True,
        "html_total": total,
        "html_with_ref": with_ref,
        "html_missing_ref": missing,
        "missing_samples": missing_samples,
        "with_samples": with_samples,
        "href": href,
        "note": (
            "缺失引用的 HTML 需重新 generate 一次才会挂上 script 标签；"
            "之后只更新 tracking.js 即可。"
            if missing > 0
            else "全部已抽查页均含 tracking.js 引用。"
        ),
    }


def _run_save_sync(content: str) -> None:
    """
    后台：校验 → 写 static → sync dist → 校验 → 扫 HTML。

    @param content: 编辑器 JS 全文
    """
    steps = list(_PROGRESS.get("steps") or _init_steps("save_sync"))
    summary: Dict[str, Any] = {"mode": "save_sync"}

    try:
        # 1) validate
        _set_progress(
            phase="validate",
            current_step_id="validate",
            percent=_step_percent(steps, 0),
            message="校验编辑器内容…",
            steps=_update_step(steps, "validate", status="running", detail="分析中…"),
        )
        analysis = _analyze_content(content)
        summary["content"] = analysis
        if analysis["empty"]:
            detail = "内容为空（将写入空文件，页面仍会加载 tracking.js）"
            status = "warn"
        elif analysis["looks_like_stub"]:
            detail = (
                f"疑似空壳模板 · {analysis['bytes']}B / {analysis['lines']} 行"
                "（未检测到 GA4/gtag）"
            )
            status = "warn"
        else:
            flags = []
            if analysis["has_ga4"]:
                flags.append("含 GA4/gtag")
            if analysis.get("has_clarity"):
                flags.append("含 Clarity")
            if analysis["has_measurement_id_like"]:
                flags.append("含 G-…")
            detail = (
                f"{analysis['bytes']}B / {analysis['lines']} 行"
                + ((" · " + " · ".join(flags)) if flags else "")
            )
            status = "ok"
        steps = _update_step(steps, "validate", status=status, detail=detail)
        _set_progress(steps=steps, percent=_step_percent(steps, 1))

        # 2) write_static
        _set_progress(
            phase="write_static",
            current_step_id="write_static",
            message="写入真相源 tracking.js…",
            steps=_update_step(
                steps, "write_static", status="running", detail="写入中…"
            ),
        )
        written = write_tracking_js(content, sync_dist=False)
        if not written.get("ok"):
            raise RuntimeError(written.get("error") or "写入 static 失败")
        static_path = Path(str(written["path"]))
        summary["static"] = {
            "path": str(static_path),
            "bytes": written.get("bytes"),
            "sha16": _file_sha16(static_path),
        }
        steps = _update_step(
            steps,
            "write_static",
            status="ok",
            detail=f"{static_path} · {written.get('bytes')}B",
        )
        _set_progress(steps=steps, percent=_step_percent(steps, 2))

        # 3) sync_dist
        _set_progress(
            phase="sync_dist",
            current_step_id="sync_dist",
            message="同步到 dist…",
            steps=_update_step(steps, "sync_dist", status="running", detail="复制中…"),
        )
        synced = sync_tracking_js_to_dist()
        if not synced.get("ok"):
            raise RuntimeError(synced.get("error") or "同步 dist 失败")
        dist_path = Path(str(synced["dist_path"]))
        summary["dist"] = {
            "path": str(dist_path),
            "bytes": synced.get("bytes"),
            "sha16": _file_sha16(dist_path),
        }
        steps = _update_step(
            steps,
            "sync_dist",
            status="ok",
            detail=f"{dist_path} · {synced.get('bytes')}B",
        )
        _set_progress(steps=steps, percent=_step_percent(steps, 3))

        # 4) verify
        _set_progress(
            phase="verify",
            current_step_id="verify",
            message="校验 static 与 dist…",
            steps=_update_step(steps, "verify", status="running", detail="比对哈希…"),
        )
        static_sha = summary["static"]["sha16"]
        dist_sha = summary["dist"]["sha16"]
        identical = bool(static_sha) and static_sha == dist_sha
        summary["verify"] = {
            "identical": identical,
            "static_sha16": static_sha,
            "dist_sha16": dist_sha,
        }
        if not identical:
            raise RuntimeError(
                f"static/dist 不一致：{static_sha} ≠ {dist_sha}"
            )
        steps = _update_step(
            steps,
            "verify",
            status="ok",
            detail=f"sha16={static_sha} · 一致",
        )
        _set_progress(steps=steps, percent=_step_percent(steps, 4))

        # 5) scan_html
        _set_progress(
            phase="scan_html",
            current_step_id="scan_html",
            message="扫描 dist HTML 引用…",
            steps=_update_step(
                steps, "scan_html", status="running", detail="遍历 *.html…"
            ),
        )
        scan = _scan_dist_html_refs(_DIST_ROOT)
        summary["html_scan"] = scan
        if not scan.get("ok"):
            steps = _update_step(
                steps,
                "scan_html",
                status="warn",
                detail=str(scan.get("error") or "扫描失败"),
            )
        else:
            miss = int(scan.get("html_missing_ref") or 0)
            with_n = int(scan.get("html_with_ref") or 0)
            total = int(scan.get("html_total") or 0)
            st = "warn" if miss > 0 else "ok"
            detail = f"HTML {with_n}/{total} 已引用 · 缺 {miss}"
            if miss > 0 and scan.get("missing_samples"):
                detail += " · 例: " + ", ".join(scan["missing_samples"][:3])
            steps = _update_step(steps, "scan_html", status=st, detail=detail)
        _set_progress(steps=steps, percent=_step_percent(steps, 5))

        # 6) done
        miss_n = int((summary.get("html_scan") or {}).get("html_missing_ref") or 0)
        msg = (
            f"已保存并同步 · {summary['static']['bytes']}B"
            + (f" · 注意：{miss_n} 个 HTML 尚未引用 tracking.js（需重烘）" if miss_n else "")
        )
        steps = _update_step(steps, "done", status="ok", detail=msg)
        _set_progress(
            status="done",
            phase="done",
            percent=100,
            current_step_id="done",
            message=msg,
            steps=steps,
            summary=summary,
            finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ok=True,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        cur = _PROGRESS.get("current_step_id") or "validate"
        steps = _update_step(steps, str(cur), status="failed", detail=str(exc)[:200])
        _set_progress(
            status="error",
            percent=100,
            message=str(exc)[:200],
            error=str(exc),
            steps=steps,
            summary=summary,
            finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ok=False,
        )


def _run_sync_only() -> None:
    """
    后台：仅 sync → 校验 → 扫 HTML（不改编辑器内容）。
    """
    steps = list(_PROGRESS.get("steps") or _init_steps("sync_only"))
    summary: Dict[str, Any] = {"mode": "sync_only"}

    try:
        _set_progress(
            phase="ensure",
            current_step_id="ensure",
            percent=_step_percent(steps, 0),
            message="确认真相源…",
            steps=_update_step(steps, "ensure", status="running", detail="检查文件…"),
        )
        static_path = tracking_js_static_path()
        if not static_path.is_file():
            raise RuntimeError(f"真相源不存在: {static_path}")
        content = static_path.read_text(encoding="utf-8")
        analysis = _analyze_content(content)
        summary["content"] = analysis
        summary["static"] = {
            "path": str(static_path),
            "bytes": analysis["bytes"],
            "sha16": _file_sha16(static_path),
        }
        steps = _update_step(
            steps,
            "ensure",
            status="warn" if analysis.get("looks_like_stub") else "ok",
            detail=f"{static_path.name} · {analysis['bytes']}B",
        )
        _set_progress(steps=steps, percent=_step_percent(steps, 1))

        _set_progress(
            phase="sync_dist",
            current_step_id="sync_dist",
            message="同步到 dist…",
            steps=_update_step(steps, "sync_dist", status="running", detail="复制中…"),
        )
        synced = sync_tracking_js_to_dist()
        if not synced.get("ok"):
            raise RuntimeError(synced.get("error") or "同步失败")
        dist_path = Path(str(synced["dist_path"]))
        summary["dist"] = {
            "path": str(dist_path),
            "bytes": synced.get("bytes"),
            "sha16": _file_sha16(dist_path),
        }
        steps = _update_step(
            steps,
            "sync_dist",
            status="ok",
            detail=f"{dist_path} · {synced.get('bytes')}B",
        )
        _set_progress(steps=steps, percent=_step_percent(steps, 2))

        _set_progress(
            phase="verify",
            current_step_id="verify",
            message="校验一致性…",
            steps=_update_step(steps, "verify", status="running", detail="比对…"),
        )
        identical = summary["static"]["sha16"] == summary["dist"]["sha16"]
        summary["verify"] = {
            "identical": identical,
            "static_sha16": summary["static"]["sha16"],
            "dist_sha16": summary["dist"]["sha16"],
        }
        if not identical:
            raise RuntimeError("static/dist 哈希不一致")
        steps = _update_step(
            steps,
            "verify",
            status="ok",
            detail=f"sha16={summary['static']['sha16']}",
        )
        _set_progress(steps=steps, percent=_step_percent(steps, 3))

        _set_progress(
            phase="scan_html",
            current_step_id="scan_html",
            message="扫描 dist HTML…",
            steps=_update_step(
                steps, "scan_html", status="running", detail="遍历 *.html…"
            ),
        )
        scan = _scan_dist_html_refs(_DIST_ROOT)
        summary["html_scan"] = scan
        if scan.get("ok"):
            miss = int(scan.get("html_missing_ref") or 0)
            detail = (
                f"HTML {scan.get('html_with_ref')}/{scan.get('html_total')} 已引用"
                f" · 缺 {miss}"
            )
            steps = _update_step(
                steps,
                "scan_html",
                status="warn" if miss else "ok",
                detail=detail,
            )
        else:
            steps = _update_step(
                steps,
                "scan_html",
                status="warn",
                detail=str(scan.get("error") or "扫描失败"),
            )
        _set_progress(steps=steps, percent=_step_percent(steps, 4))

        miss_n = int((summary.get("html_scan") or {}).get("html_missing_ref") or 0)
        msg = "已同步到 dist" + (
            f" · {miss_n} 个 HTML 尚未引用（需重烘）" if miss_n else ""
        )
        steps = _update_step(steps, "done", status="ok", detail=msg)
        _set_progress(
            status="done",
            phase="done",
            percent=100,
            current_step_id="done",
            message=msg,
            steps=steps,
            summary=summary,
            finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ok=True,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        cur = _PROGRESS.get("current_step_id") or "ensure"
        steps = _update_step(steps, str(cur), status="failed", detail=str(exc)[:200])
        _set_progress(
            status="error",
            percent=100,
            message=str(exc)[:200],
            error=str(exc),
            steps=steps,
            summary=summary,
            finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ok=False,
        )


def start_save_sync(content: str) -> Dict[str, Any]:
    """
    启动「保存并同步」后台任务。

    @param content: tracking.js 全文
    @returns: { ok, started, already_running?, progress }
    """
    global _WORKER

    with _PROGRESS_LOCK:
        if _PROGRESS.get("status") == "running" and _WORKER and _WORKER.is_alive():
            return {
                "ok": True,
                "started": False,
                "already_running": True,
                "progress": dict(_PROGRESS),
            }

    steps = _init_steps("save_sync")
    with _PROGRESS_LOCK:
        _PROGRESS.update(
            {
                "status": "running",
                "phase": "validate",
                "percent": 1,
                "message": "准备保存并同步 tracking.js…",
                "current_step_id": "validate",
                "steps": steps,
                "summary": None,
                "error": None,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "finished_at": None,
                "ok": None,
                "mode": "save_sync",
            }
        )

    _WORKER = threading.Thread(
        target=_run_save_sync,
        args=(str(content or ""),),
        name="ops-tracking-save-sync",
        daemon=True,
    )
    _WORKER.start()
    return {"ok": True, "started": True, "progress": get_progress()}


def start_sync_only() -> Dict[str, Any]:
    """
    启动「仅同步到 dist」后台任务。

    @returns: { ok, started, already_running?, progress }
    """
    global _WORKER

    with _PROGRESS_LOCK:
        if _PROGRESS.get("status") == "running" and _WORKER and _WORKER.is_alive():
            return {
                "ok": True,
                "started": False,
                "already_running": True,
                "progress": dict(_PROGRESS),
            }

    steps = _init_steps("sync_only")
    with _PROGRESS_LOCK:
        _PROGRESS.update(
            {
                "status": "running",
                "phase": "ensure",
                "percent": 1,
                "message": "准备同步 tracking.js → dist…",
                "current_step_id": "ensure",
                "steps": steps,
                "summary": None,
                "error": None,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "finished_at": None,
                "ok": None,
                "mode": "sync_only",
            }
        )

    _WORKER = threading.Thread(
        target=_run_sync_only,
        name="ops-tracking-sync-only",
        daemon=True,
    )
    _WORKER.start()
    return {"ok": True, "started": True, "progress": get_progress()}
