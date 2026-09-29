$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$pythonPath = Join-Path $projectRoot '.venv-bedrock/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create the build environment and install requirements-build.txt first.'
}
Push-Location $projectRoot
try {
    & rtk proxy $pythonPath -m PyInstaller --noconfirm (Join-Path $PSScriptRoot 'CMSCustomerSearch.spec')
    if ($LASTEXITCODE -ne 0) { throw 'CMSCustomerSearch build failed.' }
} finally {
    Pop-Location
}
