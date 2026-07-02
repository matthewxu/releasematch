# -*- coding: utf-8 -*-
"""
TMDB Daily Export 下载与 benchmark 测试 slot 选取。

@module workflow.metadata.tmdb_export_slots
@description
  从 files.tmdb.org 拉取 movie_ids / tv_series_ids 日导出（.json.gz），
  按 popularity 筛选非 adult、非 video 条目，生成 speedtest / pipeline 用 slot JSON。

  注：TMDB 官方格式为 gzip 压缩的 NDJSON，非 RAR；本模块按官方 Daily ID Exports 实现。
"""

from __future__ import annotations

import gzip
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from workflow.config import PROJECT_ROOT

TMDB_EXPORT_BASE_URL: str = "https://files.tmdb.org/p/exports"
DEFAULT_EXPORT_DIR: Path = PROJECT_ROOT / "data" / "tmdb_exports"
MOVIE_POPULARITY_MAX: float = 150.0
MOVIE_POPULARITY_MIN: float = 8.0
TV_POPULARITY_MIN: float = 15.0

# 优先选取：torrent 索引友好、有实测价值的锚定作品（TMDB ID）
CURATED_MOVIE_IDS: List[int] = [
    603,      # The Matrix
    155,      # The Dark Knight
    157336,   # Interstellar
    550,      # Fight Club
    680,      # Pulp Fiction
    122,      # The Lord of the Rings: RoTK
    120,      # The Lord of the Rings: FotR
    13,       # Forrest Gump
    238,      # The Godfather
    424,      # Schindler's List
    769,      # GoodFellas
    278,      # The Shawshank Redemption
]

CURATED_TV_IDS: List[int] = [
    1399,     # Game of Thrones
    66732,    # Stranger Things
    82856,    # The Mandalorian
    94997,    # House of the Dragon
    4604,     # Smallville
    1408,     # House
    71912,    # The Witcher
    1418,     # The Big Bang Theory
    1416,     # Grey's Anatomy
    60735,    # The Flash
]


@dataclass
class ExportFileSet:
    """一次 TMDB 日导出文件组。"""

    export_date: date
    movie_gz: Path
    tv_gz: Path


def _export_date_suffix(d: date) -> str:
    """TMDB 文件名日期段 MM_DD_YYYY。"""
    return d.strftime("%m_%d_%Y")


def _export_urls(d: date) -> Tuple[str, str]:
    """构造 movie / tv 导出 URL。"""
    suffix = _export_date_suffix(d)
    return (
        f"{TMDB_EXPORT_BASE_URL}/movie_ids_{suffix}.json.gz",
        f"{TMDB_EXPORT_BASE_URL}/tv_series_ids_{suffix}.json.gz",
    )


def _http_head_exists(url: str, timeout_sec: int = 30) -> bool:
    """HEAD 探测 URL 是否存在。"""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            return resp.status == 200
    except urllib.error.HTTPError:
        return False


def resolve_latest_export_date(
    *,
    start: Optional[date] = None,
    lookback_days: int = 14,
) -> date:
    """从 start 日向前探测最近可用的 TMDB 导出日。"""
    cursor = start or date.today()
    for _ in range(lookback_days + 1):
        movie_url, _ = _export_urls(cursor)
        if _http_head_exists(movie_url):
            return cursor
        cursor -= timedelta(days=1)
    raise RuntimeError(f"近 {lookback_days} 天内未找到 TMDB movie 导出文件")


def download_file(url: str, dest: Path, timeout_sec: int = 600) -> Path:
    """下载单个导出文件到 dest。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "ReleaseMatch/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        dest.write_bytes(resp.read())
    return dest


def download_tmdb_exports(
    export_date: Optional[date] = None,
    *,
    out_dir: Path = DEFAULT_EXPORT_DIR,
    force: bool = False,
) -> ExportFileSet:
    """下载指定日（或最近可用日）的 movie + tv 日导出。"""
    resolved = export_date or resolve_latest_export_date()
    movie_url, tv_url = _export_urls(resolved)
    suffix = _export_date_suffix(resolved)
    movie_gz = out_dir / f"movie_ids_{suffix}.json.gz"
    tv_gz = out_dir / f"tv_series_ids_{suffix}.json.gz"
    if force or not movie_gz.is_file():
        download_file(movie_url, movie_gz)
    if force or not tv_gz.is_file():
        download_file(tv_url, tv_gz)
    return ExportFileSet(export_date=resolved, movie_gz=movie_gz, tv_gz=tv_gz)


def iter_ndjson_gz(path: Path) -> Iterator[Dict[str, Any]]:
    """流式读取 gzip NDJSON 导出。"""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                yield json.loads(text)


def _short_label(title: str, max_len: int = 32) -> str:
    """截断标题用于 slot label。"""
    cleaned = re.sub(r"\s+", " ", (title or "").strip())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1] + "…"


def _load_export_index(path: Path) -> Dict[int, Dict[str, Any]]:
    """
    将导出文件载入 id → row 索引（用于 curated 查找）。

    @param path: .json.gz 路径
    @returns: tmdb_id → 导出行
    """
    index: Dict[int, Dict[str, Any]] = {}
    for row in iter_ndjson_gz(path):
        index[int(row["id"])] = row
    return index


def select_curated_movie_slots(
    movie_index: Dict[int, Dict[str, Any]],
    *,
    curated_ids: List[int],
    count: int,
    exclude_tmdb_ids: Optional[Set[int]] = None,
) -> List[Dict[str, Any]]:
    """
    从 curated ID 列表优先选取电影 slot。

    @param movie_index: movie 导出索引
    @param curated_ids: 优先 TMDB ID 列表
    @param count: 目标数量
    @param exclude_tmdb_ids: 排除 ID
    @returns: slot 列表
    """
    excluded = exclude_tmdb_ids or set()
    slots: List[Dict[str, Any]] = []
    for tmdb_id in curated_ids:
        if len(slots) >= count:
            break
        if tmdb_id in excluded:
            continue
        row = movie_index.get(tmdb_id)
        if not row or row.get("adult") or row.get("video"):
            continue
        title = str(row.get("original_title") or row.get("title") or f"movie:{tmdb_id}")
        pop = float(row.get("popularity") or 0.0)
        slots.append(
            {
                "label": _short_label(title),
                "tmdb_id": tmdb_id,
                "media_type": "movie",
                "popularity": round(pop, 4),
                "title": title,
                "curated": True,
            }
        )
    return slots


def select_curated_tv_slots(
    tv_index: Dict[int, Dict[str, Any]],
    *,
    curated_ids: List[int],
    count: int,
    season: int = 1,
    episode: int = 1,
    exclude_tmdb_ids: Optional[Set[int]] = None,
) -> List[Dict[str, Any]]:
    """
    从 curated ID 列表优先选取 TV slot（默认 S01E01）。

    @param tv_index: tv 导出索引
    @param curated_ids: 优先 TMDB ID 列表
    @param count: 目标数量
    @param season: 季
    @param episode: 集
    @param exclude_tmdb_ids: 排除的 series ID
    @returns: slot 列表
    """
    excluded = exclude_tmdb_ids or set()
    slots: List[Dict[str, Any]] = []
    for tmdb_id in curated_ids:
        if len(slots) >= count:
            break
        if tmdb_id in excluded:
            continue
        row = tv_index.get(tmdb_id)
        if not row or row.get("adult"):
            continue
        title = str(row.get("original_name") or row.get("name") or f"tv:{tmdb_id}")
        pop = float(row.get("popularity") or 0.0)
        slots.append(
            {
                "label": f"{_short_label(title, 24)} S{season:02d}E{episode:02d}",
                "tmdb_id": tmdb_id,
                "media_type": "tv",
                "season": season,
                "episode": episode,
                "popularity": round(pop, 4),
                "title": title,
                "curated": True,
            }
        )
    return slots


def select_movie_slots(
    movie_gz: Path,
    *,
    count: int,
    exclude_tmdb_ids: Optional[Set[int]] = None,
    pop_min: float = MOVIE_POPULARITY_MIN,
    pop_max: float = MOVIE_POPULARITY_MAX,
) -> List[Dict[str, Any]]:
    """从 movie 导出中按 popularity 选取电影 slot。"""
    excluded = exclude_tmdb_ids or set()
    candidates: List[Tuple[float, Dict[str, Any]]] = []
    for row in iter_ndjson_gz(movie_gz):
        if row.get("adult") or row.get("video"):
            continue
        tmdb_id = int(row["id"])
        if tmdb_id in excluded:
            continue
        pop = float(row.get("popularity") or 0.0)
        if pop < pop_min or pop > pop_max:
            continue
        title = str(row.get("original_title") or row.get("title") or f"movie:{tmdb_id}")
        candidates.append(
            (
                pop,
                {
                    "label": _short_label(title),
                    "tmdb_id": tmdb_id,
                    "media_type": "movie",
                    "popularity": round(pop, 4),
                    "title": title,
                },
            )
        )
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in candidates[:count]]


def select_tv_slots(
    tv_gz: Path,
    *,
    count: int,
    season: int = 1,
    episode: int = 1,
    exclude_tmdb_ids: Optional[Set[int]] = None,
    pop_min: float = TV_POPULARITY_MIN,
) -> List[Dict[str, Any]]:
    """从 tv 导出中按 popularity 选取剧集 slot（默认 S01E01）。"""
    excluded = exclude_tmdb_ids or set()
    candidates: List[Tuple[float, Dict[str, Any]]] = []
    for row in iter_ndjson_gz(tv_gz):
        if row.get("adult"):
            continue
        tmdb_id = int(row["id"])
        if tmdb_id in excluded:
            continue
        pop = float(row.get("popularity") or 0.0)
        if pop < pop_min:
            continue
        title = str(row.get("original_name") or row.get("name") or f"tv:{tmdb_id}")
        candidates.append(
            (
                pop,
                {
                    "label": f"{_short_label(title, 24)} S{season:02d}E{episode:02d}",
                    "tmdb_id": tmdb_id,
                    "media_type": "tv",
                    "season": season,
                    "episode": episode,
                    "popularity": round(pop, 4),
                    "title": title,
                },
            )
        )
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in candidates[:count]]


ANCHOR_SLOTS: List[Dict[str, Any]] = [
    {"label": "BB S04E01", "tmdb_id": 1396, "media_type": "tv", "season": 4, "episode": 1},
    {"label": "BB S04E02", "tmdb_id": 1396, "media_type": "tv", "season": 4, "episode": 2},
    {"label": "BB S04E04", "tmdb_id": 1396, "media_type": "tv", "season": 4, "episode": 4},
    {"label": "BB S04E06", "tmdb_id": 1396, "media_type": "tv", "season": 4, "episode": 6},
    {"label": "BB S04E07", "tmdb_id": 1396, "media_type": "tv", "season": 4, "episode": 7},
    {"label": "BB S04E08", "tmdb_id": 1396, "media_type": "tv", "season": 4, "episode": 8},
    {"label": "Inception", "tmdb_id": 27205, "media_type": "movie"},
]


def build_benchmark_slot_list(
    files: ExportFileSet,
    *,
    total: int = 20,
    movie_count: Optional[int] = None,
    tv_count: Optional[int] = None,
    anchors: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """合并锚点 + TMDB 导出选取，生成 C1 / speedtest 用 slot 清单。"""
    anchor_list = list(anchors or ANCHOR_SLOTS)
    used_ids: Set[int] = {int(s["tmdb_id"]) for s in anchor_list}
    used_tv_series: Set[int] = {
        int(s["tmdb_id"]) for s in anchor_list if s.get("media_type") == "tv"
    }
    remaining = max(0, total - len(anchor_list))
    if movie_count is None and tv_count is None:
        movie_count = remaining // 2 + remaining % 2
        tv_count = remaining // 2
    elif movie_count is None:
        movie_count = max(0, remaining - int(tv_count or 0))
    elif tv_count is None:
        tv_count = max(0, remaining - int(movie_count or 0))

    new_movies = select_curated_movie_slots(
        _load_export_index(files.movie_gz),
        curated_ids=CURATED_MOVIE_IDS,
        count=movie_count,
        exclude_tmdb_ids=used_ids,
    )
    if len(new_movies) < movie_count:
        need = movie_count - len(new_movies)
        for slot in new_movies:
            used_ids.add(int(slot["tmdb_id"]))
        new_movies.extend(
            select_movie_slots(
                files.movie_gz,
                count=need,
                exclude_tmdb_ids=used_ids,
            )
        )
    for slot in new_movies:
        used_ids.add(int(slot["tmdb_id"]))

    new_tv = select_curated_tv_slots(
        _load_export_index(files.tv_gz),
        curated_ids=CURATED_TV_IDS,
        count=tv_count,
        exclude_tmdb_ids=used_tv_series,
    )
    if len(new_tv) < tv_count:
        need = tv_count - len(new_tv)
        for slot in new_tv:
            used_tv_series.add(int(slot["tmdb_id"]))
        new_tv.extend(
            select_tv_slots(
                files.tv_gz,
                count=need,
                exclude_tmdb_ids=used_tv_series,
            )
        )

    slots: List[Dict[str, Any]] = []
    for row in anchor_list + new_movies + new_tv:
        slim: Dict[str, Any] = {
            "label": row["label"],
            "tmdb_id": row["tmdb_id"],
            "media_type": row["media_type"],
        }
        if row.get("media_type") == "tv":
            slim["season"] = int(row["season"])
            slim["episode"] = int(row["episode"])
        if "popularity" in row:
            slim["popularity"] = row["popularity"]
        if "title" in row:
            slim["title"] = row["title"]
        slots.append(slim)

    return {
        "meta": {
            "export_date": files.export_date.isoformat(),
            "movie_export": str(files.movie_gz.name),
            "tv_export": str(files.tv_gz.name),
            "source": TMDB_EXPORT_BASE_URL,
            "format": "json.gz (TMDB Daily ID Exports NDJSON)",
            "anchor_count": len(anchor_list),
            "new_movie_count": len(new_movies),
            "new_tv_count": len(new_tv),
            "total_slots": len(slots),
            "movie_popularity_range": [MOVIE_POPULARITY_MIN, MOVIE_POPULARITY_MAX],
            "tv_popularity_min": TV_POPULARITY_MIN,
            "tv_episode_note": "新 TV slot 默认 S01E01，扩槽后需 pipeline 拉 magnet",
        },
        "slots": slots,
    }


def write_slots_json(report: Dict[str, Any], path: Path) -> Path:
    """写入 slot JSON（仅 slots 数组，兼容 batch --slots-json）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report["slots"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def write_report_json(report: Dict[str, Any], path: Path) -> Path:
    """写入完整报告（含 meta + slots）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
