param([string]$PythonPath = '')

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
if (-not $PythonPath) {
    $PythonPath = Join-Path $projectRoot '.venv-bedrock\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $PythonPath)) {
        $PythonPath = (Get-Command python -ErrorAction Stop).Source
    }
}
Push-Location (Join-Path $PSScriptRoot 'ui')
try {
    # Windows PowerShell treats native stderr (including build progress) as errors.
    # Use the native exit code to distinguish logging from command failure.
    $ErrorActionPreference = 'Continue'
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed. Install UI dependencies with npm ci first.' }
} finally {
    $ErrorActionPreference = 'Stop'
    Pop-Location
}

Push-Location $projectRoot
try {
    $ErrorActionPreference = 'Continue'
    & $PythonPath (Join-Path $PSScriptRoot 'prepare_drivers.py')
    if ($LASTEXITCODE -ne 0) { throw 'Browser driver preparation failed.' }
    & $PythonPath -m PyInstaller --noconfirm (Join-Path $PSScriptRoot 'CMSCustomerSearch.spec')
    if ($LASTEXITCODE -ne 0) { throw 'CMSCustomerSearch build failed.' }
    & $PythonPath (Join-Path $PSScriptRoot 'smoke_exe.py')
    if ($LASTEXITCODE -ne 0) { throw 'Packaged smoke test failed.' }
    $ErrorActionPreference = 'Stop'

    $portable = Join-Path $projectRoot 'dist\CMSCustomerSearch-portable'
    New-Item -ItemType Directory -Path $portable -Force | Out-Null
    $exe = Join-Path $portable 'CMSCustomerSearch.exe'
    $template = Join-Path $portable '.env.example'
    $readme = Join-Path $portable 'README.md'
    Copy-Item -LiteralPath (Join-Path $projectRoot 'dist\CMSCustomerSearch.exe') -Destination $exe -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'portable.env.example') -Destination $template -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'PORTABLE.md') -Destination $readme -Force
    # Explicit allowlist: never archive an operator's local .env or results.
    Compress-Archive -LiteralPath $exe, $template, $readme `
        -DestinationPath (Join-Path $projectRoot 'dist\CMSCustomerSearch-portable.zip') -Force
} finally {
    $ErrorActionPreference = 'Stop'
    Pop-Location
}
