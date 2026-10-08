$ErrorActionPreference = 'Stop'
$processDir = $PSScriptRoot
$repoDir = (Resolve-Path (Join-Path $processDir '../../..')).Path
$pythonExe = Join-Path $repoDir '.venv-bedrock/Scripts/python.exe'
Push-Location (Join-Path $processDir 'frontend')
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
} finally { Pop-Location }
Push-Location $repoDir
try {
    & $pythonExe -m PyInstaller --noconfirm (Join-Path $processDir 'subject_line_builder.spec')
    if ($LASTEXITCODE -ne 0) { throw 'EXE build failed' }
    & $pythonExe -c "import sys; sys.path.insert(0, 'Processes/SubjectLineBuilder/Deploy-Ready'); from excel_input import create_template; create_template('dist/SubjectLineBuilder-Input.xlsx'); create_template('Processes/SubjectLineBuilder/Stand-Alone/SubjectLineBuilder-Input.xlsx')"
    if ($LASTEXITCODE -ne 0) { throw 'Excel template generation failed' }
    & $pythonExe -c "import hashlib; from pathlib import Path; p=Path('dist/SubjectLineBuilder.exe'); p.with_suffix('.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest() + '  SubjectLineBuilder.exe' + chr(10))"
    if ($LASTEXITCODE -ne 0) { throw 'Checksum generation failed' }
} finally { Pop-Location }
Write-Host 'Built dist/SubjectLineBuilder.exe. Microsoft Edge WebView2 Runtime is required.'
