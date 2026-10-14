$ErrorActionPreference = 'Stop'
$processDir = $PSScriptRoot
$repoDir = (Resolve-Path (Join-Path $processDir '../../..')).Path
$pythonExe = Join-Path $repoDir '.venv-bedrock/Scripts/python.exe'
if (!(Test-Path $pythonExe)) { throw 'Restore .venv-bedrock and install the packaging dependencies first.' }
# Keep build scratch outside the repository; only the finished artifact is copied.
$scratch = Join-Path $env:LOCALAPPDATA ('Temp/UnityAssignment-build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $scratch | Out-Null
Write-Host "Build scratch: $scratch"
Push-Location (Join-Path $processDir 'frontend')
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
} finally { Pop-Location }
Push-Location $repoDir
try {
    & $pythonExe -m PyInstaller --noconfirm --distpath (Join-Path $scratch 'dist') --workpath (Join-Path $scratch 'work') (Join-Path $processDir 'unity_assignment.spec')
    if ($LASTEXITCODE -ne 0) { throw 'UnityAssignment EXE build failed' }
    $exe = Join-Path $scratch 'dist/UnityAssignment.exe'
    $report = Join-Path $scratch 'self-test.txt'
    $check = Start-Process -FilePath $exe -ArgumentList @('--self-test', '--report', ('"' + $report + '"')) -Wait -PassThru
    if ($check.ExitCode -ne 0 -or !(Test-Path $report)) { throw "Built EXE self-test failed ($($check.ExitCode)); inspect $report" }
    Get-Content $report
    Write-Host "EXE self-test exit code: $($check.ExitCode)"
    New-Item -ItemType Directory -Force 'dist' | Out-Null
    Copy-Item -Force $exe 'dist/UnityAssignment.exe'
    $destination = Join-Path $repoDir 'dist/UnityAssignment.exe'
    $hash = (Get-FileHash -Algorithm SHA256 $destination).Hash.ToLowerInvariant()
    if ($hash -ne (Get-FileHash -Algorithm SHA256 $exe).Hash.ToLowerInvariant()) { throw 'Copied EXE checksum mismatch' }
    [System.IO.File]::WriteAllText(($destination + '.sha256'), ($hash + '  UnityAssignment.exe' + "`n"), [System.Text.UTF8Encoding]::new($false))
} finally { Pop-Location }
Write-Host 'Built dist/UnityAssignment.exe and UnityAssignment.exe.sha256. Microsoft Edge WebView2 Runtime is required.'
