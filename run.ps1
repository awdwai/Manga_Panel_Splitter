$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

Write-Host "MangaAnimatorPrep launcher"
Write-Host "Repository root: $(Get-Location)"
Write-Host ""

$activateScript = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    Write-Host "Activating virtual environment: .venv"
    . $activateScript
} else {
    Write-Host "No .venv found; using system Python."
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if (-not $pyCommand) {
        Write-Error "Python was not found. Install Python 3.14+ or create .venv in this repository."
        Read-Host "Press Enter to exit"
        exit 1
    }
    $pythonExe = "py"
    $pythonArgs = @("-3")
} else {
    $pythonExe = "python"
    $pythonArgs = @()
}

try {
    Write-Host "Verifying Python dependencies..."
    & $pythonExe @pythonArgs -m pip check
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency check failed."
    }

    & $pythonExe @pythonArgs "scripts\check_runtime.py"
    if ($LASTEXITCODE -ne 0) {
        throw "Required GUI dependencies are missing."
    }

    Write-Host ""
    Write-Host "Launching MangaAnimatorPrep GUI..."
    & $pythonExe @pythonArgs -m MangaAnimatorPrep.main gui
    if ($LASTEXITCODE -ne 0) {
        throw "MangaAnimatorPrep exited with code $LASTEXITCODE."
    }
} catch {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "If dependencies are missing, run:"
    Write-Host "  python -m pip install -r requirements.txt"
    Read-Host "Press Enter to exit"
    exit 1
}
