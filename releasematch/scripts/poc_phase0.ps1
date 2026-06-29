#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ReleaseMatch Phase 0 PoC：验证四层数据源连通性。

@file scripts/poc_phase0.ps1
@description
  对应 download-resources/README.md §四 与 02 文档 §十二。
  需在本地启动 Jackett 并填入 API Key 后执行 Jackett 相关测试。
"""

param(
    [string]$JackettBaseUrl = "http://127.0.0.1:9117",
    [string]$JackettApiKey = $env:JACKETT_API_KEY
)

$ErrorActionPreference = "Continue"

Write-Host "=== ReleaseMatch Phase 0 PoC ===" -ForegroundColor Cyan

# Breaking Bad TVDB 81189 S04E06
if ($JackettApiKey) {
    $jackettUrl = "$JackettBaseUrl/api/v2.0/indexers/all/results/torznab/api?apikey=$JackettApiKey&t=tvsearch&tvdbid=81189&season=4&ep=6&cache=false"
    Write-Host "`n[1/4] Jackett Torznab (Breaking Bad S04E06)..." -ForegroundColor Yellow
    try {
        $r = Invoke-WebRequest -Uri $jackettUrl -UseBasicParsing -TimeoutSec 30
        Write-Host "  OK status=$($r.StatusCode) bytes=$($r.RawContentLength)" -ForegroundColor Green
    } catch {
        Write-Host "  FAIL: $_" -ForegroundColor Red
    }
} else {
    Write-Host "`n[1/4] Jackett SKIPPED (set JACKETT_API_KEY env or edit script)" -ForegroundColor DarkYellow
}

Write-Host "`n[2/4] EZTV JSON (Breaking Bad imdb 0904747)..." -ForegroundColor Yellow
try {
    $r = Invoke-WebRequest -Uri "https://eztvx.to/api/get-torrents?imdb_id=904747&limit=5&page=1" -UseBasicParsing -TimeoutSec 30
    Write-Host "  OK status=$($r.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "  FAIL: $_" -ForegroundColor Red
}

Write-Host "`n[3/4] YTS API (The Matrix imdb tt0133093)..." -ForegroundColor Yellow
try {
    $r = Invoke-WebRequest -Uri "https://yts.mx/api/v2/movie_details.json?imdb_id=tt0133093" -UseBasicParsing -TimeoutSec 30
    Write-Host "  OK status=$($r.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "  FAIL: $_" -ForegroundColor Red
}

Write-Host "`n[4/4] Nyaa RSS (Breaking Bad anime category)..." -ForegroundColor Yellow
try {
    $r = Invoke-WebRequest -Uri "https://nyaa.si/?page=rss&q=Breaking+Bad&c=1_0" -UseBasicParsing -TimeoutSec 30
    Write-Host "  OK status=$($r.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "  FAIL: $_" -ForegroundColor Red
}

Write-Host "`nDone. 详见 download-resources/02-数据源技术方案 §十二" -ForegroundColor Cyan
