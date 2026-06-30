#!/usr/bin/env pwsh
# ReleaseMatch Block A4: install/start Jackett on Windows and configure API Key.
# @file scripts/setup_jackett_a4.ps1
#
# Usage (run in PowerShell, from releasematch/):
#   .\scripts\setup_jackett_a4.ps1
#   .\scripts\setup_jackett_a4.ps1 -ApiKey "paste-your-key-here"

param(
    [string]$ApiKey = "",
    [string]$JackettUrl = "http://127.0.0.1:9117"
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$AccountsPath = Join-Path $Root "workflow\torrent_sources\accounts.local.json"
$Py = Join-Path $Root ".venv\Scripts\python.exe"

function Test-JackettPort {
    param([string]$Url)
    try {
        $uri = [Uri]$Url
        $tcp = Test-NetConnection -ComputerName $uri.Host -Port $uri.Port -WarningAction SilentlyContinue
        return [bool]$tcp.TcpTestSucceeded
    } catch {
        return $false
    }
}

function Test-JackettHttp {
    param([string]$Url)
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 8
        return @{ Ok = $true; Status = $r.StatusCode }
    } catch {
        return @{ Ok = $false; Error = $_.Exception.Message }
    }
}

function Update-AccountsApiKey {
    param([string]$Path, [string]$Key)
    if (-not (Test-Path $Path)) {
        Copy-Item (Join-Path $Root "workflow\torrent_sources\accounts.example.json") $Path
    }
    $json = Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $json.jackett) { $json | Add-Member -NotePropertyName jackett -NotePropertyValue (@{}) }
    $json.jackett.api_key = $Key
    $json.jackett.base_url = $JackettUrl
    $json | ConvertTo-Json -Depth 6 | Out-File $Path -Encoding utf8NoBOM
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " ReleaseMatch  A4  Jackett  Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- Step 0: environment snapshot ---
$dockerOk = $null -ne (Get-Command docker -ErrorAction SilentlyContinue)
$portOk = Test-JackettPort -Url $JackettUrl
$http = Test-JackettHttp -Url $JackettUrl

Write-Host "[0] Environment" -ForegroundColor Yellow
Write-Host "    Docker CLI : $(if ($dockerOk) { 'found' } else { 'NOT found (use Windows installer)' })"
Write-Host "    Port 9117  : $(if ($portOk) { 'OPEN' } else { 'closed' })"
Write-Host "    HTTP       : $(if ($http.Ok) { "OK ($($http.Status))" } else { "FAIL - $($http.Error)" })"
Write-Host ""

# --- Step 1: install if not running ---
if (-not $portOk) {
    Write-Host "[1] Jackett is not running. Choose an install method:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Option A (recommended) - winget:" -ForegroundColor Green
    Write-Host "    winget install --id Jackett.Jackett -e"
    Write-Host ""
    Write-Host "  Option B - official Windows installer:" -ForegroundColor Green
    Write-Host "    https://github.com/Jackett/Jackett/releases/latest"
    Write-Host "    Download Jackett.Installer.Windows.exe and run it."
    Write-Host ""
    Write-Host "  Option C - Docker (if you install Docker Desktop later):" -ForegroundColor Green
    Write-Host "    docker run -d --name jackett -p 9117:9117 -v C:\jackett\config:/config linuxserver/jackett:latest"
    Write-Host ""
    Write-Host "  After install, start the service:" -ForegroundColor DarkYellow
    Write-Host "    net start Jackett"
    Write-Host "    (or Services.msc -> Jackett -> Start)"
    Write-Host ""

    $tryWinget = Read-Host "Try winget install now? [y/N]"
    if ($tryWinget -match '^[yY]') {
        winget install --id Jackett.Jackett -e --accept-package-agreements --accept-source-agreements
        Write-Host "Starting Jackett service..." -ForegroundColor Yellow
        Start-Sleep -Seconds 3
        try { net start Jackett 2>$null } catch { Write-Host "If net start fails, start Jackett from Services or Start Menu." }
        Start-Sleep -Seconds 5
        $portOk = Test-JackettPort -Url $JackettUrl
        $http = Test-JackettHttp -Url $JackettUrl
    } else {
        Write-Host ""
        Write-Host "Install Jackett manually, then re-run:" -ForegroundColor Cyan
        Write-Host "  .\scripts\setup_jackett_a4.ps1"
        Write-Host ""
        $open = Read-Host "Open Jackett releases page in browser? [Y/n]"
        if ($open -notmatch '^[nN]') {
            Start-Process "https://github.com/Jackett/Jackett/releases/latest"
        }
        exit 1
    }
}

if (-not (Test-JackettPort -Url $JackettUrl)) {
    Write-Host "[FAIL] Port 9117 still closed. Start Jackett and re-run this script." -ForegroundColor Red
    exit 1
}

Write-Host "[1] Jackett port is open." -ForegroundColor Green
Write-Host ""

# --- Step 2: open dashboard ---
$dashUrl = "$JackettUrl/UI/Dashboard"
Write-Host "[2] Open Jackett Dashboard to copy API Key:" -ForegroundColor Yellow
Write-Host "    $dashUrl"
Write-Host "    Top-right: 'Copy API Key' (or System -> API Key)"
Write-Host ""
Start-Process $dashUrl

# --- Step 3: API Key ---
if (-not $ApiKey) {
    $ApiKey = Read-Host "Paste your Jackett API Key here"
}
$ApiKey = $ApiKey.Trim()
if (-not $ApiKey -or $ApiKey -eq "YOUR_JACKETT_API_KEY") {
    Write-Host "[FAIL] API Key is empty or still placeholder." -ForegroundColor Red
    exit 1
}

Update-AccountsApiKey -Path $AccountsPath -Key $ApiKey
Write-Host "[3] Saved API Key to accounts.local.json" -ForegroundColor Green
Write-Host ""

# --- Step 4: Torznab smoke test ---
$testUrl = "$JackettUrl/api/v2.0/indexers/all/results/torznab/api?apikey=$ApiKey&t=tvsearch&tvdbid=81189&season=4&ep=6&cache=false"
Write-Host "[4] Torznab smoke test (Breaking Bad S04E06)..." -ForegroundColor Yellow
try {
    $tr = Invoke-WebRequest -Uri $testUrl -UseBasicParsing -TimeoutSec 45
    Write-Host "    OK HTTP $($tr.StatusCode), bytes=$($tr.RawContentLength)" -ForegroundColor Green
} catch {
    Write-Host "    FAIL: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "    Tip: add indexers in Jackett Dashboard first (1337x, eztv, etc.)" -ForegroundColor DarkYellow
}

# --- Step 5: project status ---
Write-Host ""
Write-Host "[5] ReleaseMatch status:" -ForegroundColor Yellow
if (Test-Path $Py) {
    & $Py -m workflow.torrent_sources.run status
} else {
    Write-Host "    .venv not found. Run .\scripts\setup_block_a.ps1 first." -ForegroundColor DarkYellow
}

Write-Host ""
Write-Host "A4 done. Next: .\scripts\poc_phase0.ps1  (Block B)" -ForegroundColor Cyan
Write-Host ""
