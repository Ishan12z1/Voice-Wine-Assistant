[CmdletBinding()]
param(
    [string]$RawPath = "data/raw/Assignment wine dataset - Sheet1.csv",
    [string]$CleanPath = "data/processed/wines_clean.csv",
    [string]$EnrichedPath = "data/processed/wines_enriched.csv",
    [string]$PythonPath = "",
    [switch]$UpdateEnv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Resolve-ProjectPath {
    param([Parameter(Mandatory = $true)][string]$PathValue)

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $PathValue))
}

function Convert-ToEnvPath {
    param([Parameter(Mandatory = $true)][string]$AbsolutePath)

    $repoUri = [System.Uri]::new(($RepoRoot.TrimEnd('\') + '\'))
    $fileUri = [System.Uri]::new($AbsolutePath)

    if ($repoUri.IsBaseOf($fileUri)) {
        $relativeUri = $repoUri.MakeRelativeUri($fileUri).ToString()
        return [System.Uri]::UnescapeDataString($relativeUri).Replace('\', '/')
    }

    return $AbsolutePath
}

$resolvedRawPath = Resolve-ProjectPath $RawPath
$resolvedCleanPath = Resolve-ProjectPath $CleanPath
$resolvedEnrichedPath = Resolve-ProjectPath $EnrichedPath

if (-not (Test-Path $resolvedRawPath)) {
    throw "Raw dataset not found at: $resolvedRawPath"
}

$defaultVenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if ($PythonPath) {
    $pythonExe = Resolve-ProjectPath $PythonPath
} elseif (Test-Path $defaultVenvPython) {
    $pythonExe = $defaultVenvPython
} else {
    $pythonExe = "python"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $resolvedCleanPath) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $resolvedEnrichedPath) | Out-Null

Push-Location $RepoRoot
try {
    & $pythonExe -m backend.services.loader `
        --raw-path $resolvedRawPath `
        --clean-path $resolvedCleanPath `
        --enriched-path $resolvedEnrichedPath

    if ($LASTEXITCODE -ne 0) {
        throw "Dataset refresh failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

$defaultRuntimeDataset = Resolve-ProjectPath "data/processed/wines_enriched.csv"
$envFilePath = Join-Path $RepoRoot ".env"
$envDatasetValue = Convert-ToEnvPath $resolvedEnrichedPath

if ($UpdateEnv) {
    $envLine = ('WINE_DATASET_PATH="{0}"' -f $envDatasetValue)
    $existingLines = @()

    if (Test-Path $envFilePath) {
        $existingLines = Get-Content $envFilePath
    }

    $updated = $false
    $rewrittenLines = foreach ($line in $existingLines) {
        if ($line -match '^\s*WINE_DATASET_PATH\s*=') {
            $updated = $true
            $envLine
        } else {
            $line
        }
    }

    if (-not $updated) {
        $rewrittenLines += $envLine
    }

    Set-Content -Path $envFilePath -Value $rewrittenLines -Encoding utf8
}

Write-Host ""
Write-Host "Dataset refresh complete."
Write-Host "Raw dataset:      $resolvedRawPath"
Write-Host "Clean dataset:    $resolvedCleanPath"
Write-Host "Enriched dataset: $resolvedEnrichedPath"
Write-Host "Metadata will refresh automatically from the active enriched dataset on the next API request."

if ($UpdateEnv) {
    Write-Host ".env updated:     $envFilePath"
    Write-Host ('WINE_DATASET_PATH="{0}"' -f $envDatasetValue)
    Write-Host "Restart the backend if it is already running so it picks up the new .env value."
} elseif ($resolvedEnrichedPath -ne $defaultRuntimeDataset) {
    Write-Host ""
    Write-Host "To make the app use this enriched dataset, update .env to:"
    Write-Host ('WINE_DATASET_PATH="{0}"' -f $envDatasetValue)
    Write-Host "Then restart the backend if it is already running."
}
