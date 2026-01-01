# Backend Başlatma Scripti
$ErrorActionPreference = "Continue"

# Mevcut dizini al
$currentDir = Get-Location

# ml-service dizinine git
$backendDir = Join-Path $currentDir "ml-service"

if (-not (Test-Path $backendDir)) {
    Write-Host "[HATA] ml-service dizini bulunamadi!" -ForegroundColor Red
    Write-Host "Mevcut dizin: $currentDir" -ForegroundColor Yellow
    exit 1
}

Set-Location $backendDir

# Venv kontrolü
if (-not (Test-Path .venv)) {
    Write-Host "[*] Virtual environment olusturuluyor..." -ForegroundColor Yellow
    py -m venv .venv
}

# Venv'i aktif et
Write-Host "[*] Virtual environment aktif ediliyor..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Paketleri kur
Write-Host "[*] Paketler kontrol ediliyor..." -ForegroundColor Yellow
pip install -q -r requirements.txt

# Backend'i başlat
Write-Host "[*] Backend baslatiliyor..." -ForegroundColor Green
Write-Host "Backend: http://localhost:8000" -ForegroundColor Cyan
Write-Host "Health: http://localhost:8000/health" -ForegroundColor Cyan
Write-Host ""
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

