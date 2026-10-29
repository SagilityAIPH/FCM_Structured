param([string]$ReportPath = (Join-Path $env:LOCALAPPDATA 'hermes/profiles/omniroute/cache/scratch/cem-build/phase2/package-selftest.txt'))
$ErrorActionPreference = 'Stop'
$processDir = $PSScriptRoot
$repoDir = (Resolve-Path (Join-Path $processDir '../../..')).Path
$pythonExe = Join-Path $repoDir '.venv-bedrock/Scripts/python.exe'
if (!(Test-Path $pythonExe)) { throw 'Restore .venv-bedrock packaging dependencies first.' }
if (![System.IO.Path]::IsPathRooted($ReportPath)) { throw 'ReportPath must be a native absolute path.' }
$scratch = Join-Path $env:LOCALAPPDATA ('hermes/profiles/omniroute/cache/scratch/cem-build/package-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $scratch | Out-Null
Push-Location (Join-Path $processDir 'frontend')
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
} finally { Pop-Location }
Push-Location $repoDir
try {
    & $pythonExe -m PyInstaller --noconfirm --distpath (Join-Path $scratch 'dist') --workpath (Join-Path $scratch 'work') (Join-Path $processDir 'cem.spec')
    if ($LASTEXITCODE -ne 0) { throw 'CEMRequest EXE build failed' }
    $exe = Join-Path $scratch 'dist/CEMRequest.exe'
    $check = Start-Process -FilePath $exe -ArgumentList @('--self-test', '--report', ('"' + $ReportPath + '"')) -Wait -PassThru
    if ($check.ExitCode -ne 0 -or !(Test-Path $ReportPath)) { throw "Packaged self-test failed ($($check.ExitCode)); candidate retained at $exe" }
    Get-Content $ReportPath
    New-Item -ItemType Directory -Force (Join-Path $repoDir 'dist') | Out-Null
    $destination = Join-Path $repoDir 'dist/CEMRequest.exe'
    Copy-Item -Force $exe $destination
    $hash = (Get-FileHash -Algorithm SHA256 $destination).Hash.ToLowerInvariant()
    if ($hash -ne (Get-FileHash -Algorithm SHA256 $exe).Hash.ToLowerInvariant()) { throw 'Copied EXE checksum mismatch' }
    [System.IO.File]::WriteAllText(($destination + '.sha256'), ($hash + '  CEMRequest.exe' + "`n"), [System.Text.UTF8Encoding]::new($false))
} finally { Pop-Location }
Write-Host 'Candidate built and self-tested; live portal remains unverified.'
