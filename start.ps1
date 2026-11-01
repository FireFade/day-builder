# Day Builder v1.0 beta — Windows local start
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$DotEnv = Join-Path $Root ".env"
if (-not (Test-Path $DotEnv)) {
    Copy-Item (Join-Path $Root ".env.example") $DotEnv
    Write-Host "Created .env. To enable Google/Microsoft, fill OAuth keys and restart."
}
# Load local project variables for this process. Do not echo secrets.
Get-Content $DotEnv | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $parts = $line.Split('=', 2)
        $key = $parts[0].Trim()
        if ($key -match '^[A-Z][A-Z0-9_]*$') {
            $val = $parts[1].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}
Set-Location $Backend
if (-not (Test-Path $Python)) {
    Write-Host "Creating Python virtual environment..."
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python 3.11+ is required." }
}
Write-Host "Installing/updating Python dependencies..."
& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
Write-Host "Applying database migrations..."
& $Python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Database migration failed" }
Write-Host "Open Day Builder at http://localhost:8000/ (Ctrl+C to stop)."
& $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
