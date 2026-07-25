# -*- coding: utf-8 -*-
"""
一键跑生成流程（generation_flow_service）单元测试。

覆盖：无批次、防重复启动、分槽进度字段、逐槽阶段推进。
"""

from __future__ import annotations

import threading
import time
import unittest
from unittest import mock

from workflow.ops import generation_flow_service as gfs


def _fake_batch(page_ids: list[str]) -> dict:
    """构造最小活跃批次。"""
    return {
        "meta": {"batch_id": "test-batch-1"},
        "slots": [
            {
                "page_id": pid,
                "label": pid,
                "selected": True,
                "gate": {
                    "magnet_count": 2,
                    "has_recommended": True,
                    "page_status": "published",
                    "indexable": True,
                },
                "stages": {
                    "pipeline": {"status": "pending"},
                    "generate": {"status": "pending"},
                    "speedtest": {"status": "pending"},
                },
            }
            for pid in page_ids
        ],
    }


class GenerationFlowServiceTests(unittest.TestCase):
    """generation_flow_service 行为测试。"""

    def setUp(self) -> None:
        """每个用例前清空进度状态。"""
        gfs._reset_for_tests()

    def tearDown(self) -> None:
        """等待可能残留的 worker 结束并复位。"""
        worker = gfs._WORKER
        if worker and worker.is_alive():
            worker.join(timeout=5)
        gfs._reset_for_tests()

    def test_start_without_batch(self) -> None:
        """无活跃批次时应失败。"""
        with mock.patch.object(gfs, "load_active_batch", return_value=None):
            result = gfs.start_generation_flow(skip_existing=True)
        self.assertFalse(result.get("ok"))
        self.assertIn("批次", result.get("error") or "")

    def test_double_start_returns_already_running(self) -> None:
        """第二次 start 应返回 already_running，不启第二个 worker。"""
        batch = _fake_batch(["movie:1", "movie:2"])
        calls = {"pipeline": 0, "generate": 0, "speedtest": 0}

        def slow_pipeline(**_kwargs):
            calls["pipeline"] += 1
            time.sleep(0.35)
            return {"ok": True, "batch": batch, "summary": {}}

        def ok_generate(**_kwargs):
            calls["generate"] += 1
            return {"ok": True, "batch": batch, "summary": {}}

        def ok_speed(**_kwargs):
            calls["speedtest"] += 1
            return {"ok": True, "batch": batch, "summary": {}}

        with mock.patch.object(gfs, "load_active_batch", return_value=batch), mock.patch.object(
            gfs.actions, "run_pipeline", side_effect=slow_pipeline
        ), mock.patch.object(
            gfs.actions, "run_generate", side_effect=ok_generate
        ), mock.patch.object(
            gfs.actions, "run_speedtest", side_effect=ok_speed
        ):
            first = gfs.start_generation_flow(skip_existing=True, page_ids=["movie:1", "movie:2"])
            second = gfs.start_generation_flow(skip_existing=True, page_ids=["movie:1", "movie:2"])
            self.assertTrue(first.get("started"))
            self.assertTrue(second.get("already_running"))
            self.assertFalse(second.get("started"))
            # 等到结束
            for _ in range(40):
                if gfs.get_progress().get("status") in ("done", "error"):
                    break
                time.sleep(0.1)
            prog = gfs.get_progress()
            self.assertEqual(prog.get("status"), "done")
            # 每个槽各跑一次 pipeline/generate/speedtest → 2 槽
            self.assertEqual(calls["pipeline"], 2)
            self.assertEqual(calls["generate"], 2)
            self.assertEqual(calls["speedtest"], 2)

    def test_progress_slot_fields_and_running_marker(self) -> None:
        """progress.slots 含 page_id / pipeline / magnet / Rec / status / indexable / generate / speedtest。"""
        batch = _fake_batch(["tv:1:s01e01"])
        release = threading.Event()

        def block_pipeline(**_kwargs):
            # 等到测试读到 running，或超时兜底
            release.wait(timeout=3.0)
            return {"ok": True, "batch": batch, "summary": {}}

        with mock.patch.object(gfs, "load_active_batch", return_value=batch), mock.patch.object(
            gfs.actions, "run_pipeline", side_effect=block_pipeline
        ), mock.patch.object(
            gfs.actions,
            "run_generate",
            return_value={"ok": True, "batch": batch, "summary": {}},
        ), mock.patch.object(
            gfs.actions,
            "run_speedtest",
            return_value={"ok": True, "batch": batch, "summary": {}},
        ):
            gfs.start_generation_flow(page_ids=["tv:1:s01e01"])
            saw_running = False
            for _ in range(80):
                prog = gfs.get_progress()
                slots = prog.get("slots") or []
                if slots and slots[0].get("pipeline") == "running":
                    saw_running = True
                    row = slots[0]
                    for key in (
                        "page_id",
                        "pipeline",
                        "magnet_count",
                        "has_recommended",
                        "page_status",
                        "indexable",
                        "generate",
                        "speedtest",
                    ):
                        self.assertIn(key, row)
                    self.assertEqual(row["page_id"], "tv:1:s01e01")
                    self.assertEqual(prog.get("phase"), "pipeline")
                    self.assertEqual(prog.get("current_page_id"), "tv:1:s01e01")
                    break
                time.sleep(0.05)
            release.set()
            self.assertTrue(saw_running, "应看到 pipeline=running")
            for _ in range(40):
                if gfs.get_progress().get("status") in ("done", "error"):
                    break
                time.sleep(0.1)
            self.assertEqual(gfs.get_progress().get("status"), "done")


if __name__ == "__main__":
    unittest.main()
