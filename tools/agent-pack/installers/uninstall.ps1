param(
    [Parameter(Mandatory=$true)][string]$Target
)

$ErrorActionPreference = "Stop"
$TargetRoot = Resolve-Path $Target
$PackDirs = @(
    ".claude\commands\pm",
    ".claude\commands\dev",
    ".claude\commands\py",
    ".claude\commands\web",
    ".claude\commands\db",
    ".claude\commands\qa",
    ".claude\commands\sec",
    ".claude\commands\healthcare",
    ".claude\commands\terminal",
    ".claude\commands\release",
    ".claude\skills\pm-plan",
    ".claude\skills\qa-acceptance-review",
    ".claude\skills\python-browser-automation",
    ".claude\skills\python-desktop-automation",
    ".claude\skills\terminal-screen-mapping",
    ".claude\skills\healthcare-eligibility-workflow",
    ".claude\skills\healthcare-claims-workflow",
    ".claude\skills\postgres-schema-review",
    ".claude\skills\react-dashboard-ui",
    ".claude\skills\security-phi-secrets-review",
    ".claude\skills\release-readiness",
    ".agents\skills\pm-plan",
    ".agents\skills\qa-acceptance-review",
    ".agents\skills\python-browser-automation",
    ".agents\skills\python-desktop-automation",
    ".agents\skills\terminal-screen-mapping",
    ".agents\skills\healthcare-eligibility-workflow",
    ".agents\skills\healthcare-claims-workflow",
    ".agents\skills\postgres-schema-review",
    ".agents\skills\react-dashboard-ui",
    ".agents\skills\security-phi-secrets-review",
    ".agents\skills\release-readiness"
)

$PackAgentFiles = @(
    ".claude\agents\project-manager.md",
    ".claude\agents\python-automation-engineer.md",
    ".claude\agents\web-ui-engineer.md",
    ".claude\agents\backend-data-engineer.md",
    ".claude\agents\qa-reviewer.md",
    ".claude\agents\healthcare-ops-sme-us.md",
    ".claude\agents\terminal-automation-engineer.md",
    ".claude\agents\agentic-ai-architect.md",
    ".claude\agents\security-compliance-reviewer.md",
    ".claude\agents\devops-release-engineer.md"
)

foreach ($Rel in $PackDirs) {
    $Path = Join-Path $TargetRoot $Rel
    if (Test-Path $Path) {
        Write-Host "Remove pack directory: $Path"
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

foreach ($Rel in $PackAgentFiles) {
    $Path = Join-Path $TargetRoot $Rel
    if (Test-Path $Path) {
        Write-Host "Remove pack agent file: $Path"
        Remove-Item -LiteralPath $Path -Force
    }
}

foreach ($RootFile in @("AGENTS.md", "CLAUDE.md")) {
    $Path = Join-Path $TargetRoot $RootFile
    if (Test-Path $Path) {
        $FirstLines = Get-Content -LiteralPath $Path -TotalCount 5
        if ($FirstLines -match "senior-agent-pack:generated") {
            Write-Host "Remove generated file: $Path"
            Remove-Item -LiteralPath $Path -Force
        } else {
            Write-Host "Kept $Path because no generated marker was found."
        }
    }
}

Write-Host "Review any .senior-agent-pack-backup-* directories before deleting backups."
