# -*- coding: utf-8 -*-
"""
TMDB REST API — external_ids 解析（CORS Proxy + 本地缓存）。

@module workflow.metadata.tmdb_api
@description
  参考 tmdbpy/workflow/W004_metadata_crawler.py 与 crawler_tmdb/api_config.py：
    - 经 Cloudflare CORS Proxy（api.weidaohang.org/cp/?apiurl=...）访问 TMDB v3
    - 补全 imdb_id / tvdb_id / title / year，提升 Jackett/YTS 命中率

  环境变量：
    RM_TMDB_API_KEY / TMDB_API_KEY
    RM_TMDB_CORS_PROXY（默认 https://api.weidaohang.org/cp/）
    RM_TMDB_API_BASE（默认 https://api.themoviedb.org/3）
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from workflow.config import (
    PROJECT_ROOT,
    TMDB_API_BASE,
    TMDB_API_KEY,
    TMDB_API_TIMEOUT,
    TMDB_CORS_PROXY_URL,
)

CACHE_FILE: Path = PROJECT_ROOT / "data" / "tmdb_exports" / "external_ids_cache.json"
_RATE_LIMIT_DELAY_SEC: float = 0.05


def _cache_load() -> Dict[str, Dict[str, Any]]:
    """读取 external_ids 磁盘缓存。"""
    if not CACHE_FILE.is_file():
        return {}
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _cache_save(cache: Dict[str, Dict[str, Any]]) -> None:
    """写入 external_ids 磁盘缓存。"""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _cache_key(tmdb_id: int, media_type: str) -> str:
    """生成缓存键 movie:603 / tv:1399。"""
    return f"{media_type}:{tmdb_id}"


def _parse_year(date_str: Optional[str]) -> Optional[int]:
    """从 release_date / first_air_date 解析年份。"""
    if not date_str or len(date_str) < 4:
        return None
    try:
        return int(date_str[:4])
    except ValueError:
        return None


def _normalize_imdb(raw: Any) -> Optional[str]:
    """规范化 IMDb ID。"""
    if not raw:
        return None
    text = str(raw).strip()
    if text in ("", "None", "null", "0"):
        return None
    if not text.startswith("tt"):
        text = f"tt{text}"
    return text


class TmdbApiClient:
    """
    TMDB v3 客户端 — 经 CORS Proxy 拉取元数据（对齐 W004 TmdbApiClient）。

    @var api_key: TMDB API Key
    @var cors_proxy_url: Cloudflare CORS Proxy 根 URL
    @var target_api_base: TMDB API v3 根 URL
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        cors_proxy_url: Optional[str] = None,
        target_api_base: Optional[str] = None,
        timeout: Optional[Tuple[int, int]] = None,
    ) -> None:
        """初始化客户端。"""
        self.api_key = (api_key or TMDB_API_KEY or "").strip()
        self.cors_proxy_url = (cors_proxy_url or TMDB_CORS_PROXY_URL or "").strip().rstrip("/") + "/"
        self.target_api_base = (target_api_base or TMDB_API_BASE or "").strip().rstrip("/")
        self.timeout = timeout or TMDB_API_TIMEOUT
        self.request_count = 0
        self._last_request_at = 0.0

    def configured(self) -> bool:
        """是否已配置 API Key。"""
        return bool(self.api_key)

    def _rate_limit(self) -> None:
        """限速（约 20 req/s，保守于 TMDB 50 req/s 上限）。"""
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < _RATE_LIMIT_DELAY_SEC:
            time.sleep(_RATE_LIMIT_DELAY_SEC - elapsed)
        self._last_request_at = time.monotonic()

    def _build_target_url(self, path: str, *, append: Optional[str] = None) -> str:
        """
        构造 TMDB 目标 URL（供 CORS Proxy apiurl 参数）。

        @param path: 如 /movie/603 或 /tv/1399
        @param append: append_to_response 值
        @returns: 完整 TMDB URL
        """
        sep = "&" if "?" in path else "?"
        url = f"{self.target_api_base}{path}{sep}api_key={self.api_key}"
        if append:
            url = f"{url}&append_to_response={append}"
        return url

    def _get_json(self, target_url: str, *, retry_429: int = 2) -> Optional[Dict[str, Any]]:
        """
        经 CORS Proxy 或直连 GET JSON。

        @param target_url: TMDB 完整 URL
        @param retry_429: 429 时重试次数
        @returns: 解析后的 dict；失败返回 None
        """
        import requests  # noqa: WPS433 — 与 requirements 一致

        self._rate_limit()
        self.request_count += 1

        if self.cors_proxy_url and self.cors_proxy_url.startswith("http"):
            request_url = self.cors_proxy_url
            params = {"apiurl": target_url}
        else:
            request_url = target_url
            params = None

        try:
            resp = requests.get(request_url, params=params, timeout=self.timeout)
        except requests.RequestException:
            return None

        if resp.status_code == 200:
            try:
                return resp.json()
            except json.JSONDecodeError:
                return None
        if resp.status_code == 404:
            return None
        if resp.status_code == 429 and retry_429 > 0:
            time.sleep(5)
            return self._get_json(target_url, retry_429=retry_429 - 1)
        return None

    def fetch_metadata(self, tmdb_id: int, media_type: str = "movie") -> Optional[Dict[str, Any]]:
        """
        拉取作品元数据 + external_ids（单次 append_to_response=external_ids）。

        @param tmdb_id: TMDB ID
        @param media_type: movie | tv
        @returns: 含 imdb_id、tvdb_id、title、year 等字段
        """
        if not self.configured():
            return None

        path = f"/{'movie' if media_type == 'movie' else 'tv'}/{tmdb_id}"
        target_url = self._build_target_url(path, append="external_ids")
        data = self._get_json(target_url)
        if not data:
            return None

        ext = data.get("external_ids") if isinstance(data.get("external_ids"), dict) else {}
        imdb_id = _normalize_imdb(data.get("imdb_id") or ext.get("imdb_id"))
        tvdb_raw = ext.get("tvdb_id") if media_type == "tv" else data.get("tvdb_id")
        tvdb_id = int(tvdb_raw) if tvdb_raw not in (None, "", 0) else None

        if media_type == "movie":
            title = str(data.get("title") or data.get("original_title") or "")
            year = _parse_year(data.get("release_date"))
        else:
            title = str(data.get("name") or data.get("original_name") or "")
            year = _parse_year(data.get("first_air_date"))

        return {
            "tmdb_id": tmdb_id,
            "media_type": media_type,
            "imdb_id": imdb_id,
            "tvdb_id": tvdb_id,
            "title": title or None,
            "original_language": data.get("original_language"),
            "year": year,
            "source": "tmdb_api",
        }


def fetch_external_ids_from_api(
    tmdb_id: int,
    media_type: str = "movie",
    *,
    api_key: Optional[str] = None,
    use_cache: bool = True,
    client: Optional[TmdbApiClient] = None,
) -> Optional[Dict[str, Any]]:
    """
    从 TMDB API 拉取 imdb_id / tvdb_id（带磁盘缓存）。

    @param tmdb_id: TMDB 作品 ID
    @param media_type: movie | tv
    @param api_key: 可选覆盖 API Key
    @param use_cache: 是否读写缓存
    @param client: 可选复用 TmdbApiClient
    @returns: metadata 字典；失败返回 None
    """
    cache_key = _cache_key(tmdb_id, media_type)
    cache = _cache_load() if use_cache else {}
    if use_cache and cache_key in cache:
        return dict(cache[cache_key])

    api_client = client or TmdbApiClient(api_key=api_key)
    row = api_client.fetch_metadata(tmdb_id, media_type)
    if not row:
        return None

    if use_cache:
        cache[cache_key] = row
        _cache_save(cache)
    return row


def warm_external_ids_cache(
    slots: List[Dict[str, Any]],
    *,
    api_key: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    批量预热 slot 清单涉及的 TMDB external_ids 缓存。

    @param slots: benchmark slot JSON 数组
    @param api_key: 可选 API Key
    @param force: True 时忽略已有缓存
    @returns: 预热摘要
    """
    client = TmdbApiClient(api_key=api_key)
    if not client.configured():
        return {"ok": False, "error": "未配置 RM_TMDB_API_KEY"}

    seen: Set[Tuple[int, str]] = set()
    ok_count = 0
    skip_count = 0
    fail_count = 0
    cache = _cache_load()

    for slot in slots:
        tmdb_id = int(slot["tmdb_id"])
        media_type = str(slot.get("media_type") or slot.get("media_kind") or "tv")
        key_tuple = (tmdb_id, media_type)
        if key_tuple in seen:
            continue
        seen.add(key_tuple)

        cache_key = _cache_key(tmdb_id, media_type)
        if not force and cache_key in cache and cache[cache_key].get("imdb_id"):
            skip_count += 1
            continue

        row = client.fetch_metadata(tmdb_id, media_type)
        if row and row.get("imdb_id"):
            cache[cache_key] = row
            ok_count += 1
        else:
            fail_count += 1

    _cache_save(cache)
    return {
        "ok": True,
        "unique_works": len(seen),
        "ok_count": ok_count,
        "skip_count": skip_count,
        "fail_count": fail_count,
        "api_requests": client.request_count,
        "cache_file": str(CACHE_FILE),
    }


def enrich_external_ids(
    tmdb_id: int,
    media_type: str,
    *,
    title: Optional[str] = None,
    base: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    合并 standalone / TMDB API / slot title，供 fetch 使用。

    @param tmdb_id: TMDB ID
    @param media_type: movie | tv
    @param title: slot 导出标题
    @param base: 已有字段覆盖
    @returns: enriched external_ids 字典
    """
    from workflow.metadata.external_ids import resolve_external_ids

    ext = resolve_external_ids(tmdb_id, media_type, title=title)
    if base:
        for key, value in base.items():
            if value is not None:
                ext[key] = value

    api_row = fetch_external_ids_from_api(tmdb_id, media_type)
    if api_row:
        if api_row.get("imdb_id"):
            ext["imdb_id"] = api_row["imdb_id"]
        if api_row.get("tvdb_id"):
            ext["tvdb_id"] = api_row["tvdb_id"]
        if api_row.get("title") and not ext.get("title"):
            ext["title"] = api_row["title"]
        if api_row.get("original_language"):
            ext["original_language"] = api_row["original_language"]
        if api_row.get("year") and not ext.get("year"):
            ext["year"] = api_row["year"]
        ext["source"] = api_row.get("source", ext.get("source"))

    if title and not ext.get("title"):
        ext["title"] = title
    if ext.get("source") == "standalone_missing" and ext.get("title"):
        ext["source"] = "slot_title"
    return ext
