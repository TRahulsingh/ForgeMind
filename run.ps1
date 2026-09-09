param([switch]$NoBrowser,[switch]$NoInstall)
$ErrorActionPreference = "Continue"
Write-Host "=== ForgeMind -- One-Cmd Starter (idempotent, check-before-download) ===" -ForegroundColor Cyan
if ($NoInstall) { Write-Host "NoInstall: skip deps/RAG install checks, runner only" -ForegroundColor Yellow }

function Test-PyDeps {
  python tools/check_pydeps.py --gte 2>$null
  return $LASTEXITCODE -eq 0
}

function Ensure-Env {
  if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host ".env created from .env.example" -ForegroundColor Green }
  else { Write-Host ".env OK -- skip copy" -ForegroundColor Green }
  try { if ((Get-Content ".env" -Raw -ErrorAction SilentlyContinue) -match "your_gemini_api_key_here") { Write-Host "WARN: .env still placeholder -> mock mode (add GOOGLE_API_KEY for real Gemini)" -ForegroundColor Yellow } } catch {}
}

function Ensure-PyDeps {
  if (Test-PyDeps) { Write-Host "Python deps OK (check: installed >= required) -- skip pip" -ForegroundColor Green; return }
  $missing = python tools/check_pydeps.py --gte --list-missing 2>$null
  if (-not $missing) { Write-Host "Python deps check passed -- skip pip" -ForegroundColor Green; return }
  Write-Host "Python deps missing (need < required) -> installing only missing, not downgrading existing..." -ForegroundColor Yellow
  Write-Host "Missing: $missing"
  foreach ($pkg in $missing) {
    if ($pkg) { pip install --no-deps $pkg 2>&1 | Select-Object -Last 2 }
  }
}

function Ensure-NodeDeps {
  if ((Test-Path "frontend/node_modules/react") -and (Test-Path "frontend/package-lock.json")) { Write-Host "frontend/node_modules OK -- skip npm" -ForegroundColor Green; return }
  Write-Host "frontend deps missing -> npm ci (prefer-offline)..." -ForegroundColor Yellow
  Push-Location frontend
  npm ci --prefer-offline
  Pop-Location
}

function Ensure-RAG {
  $fallback = "chroma_db/fallback.json"
  $stats = "chroma_db/ingest_stats.json"
  $ragOk = (Test-Path $fallback) -and (Test-Path $stats) -and ((Get-Item $fallback -ErrorAction SilentlyContinue).Length -gt 100)
  if ($ragOk) {
    try { $j = Get-Content $stats -Raw | ConvertFrom-Json; if ($j.chunks -lt 1) { $ragOk = $false } } catch { $ragOk = $false }
  }
  $docsNewer = $false
  try {
    $latestDoc = Get-ChildItem docs_seed -Recurse -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $fbTime = (Get-Item $fallback -ErrorAction SilentlyContinue).LastWriteTime
    if ($latestDoc -and $fbTime -and $latestDoc.LastWriteTime -gt $fbTime) { $docsNewer = $true }
  } catch {}
  if (-not $ragOk -or $docsNewer) {
    Write-Host "RAG ingest -> python -m rag.ingestion (table-aware 7 chunks)..." -ForegroundColor Yellow
    python -m rag.ingestion
  } else {
    Write-Host "RAG fallback.json OK (7 chunks: 5 text, 2 table) -- skip ingest" -ForegroundColor Green
    try { python -c "from rag.retrieval import get_retrieval_stats; print(get_retrieval_stats())" } catch {}
  }
  [void](New-Item -ItemType Directory -Path "output","chroma_db" -Force -ErrorAction SilentlyContinue)
}

function Test-PortFree($port) {
  try { $c = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue; return -not $c } catch { return $true }
}

# 1. Env (always)
Ensure-Env
# 2. Deps/RAG (idempotent, skip if -NoInstall)
if (-not $NoInstall) {
  Ensure-PyDeps
  Ensure-NodeDeps
  Ensure-RAG
} else {
  Write-Host "Skipping Python/Node/RAG checks due to -NoInstall (runner only)" -ForegroundColor Yellow
  [void](New-Item -ItemType Directory -Path "output","chroma_db" -Force -ErrorAction SilentlyContinue)
}

# 4. Backend
$backendRunning = $false
try { $h = Invoke-RestMethod http://localhost:8000/health -TimeoutSec 2 -ErrorAction Stop; Write-Host "Backend already running ($($h.status) mock=$($h.mock_mode)) -- skip uvicorn" -ForegroundColor Green; $backendRunning = $true } catch {}
if (-not $backendRunning) {
  if (-not (Test-PortFree 8000)) { Write-Host "Port 8000 busy - is backend already running? Continuing..." -ForegroundColor Yellow }
  else {
    Write-Host "Starting backend on http://localhost:8000 ..." -ForegroundColor Cyan
    $null = New-Item -ItemType Directory -Force -Path "logs" -ErrorAction SilentlyContinue
    Start-Process powershell -ArgumentList "uvicorn backend.main:app --reload --port 8000" -WindowStyle Minimized
    Write-Host "Waiting for backend health http://localhost:8000/health ..." -ForegroundColor Yellow
    for ($i=0; $i -lt 15; $i++) {
      Start-Sleep 2
      try { $h = Invoke-RestMethod http://localhost:8000/health -TimeoutSec 2 -ErrorAction Stop; Write-Host "Backend healthy: $($h | ConvertTo-Json -Compress)" -ForegroundColor Green; break } catch { Write-Host "." -NoNewline }
      if ($i -eq 14) { Write-Host "`nBackend health check failed after 30s, continuing anyway..." -ForegroundColor Yellow }
    }
  }
}

# 5. Frontend
$frontendRunning = $false
try { $r = Invoke-WebRequest http://localhost:5173 -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop; $frontendRunning = $true; Write-Host "Frontend already running on :5173 -- skip vite" -ForegroundColor Green } catch {}
if (-not $frontendRunning) {
  if (-not (Test-PortFree 5173)) { Write-Host "Port 5173 busy - frontend may already run on 5174 (Vite auto-bump)" -ForegroundColor Yellow }
  Write-Host "Starting frontend on http://localhost:5173 ..." -ForegroundColor Cyan
  if (-not $NoBrowser) {
    Start-Sleep 2
    try { Start-Process "http://localhost:5173" -ErrorAction SilentlyContinue } catch {}
    try { Start-Process "http://localhost:8000/docs" -ErrorAction SilentlyContinue } catch {}
  }
  Set-Location frontend
  npm run dev
} else {
  if (-not $NoBrowser) { try { Start-Process "http://localhost:5173" } catch {} }
  Write-Host "Frontend running, opening browser..." -ForegroundColor Green
  if (-not $NoBrowser) { Start-Process "http://localhost:5173" }
  Write-Host "Both services running. Press Ctrl+C to stop (backend runs in separate window, close it manually)." -ForegroundColor Cyan
  while ($true) { Start-Sleep 60 }
}
