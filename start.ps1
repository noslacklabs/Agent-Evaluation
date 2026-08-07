$ErrorActionPreference = "Stop"

$projectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDirectory = Join-Path $projectDirectory "backend"
$frontendDirectory = Join-Path $projectDirectory "frontend"
$virtualPython = Join-Path $backendDirectory ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath (Join-Path $projectDirectory ".env"))) {
    Copy-Item -LiteralPath (Join-Path $projectDirectory ".env.example") -Destination (Join-Path $projectDirectory ".env")
    Write-Host "Created .env from .env.example. Add a judge-provider API key before real evaluations." -ForegroundColor Yellow
}

if (-not (Test-Path -LiteralPath $virtualPython)) {
    Write-Host "Creating backend virtual environment..." -ForegroundColor Cyan
    python -m venv (Join-Path $backendDirectory ".venv")
}

Write-Host "Installing backend dependencies..." -ForegroundColor Cyan
& $virtualPython -m pip install -r (Join-Path $backendDirectory "requirements.txt")

if (-not (Test-Path -LiteralPath (Join-Path $frontendDirectory "node_modules"))) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    Push-Location $frontendDirectory
    try { npm install } finally { Pop-Location }
}

$backendProcess = Start-Process -FilePath $virtualPython -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8002") -WorkingDirectory $backendDirectory -WindowStyle Hidden -PassThru
Write-Host "Agent Evaluator API: http://127.0.0.1:8002" -ForegroundColor Green
Write-Host "Agent Evaluator UI:  http://127.0.0.1:5173" -ForegroundColor Green

Push-Location $frontendDirectory
try {
    npm run dev
} finally {
    Pop-Location
    if (-not $backendProcess.HasExited) { Stop-Process -Id $backendProcess.Id }
}
