# Web Başlatma Scripti
$ErrorActionPreference = "Continue"

# Mevcut dizini al
$currentDir = Get-Location

# web dizinine git
$webDir = Join-Path $currentDir "web"

if (-not (Test-Path $webDir)) {
    Write-Host "[HATA] web dizini bulunamadi!" -ForegroundColor Red
    Write-Host "Mevcut dizin: $currentDir" -ForegroundColor Yellow
    exit 1
}

Set-Location $webDir

# Node paketlerini kontrol et
if (-not (Test-Path node_modules)) {
    Write-Host "[*] Node paketleri kuruluyor..." -ForegroundColor Yellow
    npm install
}

# Web'i başlat
Write-Host "[*] Web baslatiliyor..." -ForegroundColor Green
Write-Host "Web: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
npm run dev

