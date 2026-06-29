#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批补优先级队列构建（独立版，解耦 W002）。

@module workflow.priority.queue_builder
@description
  原规划复用 tmdbpy/workflow/W002_priority_engine.py 的 media_priority 队列。
  Release 导航站通过本模块独立构建批补队列，可选只读 MySQL popularity 表。

  R0：使用 Demo 清单（Breaking Bad 全季 + 2 电影）
  R1：对接 TMDB popularity 或自有优先级 JSON
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EpisodeSlot:
    """剧集单集槽位。"""

    season: int
    episode: int


@dataclass
class PriorityWorkItem:
    """
    批补队列中的单个作品项。

    @var tmdb_id: TMDB ID
    @var media_type: movie 或 tv
    @var tier: P0 / P1 / P2
    @var imdb_id: IMDb ID
    @var tvdb_id: TVDB ID（剧集）
    @var episodes: 需拉取的集列表（剧集）
    @var title: 展示用标题
    """

    tmdb_id: int
    media_type: str
    tier: str = "P0"
    imdb_id: Optional[str] = None
    tvdb_id: Optional[int] = None
    episodes: List[EpisodeSlot] = field(default_factory=list)
    title: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转为 JSON 可序列化字典。"""
        return {
            "tmdb_id": self.tmdb_id,
            "media_type": self.media_type,
            "tier": self.tier,
            "imdb_id": self.imdb_id,
            "tvdb_id": self.tvdb_id,
            "title": self.title,
            "episodes": [{"season": e.season, "episode": e.episode} for e in self.episodes],
        }


def demo_cold_start_queue() -> List[PriorityWorkItem]:
    """
    R0 冷启动 Demo 队列：Breaking Bad 47 集子集 + 2 电影。

    @returns: PriorityWorkItem 列表
    """
    # Season 4 全 13 集 + Season 1 前 5 集作为 Demo 子集示例
    bb_episodes = [EpisodeSlot(4, ep) for ep in range(1, 14)]
    bb_episodes += [EpisodeSlot(1, ep) for ep in range(1, 6)]

    return [
        PriorityWorkItem(
            tmdb_id=1396,
            media_type="tv",
            tier="P0",
            imdb_id="tt0903747",
            tvdb_id=81189,
            episodes=bb_episodes,
            title="Breaking Bad",
        ),
        PriorityWorkItem(
            tmdb_id=603,
            media_type="movie",
            tier="P0",
            imdb_id="tt0133093",
            title="The Matrix",
        ),
        PriorityWorkItem(
            tmdb_id=27205,
            media_type="movie",
            tier="P0",
            imdb_id="tt1375666",
            title="Inception",
        ),
    ]


def build_queue(source: str = "demo", limit: int = 100) -> List[PriorityWorkItem]:
    """
    构建批补优先级队列。

    @param source: demo | mysql | json（R1 扩展）
    @param limit: 最大作品数
    @returns: 队列列表
    """
    if source == "demo":
        items = demo_cold_start_queue()
        return items[:limit]

    # R1: mysql / json 文件队列
    return demo_cold_start_queue()[:limit]
