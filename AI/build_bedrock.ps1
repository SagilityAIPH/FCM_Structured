$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    if (-not (Test-Path '.venv-bedrock/Scripts/python.exe')) {
        rtk proxy python -m venv .venv-bedrock
        if ($LASTEXITCODE -ne 0) { throw 'Failed to create build environment' }
    }
    rtk proxy .venv-bedrock/Scripts/python.exe -m pip install -r AI/requirements-bedrock-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install build dependencies' }
    rtk proxy .venv-bedrock/Scripts/python.exe -m PyInstaller --noconfirm AI/bedrock.spec
    if ($LASTEXITCODE -ne 0) { throw 'EXE build failed' }
    Write-Host 'Created dist/AI-FCM-Bedrock.exe'
} finally {
    Pop-Location
}
