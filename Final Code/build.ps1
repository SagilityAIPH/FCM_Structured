param([string]$Python = "")
$ErrorActionPreference = "Stop"
$finalCodeRoot = $PSScriptRoot
$repositoryRoot = Split-Path $finalCodeRoot -Parent
$workbenchFrontend = Join-Path $repositoryRoot "AI/workbench/frontend"
if (-not $Python) { $Python = Join-Path $repositoryRoot ".venv-bedrock/Scripts/python.exe" }
if (-not (Test-Path -LiteralPath $Python)) { throw "Python environment not found. Install AI/workbench/requirements.txt first." }
Push-Location $repositoryRoot
try {
    # The frontend is rebuilt first: PyInstaller bundles whatever is in dist/,
    # so skipping this silently ships a stale UI.
    & npm.cmd --prefix "$workbenchFrontend" ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
    & npm.cmd --prefix "$workbenchFrontend" run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    & $Python -m PyInstaller --noconfirm "$finalCodeRoot/final_code.spec"
    if ($LASTEXITCODE -ne 0) { throw "Executable build failed." }
    Write-Output "Built dist/FinalCode.exe. WebView2 Runtime is required."
    Write-Output "Verify with: dist/FinalCode.exe --self-test --report selftest.json"
} finally {
    Pop-Location
}
