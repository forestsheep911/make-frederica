[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$RepoRoot = "",
    [string]$FredericaHome = $(if ($env:FREDERICA_HOME) { $env:FREDERICA_HOME } else { Join-Path $HOME ".frederica" }),
    [string]$CodexSkillDir = (Join-Path $HOME ".codex\skills\frederica"),
    [string]$AgentsSkillDir = (Join-Path $HOME ".agents\skills\frederica"),
    [switch]$SyncEnv,
    [switch]$AddToUserPath
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$repoRootPath = [System.IO.Path]::GetFullPath($RepoRoot)
$fredericaHomePath = [System.IO.Path]::GetFullPath($FredericaHome)
$binDir = Join-Path $fredericaHomePath "bin"
$configDir = Join-Path $fredericaHomePath "config"
$cmdWrapperPath = Join-Path $binDir "entrykit.cmd"
$psWrapperPath = Join-Path $binDir "entrykit.ps1"
$skillSource = Join-Path $repoRootPath "skills\frederica"
$legacyCodexSkillDir = Join-Path $HOME ".codex\skills\chat-knowledge-capture"
$legacyAgentsSkillDir = Join-Path $HOME ".agents\skills\chat-knowledge-capture"
$envSource = Join-Path $repoRootPath ".env"
$envTarget = Join-Path $configDir ".env"

if (-not (Test-Path -LiteralPath $skillSource)) {
    throw "Skill source not found: $skillSource"
}

$cmdWrapper = @"
@echo off
setlocal
set "ENTRYKIT_ROOT=$repoRootPath"
if defined PYTHONPATH (
  set "PYTHONPATH=%ENTRYKIT_ROOT%\src;%PYTHONPATH%"
) else (
  set "PYTHONPATH=%ENTRYKIT_ROOT%\src"
)
if not "%ENTRYKIT_PYTHON_BIN%"=="" (
  "%ENTRYKIT_PYTHON_BIN%" -m entrykit.cli %*
  exit /b %errorlevel%
)
where python >nul 2>nul
if not errorlevel 1 (
  python -m entrykit.cli %*
  exit /b %errorlevel%
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m entrykit.cli %*
  exit /b %errorlevel%
)
echo Could not find Python 3.10+ for entrykit. Set ENTRYKIT_PYTHON_BIN or install python.exe. 1>&2
exit /b 1
"@

$psWrapper = @"
`$ErrorActionPreference = 'Stop'
`$repoRoot = '$repoRootPath'
if (`$env:PYTHONPATH) {
    `$env:PYTHONPATH = "`$repoRoot\src;`$env:PYTHONPATH"
} else {
    `$env:PYTHONPATH = "`$repoRoot\src"
}
if (`$env:ENTRYKIT_PYTHON_BIN) {
    & `$env:ENTRYKIT_PYTHON_BIN -m entrykit.cli @args
    exit `$LASTEXITCODE
}
`$python = Get-Command python -ErrorAction SilentlyContinue
if (`$python) {
    & `$python.Source -m entrykit.cli @args
    exit `$LASTEXITCODE
}
`$py = Get-Command py -ErrorAction SilentlyContinue
if (`$py) {
    & `$py.Source -3 -m entrykit.cli @args
    exit `$LASTEXITCODE
}
Write-Error 'Could not find Python 3.10+ for entrykit. Set ENTRYKIT_PYTHON_BIN or install python.exe.'
exit 1
"@

function Ensure-Directory {
    param([string]$Path)
    if ($PSCmdlet.ShouldProcess($Path, "Create directory")) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

function Remove-TreeIfExists {
    param([string]$Path)
    if ((Test-Path -LiteralPath $Path) -and $PSCmdlet.ShouldProcess($Path, "Remove existing path")) {
        Remove-Item -Recurse -Force -LiteralPath $Path
    }
}

Ensure-Directory -Path $binDir
Ensure-Directory -Path (Split-Path -Parent $CodexSkillDir)
Ensure-Directory -Path (Split-Path -Parent $AgentsSkillDir)
Ensure-Directory -Path $configDir

if ($PSCmdlet.ShouldProcess($cmdWrapperPath, "Write CMD wrapper")) {
    Set-Content -LiteralPath $cmdWrapperPath -Value $cmdWrapper -Encoding ascii
}
if ($PSCmdlet.ShouldProcess($psWrapperPath, "Write PowerShell wrapper")) {
    Set-Content -LiteralPath $psWrapperPath -Value $psWrapper -Encoding utf8
}

Remove-TreeIfExists -Path $CodexSkillDir
Remove-TreeIfExists -Path $AgentsSkillDir
Remove-TreeIfExists -Path $legacyCodexSkillDir
Remove-TreeIfExists -Path $legacyAgentsSkillDir

if ($PSCmdlet.ShouldProcess($CodexSkillDir, "Install Codex skill")) {
    Copy-Item -Recurse -Force -Path $skillSource -Destination $CodexSkillDir
}
if ($PSCmdlet.ShouldProcess($AgentsSkillDir, "Install Agents skill")) {
    Copy-Item -Recurse -Force -Path $skillSource -Destination $AgentsSkillDir
}

if ($SyncEnv -and (Test-Path -LiteralPath $envSource) -and $PSCmdlet.ShouldProcess($envTarget, "Copy repo .env to frederica config")) {
    Copy-Item -Force -LiteralPath $envSource -Destination $envTarget
}

if ($AddToUserPath) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($userPath) {
        $parts = $userPath.Split(';', [System.StringSplitOptions]::RemoveEmptyEntries)
    }
    if ($parts -notcontains $binDir) {
        $updatedPath = @($binDir) + $parts
        if ($PSCmdlet.ShouldProcess("User PATH", "Add $binDir")) {
            [Environment]::SetEnvironmentVariable("Path", ($updatedPath -join ';'), "User")
        }
    }
}

Write-Host "Installed CMD wrapper to $cmdWrapperPath"
Write-Host "Installed PowerShell wrapper to $psWrapperPath"
Write-Host "Installed skill to $CodexSkillDir"
Write-Host "Installed skill to $AgentsSkillDir"
if ($SyncEnv) {
    if (Test-Path -LiteralPath $envSource) {
        Write-Host "Copied .env to $envTarget"
    } else {
        Write-Host "Skipped .env sync because $envSource was not found"
    }
}
if ($AddToUserPath) {
    Write-Host "Updated user PATH to include $binDir"
} else {
    Write-Host "Add $binDir to PATH if you want to run entrykit directly in new shells"
}
