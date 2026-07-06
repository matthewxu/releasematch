# -*- coding: utf-8 -*-
"""
从 libtorrent metadata 提取 torrent 结构信息（等价于 .torrent info 字典）。

@module workflow.torrent_sources.speedtest.torrent_metadata
@description
  Phase 2 测速 session 在 ``has_metadata`` 后读取 file list / total size，
  与 indexer ``size_bytes`` 交叉验证，供页面 bake 展示。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# 判定主视频文件的扩展名
_VIDEO_EXTENSIONS = frozenset(
    {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".ts", ".m2ts", ".mov", ".webm"}
)

# 写入 DB 的 files_json 最多条数
_MAX_FILES_STORED = 24

# 与 indexer size 视为一致：±1% 或 ±1 MiB（取较大）
_SIZE_MATCH_RATIO = 0.01
_SIZE_MATCH_MIN_BYTES = 1_048_576


@dataclass
class TorrentMetadataResult:
    """
    libtorrent 提取的 torrent 结构元数据。

    @var infohash: 40 位小写 infohash
    @var status: ok | no_metadata | error | dry_run
    @var torrent_name: torrent 根名 / 单文件名
    @var total_size_bytes: 全部文件总字节
    @var file_count: 文件数
    @var piece_length: piece 大小（字节）
    @var is_private: 是否 private torrent
    @var primary_file: 主视频文件路径（启发式）
    @var primary_file_size_bytes: 主文件大小
    @var files: 文件列表 [{path, size_bytes}]
    @var indexer_size_bytes: 拉取时 indexer 报告的大小
    @var size_match: ok | mismatch | unknown — 与 indexer 对比
    @var size_delta_bytes: total - indexer（可正可负）
    @var error: 失败原因
    @var page_id: 关联页面
    """

    infohash: str
    status: str = "ok"
    torrent_name: str = ""
    total_size_bytes: int = 0
    file_count: int = 0
    piece_length: int = 0
    is_private: bool = False
    primary_file: str = ""
    primary_file_size_bytes: int = 0
    files: List[Dict[str, Any]] = field(default_factory=list)
    indexer_size_bytes: int = 0
    size_match: str = "unknown"
    size_delta_bytes: int = 0
    error: Optional[str] = None
    page_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转为 JSON / MySQL 可序列化字典。"""
        return asdict(self)

    def files_json(self) -> str:
        """
        压缩文件列表为 JSON 字符串（入库用）。

        @returns: JSON 数组字符串
        """
        return json.dumps(self.files[:_MAX_FILES_STORED], ensure_ascii=False)


def compare_torrent_sizes(
    torrent_total: int,
    indexer_size: int,
) -> Tuple[str, int]:
    """
    对比 swarm metadata 总大小与 indexer 报告大小。

    @param torrent_total: libtorrent total_size
    @param indexer_size: download_resources.size_bytes
    @returns: (size_match, size_delta_bytes)
    """
    if torrent_total <= 0 or indexer_size <= 0:
        return "unknown", 0
    delta = torrent_total - indexer_size
    tolerance = max(_SIZE_MATCH_MIN_BYTES, int(indexer_size * _SIZE_MATCH_RATIO))
    if abs(delta) <= tolerance:
        return "ok", delta
    return "mismatch", delta


def pick_primary_video_file(
    files: List[Tuple[str, int]],
) -> Tuple[str, int]:
    """
    从文件列表中选取主视频文件（最大体积的视频扩展名文件）。

    @param files: (path, size_bytes) 列表
    @returns: (path, size) 或 ("", 0)
    """
    if not files:
        return "", 0
    video_candidates = [
        (path, size)
        for path, size in files
        if os.path.splitext(path.lower())[1] in _VIDEO_EXTENSIONS
    ]
    pool = video_candidates if video_candidates else files
    best = max(pool, key=lambda item: item[1])
    return best[0], int(best[1])


def _iter_torrent_files(torrent_info: Any) -> List[Tuple[str, int]]:
    """
    兼容 libtorrent 1.x / 2.x 的文件枚举 API。

    @param torrent_info: handle.torrent_file() 返回值
    @returns: (path, size_bytes) 列表
    """
    out: List[Tuple[str, int]] = []
    try:
        fs = torrent_info.files()
        if hasattr(fs, "num_files"):
            for i in range(int(fs.num_files())):
                out.append((str(fs.file_path(i)), int(fs.file_size(i))))
            if out:
                return out
    except (AttributeError, TypeError, ValueError):
        pass

    try:
        count = int(torrent_info.num_files())
        for i in range(count):
            entry = torrent_info.file_at(i)
            path = getattr(entry, "path", None) or str(entry)
            size = int(getattr(entry, "size", 0))
            out.append((str(path), size))
    except (AttributeError, TypeError, ValueError):
        pass

    return out


def extract_from_handle(
    handle: Any,
    infohash: str,
    *,
    page_id: Optional[str] = None,
    indexer_size_bytes: int = 0,
) -> TorrentMetadataResult:
    """
    从 libtorrent torrent_handle 读取 metadata（须在 remove_torrent 之前调用）。

    @param handle: libtorrent torrent_handle
    @param infohash: 40 位 infohash
    @param page_id: 可选页面 ID
    @param indexer_size_bytes: indexer 体积，用于 size_match
    @returns: TorrentMetadataResult
    """
    infohash_norm = (infohash or "").lower().strip()
    try:
        status = handle.status()
        if not getattr(status, "has_metadata", False):
            return TorrentMetadataResult(
                infohash=infohash_norm,
                status="no_metadata",
                page_id=page_id,
                indexer_size_bytes=indexer_size_bytes,
            )

        ti = handle.torrent_file()
        raw_files = _iter_torrent_files(ti)
        file_dicts = [{"path": p, "size_bytes": s} for p, s in raw_files]
        total = 0
        try:
            total = int(ti.total_size())
        except (AttributeError, TypeError, ValueError):
            total = sum(s for _, s in raw_files)

        piece_len = 0
        try:
            piece_len = int(ti.piece_length())
        except (AttributeError, TypeError, ValueError):
            pass

        is_private = False
        try:
            is_private = bool(ti.priv())
        except (AttributeError, TypeError, ValueError):
            pass

        name = ""
        try:
            name = str(ti.name() or "")
        except (AttributeError, TypeError, ValueError):
            pass

        primary_path, primary_size = pick_primary_video_file(raw_files)
        size_match, size_delta = compare_torrent_sizes(total, indexer_size_bytes)

        return TorrentMetadataResult(
            infohash=infohash_norm,
            status="ok",
            torrent_name=name[:1024],
            total_size_bytes=total,
            file_count=len(raw_files),
            piece_length=piece_len,
            is_private=is_private,
            primary_file=primary_path[:1024],
            primary_file_size_bytes=primary_size,
            files=file_dicts[:_MAX_FILES_STORED],
            indexer_size_bytes=indexer_size_bytes,
            size_match=size_match,
            size_delta_bytes=size_delta,
            page_id=page_id,
        )
    except Exception as exc:  # noqa: BLE001 — 测速主流程不应因 metadata 失败
        return TorrentMetadataResult(
            infohash=infohash_norm,
            status="error",
            page_id=page_id,
            indexer_size_bytes=indexer_size_bytes,
            error=str(exc)[:512],
        )


def is_metadata_publishable(meta: Optional[TorrentMetadataResult]) -> bool:
    """
    是否应 bake 进静态页。

    @param meta: 提取结果
    @returns: True 表示可展示
    """
    if meta is None:
        return False
    return meta.status == "ok" and meta.total_size_bytes > 0 and meta.file_count > 0
