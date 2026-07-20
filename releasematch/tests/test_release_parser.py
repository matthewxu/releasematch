#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
release_parser 回归测试 — 防止清单列（Source/Video/Audio/Group）误解析。

@module tests.test_release_parser
@description 覆盖 Group 误切、CAM/TS、YTS WEB、Audio 不混 Source 等。
"""

from __future__ import annotations

import unittest

from workflow.torrent_sources.release_parser import (
    build_display_specs,
    classify_edition,
    enrich_item_dict,
    parse_release_title,
)


class ReleaseParserDisplaySafetyTests(unittest.TestCase):
    """表格列展示正确性回归。"""

    def test_web_dl_does_not_become_group_dl(self) -> None:
        """WEB-DL 连字符不得切出 Group=DL。"""
        p = parse_release_title("Documentary 2020 1080p WEB-DL AAC2.0 x264")
        self.assertEqual(p["source"], "WEB-DL")
        self.assertEqual(p["release_group"], "")
        self.assertIn("AAC", build_display_specs(p, "Documentary 2020 1080p WEB-DL AAC2.0 x264")[1])

    def test_dts_hd_does_not_become_group_hd(self) -> None:
        """DTS-HD 不得切出 Group=HD。"""
        title = "Avatar 2009 1080p BluRay REMUX DTS-HD MA TrueHD Atmos 7.1"
        p = parse_release_title(title)
        self.assertEqual(p["source"], "REMUX")
        self.assertNotEqual(p["release_group"].upper(), "HD")
        self.assertTrue(p["release_group"] == "" or len(p["release_group"]) > 2)

    def test_platform_suffix_not_group(self) -> None:
        """-NF 是平台，不是 Release Group。"""
        title = "Inception.2010.2160p.WEBRip.x265.10bit.DDP5.1-NF"
        p = parse_release_title(title)
        self.assertEqual(p["source"], "WEBRip")
        self.assertEqual(p["platform"], "NF")
        self.assertNotEqual(p["release_group"].upper(), "NF")
        video, audio = build_display_specs(p, title)
        self.assertIn("HEVC", video)
        self.assertIn("Netflix", audio)
        self.assertIn("DDP5.1", audio)
        self.assertNotIn("WEBRip", audio)

    def test_scene_group_still_extracted(self) -> None:
        """正常 -NTb 组名仍可提取。"""
        title = "Breaking.Bad.S04E06.1080p.WEB-DL.DDP5.1.H.264-NTb"
        p = parse_release_title(title)
        self.assertEqual(p["source"], "WEB-DL")
        self.assertEqual(p["release_group"], "NTb")
        self.assertEqual(p["codec"], "H.264")

    def test_audio_never_copies_source_web(self) -> None:
        """Audio 不得写入 WEB / WEB-DL。"""
        title = "Enola Holmes 3.1080p.web-YTS"
        p = parse_release_title(title)
        self.assertEqual(p["source"], "WEB")
        _video, audio = build_display_specs(p, title)
        self.assertEqual(audio, "")

    def test_yts_enrich_normalizes_honestly(self) -> None:
        """YTS 预填/库内 WEB 展示为 WEBRip；Audio 为空；不升格 WEB-DL。"""
        item = enrich_item_dict(
            {
                "title_raw": "Enola Holmes 3.1080p.web-YTS",
                "source": "WEB",
                "resolution": "1080p",
                "release_group": "YTS",
                "audio_spec": "WEB",
            },
            force_specs=True,
        )
        self.assertEqual(item["source"], "WEBRip")
        self.assertEqual(item["audio_spec"], "")
        self.assertEqual(item["video_spec"], "")
        self.assertEqual(item["release_group"], "YTS")
        self.assertEqual(classify_edition(str(item["title_raw"]), str(item["source"])), "web-dl")

    def test_yts_web_dl_overclaim_demoted(self) -> None:
        """历史错误把 YTS 标成 WEB-DL 时，渲染降为 WEBRip。"""
        item = enrich_item_dict(
            {
                "title_raw": "Dune.2024.1080p.web-YTS",
                "source": "WEB-DL",
                "release_group": "YTS",
            },
            force_specs=True,
        )
        self.assertEqual(item["source"], "WEBRip")

    def test_junk_group_cleared(self) -> None:
        """DB 中误存的 Group=DL 应被清空。"""
        item = enrich_item_dict(
            {
                "title_raw": "Film 2020 1080p WEB-DL AAC x264",
                "source": "WEB",
                "release_group": "DL",
            },
            force_specs=True,
        )
        self.assertEqual(item["release_group"], "")
        self.assertEqual(item["source"], "WEB-DL")

    def test_cam_source_matches_edition(self) -> None:
        """CAM 行 Source 与 edition 一致，不为空。"""
        title = "Something.1080p.CAM.x264-EVO"
        p = parse_release_title(title)
        self.assertEqual(p["source"], "CAM")
        self.assertEqual(p["release_group"], "EVO")
        self.assertEqual(classify_edition(title, p["source"]), "cam")

    def test_ts_eliot_not_cam(self) -> None:
        """片名含 TS 单词不得误判 CAM。"""
        title = "TS Eliot Documentary 1080p BluRay-GROUP"
        p = parse_release_title(title)
        self.assertEqual(p["source"], "BluRay")
        self.assertNotEqual(classify_edition(title, p["source"]), "cam")

    def test_ts_with_quality_is_cam(self) -> None:
        """邻近画质的 TS 仍识别为盗录。"""
        title = "Pirates 2003 720p TS x264-EVO"
        p = parse_release_title(title)
        self.assertEqual(p["source"], "TS")
        self.assertEqual(classify_edition(title, p["source"]), "cam")

    def test_remux_source_priority(self) -> None:
        """含 REMUX 时 Source 显示 REMUX 而非 BluRay。"""
        title = "Movie.2020.1080p.BluRay.REMUX.VC-1.DTS-HD.MA.5.1-GROUP"
        p = parse_release_title(title)
        self.assertEqual(p["source"], "REMUX")
        self.assertEqual(classify_edition(title, p["source"]), "remux")


if __name__ == "__main__":
    unittest.main()
