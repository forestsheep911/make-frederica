[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$RepoRoot = "",
    [string]$PythonBin = "",
    [string]$BuildVenv = "",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$repoRootPath = [System.IO.Path]::GetFullPath($RepoRoot)
if (-not $BuildVenv) {
    $BuildVenv = Join-Path $repoRootPath ".venv-build"
}
$buildVenvPath = [System.IO.Path]::GetFullPath($BuildVenv)
$venvPython = Join-Path $buildVenvPath "Scripts\python.exe"
$pyInstaller = Join-Path $buildVenvPath "Scripts\pyinstaller.exe"
$distDir = Join-Path $repoRootPath "dist"
$workDir = Join-Path $repoRootPath "build\pyinstaller"
$specDir = Join-Path $repoRootPath "build"
$entryScript = Join-Path $repoRootPath "src\entrykit\cli.py"
$binaryPath = Join-Path $distDir "entrykit.exe"

function Resolve-PythonCommand {
    param([string]$Override)
    if ($Override) {
        return $Override
    }
    if ($env:ENTRYKIT_PYTHON_BIN) {
        return $env:ENTRYKIT_PYTHON_BIN
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return "$($py.Source) -3"
    }
    throw "Could not find Python 3.10+ for building entrykit. Set ENTRYKIT_PYTHON_BIN or pass -PythonBin."
}

function Invoke-ExternalCommand {
    param(
        [string]$Command,
        [string[]]$Arguments,
        [string]$Description
    )

    $display = @($Command) + $Arguments
    if ($PSCmdlet.ShouldProcess(($display -join " "), $Description)) {
        & $Command @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$Description failed with exit code $LASTEXITCODE"
        }
    }
}

if ($Clean) {
    if ((Test-Path -LiteralPath $buildVenvPath) -and $PSCmdlet.ShouldProcess($buildVenvPath, "Remove build virtualenv")) {
        Remove-Item -Recurse -Force -LiteralPath $buildVenvPath
    }
    if ((Test-Path -LiteralPath $workDir) -and $PSCmdlet.ShouldProcess($workDir, "Remove PyInstaller work directory")) {
        Remove-Item -Recurse -Force -LiteralPath $workDir
    }
}

$pythonCommand = Resolve-PythonCommand -Override $PythonBin
$pythonParts = $pythonCommand -split ' '
$pythonExe = $pythonParts[0]
$pythonArgs = @()
if ($pythonParts.Length -gt 1) {
    $pythonArgs = $pythonParts[1..($pythonParts.Length - 1)]
}

Invoke-ExternalCommand -Command $pythonExe -Arguments ($pythonArgs + @("-m", "venv", $buildVenvPath)) -Description "Create build virtualenv"
Invoke-ExternalCommand -Command $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip") -Description "Upgrade pip in build virtualenv"
Invoke-ExternalCommand -Command $venvPython -Arguments @("-m", "pip", "install", "-e", "$repoRootPath[build]") -Description "Install entrykit build dependencies"
Invoke-ExternalCommand `
    -Command $pyInstaller `
    -Arguments @(
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name", "entrykit",
        "--distpath", $distDir,
        "--workpath", $workDir,
        "--specpath", $specDir,
        "--paths", (Join-Path $repoRootPath "src"),
        $entryScript
    ) `
    -Description "Build entrykit.exe with PyInstaller"

Write-Host ""
Write-Host "Built binary: $binaryPath"
