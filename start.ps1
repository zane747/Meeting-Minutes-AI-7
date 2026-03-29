$Host.UI.RawUI.WindowTitle = "Meeting Minutes AI"

Write-Host ""
Write-Host "  ====================================" -ForegroundColor Cyan
Write-Host "   Meeting Minutes AI" -ForegroundColor Cyan
Write-Host "  ====================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "  [ERROR] uv not found. Install: pip install uv" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to close"
    exit 1
}

if (-not (Test-Path ".env")) {
    Write-Host "  [WARN] .env not found, copying from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "  [INFO] Please edit .env" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "  [1/2] Syncing dependencies..." -ForegroundColor White
uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  [ERROR] Sync failed" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host ""
Write-Host "  [2/2] Starting server..." -ForegroundColor White
Write-Host ""
Write-Host "  ====================================" -ForegroundColor Green
Write-Host "   http://localhost:8000" -ForegroundColor Green
Write-Host "   Ctrl+C to stop" -ForegroundColor Green
Write-Host "  ====================================" -ForegroundColor Green
Write-Host ""

Start-Job { Start-Sleep 2; Start-Process "http://localhost:8000" } | Out-Null

uv run uvicorn app.main:app --reload --port 8000

Write-Host ""
Write-Host "  Server stopped." -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to close"