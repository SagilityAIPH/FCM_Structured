param(
    [Parameter(Mandatory=$true)][string]$Target,
    [string]$Profile = "base",
    [switch]$Claude,
    [switch]$Codex,
    [switch]$All
)

$ErrorActionPreference = "Stop"
$PackRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$TargetRoot = Resolve-Path $Target
$Stamp = Get-Date -Format "yyyyMMddHHmmss"
$BackupRoot = Join-Path $TargetRoot ".senior-agent-pack-backup-$Stamp"
$Installed = New-Object System.Collections.Generic.List[string]

function Backup-File($Path) {
    if (Test-Path $Path) {
        New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
        Copy-Item -LiteralPath $Path -Destination (Join-Path $BackupRoot (Split-Path $Path -Leaf)) -Force
    }
}

function Copy-PackFile($Source, $Destination) {
    New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) | Out-Null
    Backup-File $Destination
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    $Installed.Add($Destination) | Out-Null
}

if (-not ($All -or $Claude -or $Codex)) { $Codex = $true }
if ($All) { $Claude = $true; $Codex = $true }

Copy-PackFile (Join-Path $PackRoot "AGENTS.md") (Join-Path $TargetRoot "AGENTS.md")

if ($Claude) {
    Copy-PackFile (Join-Path $PackRoot "CLAUDE.md") (Join-Path $TargetRoot "CLAUDE.md")
    Copy-Item -Path (Join-Path $PackRoot "agents\*.md") -Destination (New-Item -ItemType Directory -Force -Path (Join-Path $TargetRoot ".claude\agents")).FullName -Force
    Copy-Item -Path (Join-Path $PackRoot "commands\*") -Destination (New-Item -ItemType Directory -Force -Path (Join-Path $TargetRoot ".claude\commands")).FullName -Recurse -Force
    Copy-Item -Path (Join-Path $PackRoot "skills\*") -Destination (New-Item -ItemType Directory -Force -Path (Join-Path $TargetRoot ".claude\skills")).FullName -Recurse -Force
    $Installed.Add(".claude agents/commands/skills") | Out-Null
}

if ($Codex) {
    Copy-Item -Path (Join-Path $PackRoot "skills\*") -Destination (New-Item -ItemType Directory -Force -Path (Join-Path $TargetRoot ".agents\skills")).FullName -Recurse -Force
    $Installed.Add(".agents/skills") | Out-Null
}

Write-Host "Installed senior-agent-pack profile '$Profile' to $TargetRoot"
if (Test-Path $BackupRoot) { Write-Host "Backups: $BackupRoot" }
$Installed | ForEach-Object { Write-Host "- $_" }

