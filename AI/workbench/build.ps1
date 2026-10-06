param([string]$Python = "")
$ErrorActionPreference = "Stop"
$workbenchRoot = $PSScriptRoot
$repositoryRoot = Split-Path (Split-Path $workbenchRoot -Parent) -Parent
if (-not $Python) { $Python = Join-Path $repositoryRoot ".venv-bedrock/Scripts/python.exe" }
if (-not (Test-Path -LiteralPath $Python)) { throw "Python environment not found. Install workbench/requirements.txt first." }
Push-Location $repositoryRoot
try {
    & npm.cmd --prefix "$workbenchRoot/frontend" ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
    & npm.cmd --prefix "$workbenchRoot/frontend" run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    & $Python -m PyInstaller --noconfirm "$workbenchRoot/workbench.spec"
    if ($LASTEXITCODE -ne 0) { throw "Executable build failed." }
    Write-Output "Built dist/AI-FCM-Workbench.exe. WebView2 Runtime is required."
} finally {
    Pop-Location
}
