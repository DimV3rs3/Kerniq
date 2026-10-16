# Remove Kerniq's venv and only the packages this install added.
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$wipe = $false
foreach ($arg in $args) {
    if ($arg -eq "--wipe-project" -or $arg -eq "wipe") { $wipe = $true }
}
$manifestPath = Join-Path $Root ".kerniq\install.json"
$manifest = $null
if (Test-Path $manifestPath) {
    $manifest = Get-Content -Raw -Path $manifestPath | ConvertFrom-Json
}
$py = $null
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if ($manifest -and $manifest.python -and (Test-Path -LiteralPath $manifest.python)) {
    $py = $manifest.python
} elseif (Test-Path $venvPy) {
    $py = $venvPy
} else {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notmatch "WindowsApps") { $py = $cmd.Source }
}
if (-not $py) {
    Write-Host "Python for this install was not found. Nothing was removed."
    exit 1
}

if (Test-Path -LiteralPath $py) {
    Write-Host "Resetting Kerniq settings..."
    $uninstallArgs = @("-m", "Kerniq", "uninstall", "-y")
    if ($wipe) { $uninstallArgs += "--wipe-project" }
    & $py @uninstallArgs
}

if ($wipe) {
    Write-Host "Project wipe was requested. Source, venv, and the private Python copy go with it."
    exit 0
}

if ($manifest -and $manifest.created_venv) {
    $venv = Join-Path $Root ".venv"
    if (Test-Path $venv) {
        Write-Host "Removing .venv and the libraries installed into it."
        Remove-Item -Recurse -Force $venv
    }
} elseif ($manifest) {
    Write-Host "Removing only packages Kerniq installed. Packages that were already here stay."
    $names = & $py (Join-Path $Root "scripts\env_manifest.py") remove-new $manifestPath
    $list = @($names | Where-Object { $_ -and $_.Trim() -ne "" })
    if ($list.Count -gt 0) {
        & $py -m pip uninstall -y @list
    }
}

if ($manifest -and $manifest.created_runtime) {
    $runtime = Join-Path $Root ".kerniq\runtime"
    if (Test-Path $runtime) {
        Write-Host "Removing the private Python copy Kerniq downloaded."
        Remove-Item -Recurse -Force $runtime
    }
}
Remove-Item -Force $manifestPath -ErrorAction SilentlyContinue
Remove-Item -Force (Join-Path $Root ".kerniq\kerniq.cmd") -ErrorAction SilentlyContinue
Remove-Item -Force (Join-Path $Root ".kerniq\kerniq") -ErrorAction SilentlyContinue
Write-Host "Done."
