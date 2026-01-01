# Voice Quran - Doctor Script (Windows PowerShell)

$ErrorActionPreference = "Continue"

# Kök dizin: script'in bulunduğu dizinden bir üst
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptPath
$backendDir = Join-Path $rootDir "ml-service"
$webDir = Join-Path $rootDir "web"

# Eğer rootDir bulunamazsa, mevcut dizini kullan
if (-not (Test-Path $backendDir)) {
    $rootDir = Get-Location
    $backendDir = Join-Path $rootDir "ml-service"
    $webDir = Join-Path $rootDir "web"
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Voice Quran - Doctor Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# A) ÖN KOŞUL KONTROLÜ
Write-Host "[A] Ön Koşul Kontrolü..." -ForegroundColor Yellow

try {
    $pyVersion = py -V 2>&1
    Write-Host "  [OK] Python: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] Python bulunamadı!" -ForegroundColor Red
    Write-Host "     Minimum: Python 3.11+ önerilir" -ForegroundColor Yellow
    exit 1
}

try {
    $pipVersion = pip -V 2>&1
    Write-Host "  [OK] pip: $pipVersion" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] pip bulunamadı!" -ForegroundColor Red
    exit 1
}

try {
    $nodeVersion = node -v 2>&1
    Write-Host "  [OK] Node: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] Node bulunamadı!" -ForegroundColor Red
    Write-Host "     Minimum: Node LTS (18+) önerilir" -ForegroundColor Yellow
    exit 1
}

try {
    $npmVersion = npm -v 2>&1
    Write-Host "  [OK] npm: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] npm bulunamadı!" -ForegroundColor Red
    exit 1
}

Write-Host ""

# B) BACKEND DOKTORU
Write-Host "[B] Backend (ml-service) Kontrolü..." -ForegroundColor Yellow

Push-Location $backendDir

# Dosya kontrolü
$requiredFiles = @(
    "main.py",
    "requirements.txt",
    "utils\audio.py",
    "utils\arabic_norm.py",
    "utils\quran_index.py",
    "utils\seq_align.py",
    "utils\tracking.py",
    "utils\wav_io.py"
)

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "  [OK] $file" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] $file bulunamadı!" -ForegroundColor Red
        Pop-Location
        exit 1
    }
}

# Sanal ortam kontrolü
$venvPath = Join-Path $backendDir ".venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "  [*] Sanal ortam oluşturuluyor..." -ForegroundColor Yellow
    py -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [FAIL] Sanal ortam oluşturulamadı!" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Write-Host "  [OK] Sanal ortam oluşturuldu" -ForegroundColor Green
} else {
    Write-Host "  [OK] Sanal ortam mevcut" -ForegroundColor Green
}

# Sanal ortamı aktifleştir
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    & $activateScript
    Write-Host "  [OK] Sanal ortam aktifleştirildi" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Activate script bulunamadı!" -ForegroundColor Red
    Pop-Location
    exit 1
}

# pip upgrade
Write-Host "  [*] pip güncelleniyor..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [WARN] pip güncelleme başarısız (devam ediliyor)" -ForegroundColor Yellow
}

# Paket kurulumu
Write-Host "  [*] Paketler kuruluyor..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] Paket kurulumu başarısız!" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  [OK] Paketler kuruldu" -ForegroundColor Green

# Import test
Write-Host "  [*] Import testi..." -ForegroundColor Yellow
$importTest = python -c "import fastapi, uvicorn, numpy; import rapidfuzz; import faster_whisper; import imageio_ffmpeg; print('imports_ok')" 2>&1
if ($importTest -match "imports_ok") {
    Write-Host "  [OK] Import testi başarılı" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Import testi başarısız!" -ForegroundColor Red
    Write-Host "     Hata: $importTest" -ForegroundColor Red
    Pop-Location
    exit 1
}

# Sürüm raporu
Write-Host "  [*] Sürüm raporu alınıyor..." -ForegroundColor Yellow
$versionReport = python -c "import fastapi, uvicorn, numpy, rapidfuzz, faster_whisper, pydantic; print('fastapi', fastapi.__version__); print('uvicorn', uvicorn.__version__); print('numpy', numpy.__version__); print('rapidfuzz', rapidfuzz.__version__); print('faster_whisper', faster_whisper.__version__); print('pydantic', pydantic.__version__)" 2>&1
Write-Host "  [OK] Sürümler:" -ForegroundColor Green
$versionReport | ForEach-Object { Write-Host "     $_" -ForegroundColor Gray }

# Quran text kontrolü
$quranFile = Join-Path $backendDir "quran\quran_tanzil.txt"
if (-not (Test-Path $quranFile)) {
    Write-Host "  [*] Kuran metni indiriliyor..." -ForegroundColor Yellow
    python scripts\fetch_quran_text.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [WARN] Kuran metni indirilemedi (devam ediliyor)" -ForegroundColor Yellow
    } else {
        Write-Host "  [OK] Kuran metni indirildi" -ForegroundColor Green
    }
} else {
    Write-Host "  [OK] Kuran metni mevcut" -ForegroundColor Green
}

# requirements.lock oluştur
Write-Host "  [*] requirements.lock.txt oluşturuluyor..." -ForegroundColor Yellow
pip freeze > requirements.lock.txt
Write-Host "  [OK] requirements.lock.txt oluşturuldu" -ForegroundColor Green

Pop-Location
Write-Host ""

# C) WEB DOKTORU
Write-Host "[C] Web (Next.js) Kontrolü..." -ForegroundColor Yellow

Push-Location $webDir

# Dosya kontrolü
$requiredWebFiles = @(
    "package.json",
    "app\page.tsx",
    "public\worklets\pcm-processor.js"
)

foreach ($file in $requiredWebFiles) {
    if (Test-Path $file) {
        Write-Host "  [OK] $file" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] $file bulunamadı (opsiyonel)" -ForegroundColor Yellow
    }
}

# .env.local kontrolü
$envFile = Join-Path $webDir ".env.local"
if (-not (Test-Path $envFile)) {
    Write-Host "  [*] .env.local oluşturuluyor..." -ForegroundColor Yellow
    "NEXT_PUBLIC_API_BASE=http://localhost:8000" | Out-File -FilePath $envFile -Encoding utf8
    Write-Host "  [OK] .env.local oluşturuldu" -ForegroundColor Green
} else {
    Write-Host "  [OK] .env.local mevcut" -ForegroundColor Green
}

# npm install
Write-Host "  [*] npm paketleri kuruluyor..." -ForegroundColor Yellow
if (Test-Path "package-lock.json") {
    npm ci
} else {
    npm install
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] npm install başarısız!" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  [OK] npm paketleri kuruldu" -ForegroundColor Green

# npm ls
Write-Host "  [*] Bağımlılık listesi alınıyor..." -ForegroundColor Yellow
$npmLs = npm ls --depth=0 2>&1
Write-Host "  [OK] Bağımlılıklar:" -ForegroundColor Green
$npmLs | Select-Object -First 10 | ForEach-Object { Write-Host "     $_" -ForegroundColor Gray }

# Build test
Write-Host "  [*] Build testi..." -ForegroundColor Yellow
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] Build başarısız!" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  [OK] Build başarılı" -ForegroundColor Green

Pop-Location

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "[OK] DOKTOR TESTİ TAMAMLANDI" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Çalıştırma komutları:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Backend:" -ForegroundColor Cyan
Write-Host "  cd `"$backendDir`"" -ForegroundColor White
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "  uvicorn main:app --host 0.0.0.0 --port 8000 --reload" -ForegroundColor White
Write-Host ""
Write-Host "Web (yeni terminal):" -ForegroundColor Cyan
Write-Host "  cd `"$webDir`"" -ForegroundColor White
Write-Host "  npm run dev" -ForegroundColor White
Write-Host ""
Write-Host "Smoke Test:" -ForegroundColor Cyan
Write-Host "  # Backend health check:" -ForegroundColor Gray
Write-Host "  Invoke-WebRequest http://localhost:8000/health | Select-Object -Expand Content" -ForegroundColor White
Write-Host ""
Write-Host "  # Web: http://localhost:3000" -ForegroundColor Gray
Write-Host "  # Test: Record -> Stop -> Send" -ForegroundColor Gray
Write-Host "  # Test: Track (timeline)" -ForegroundColor Gray
Write-Host "  # Test: Start Live (WebSocket)" -ForegroundColor Gray
Write-Host ""
