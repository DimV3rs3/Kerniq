# Install into PATH Python when it exists. Otherwise create .venv and install there.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Meta = Join-Path $Root ".kerniq"
New-Item -ItemType Directory -Force -Path $Meta | Out-Null

function Test-Py311([string]$Exe) {
    if (-not $Exe) { return $false }
    if ($Exe -match "WindowsApps") { return $false }
    $isCmd = $Exe -notmatch '[\\/]'
    if (-not $isCmd -and -not (Test-Path -LiteralPath $Exe)) { return $false }
    try {
        $out = & $Exe -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Find-PythonOnPath {
    $candidates = @()
    foreach ($name in @("python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -notmatch "WindowsApps") { $candidates += $cmd.Source }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($ver in @("3.14", "3.13", "3.12", "3.11")) {
            try {
                $exe = & py "-$ver" -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $exe) { $candidates += $exe.Trim() }
            } catch {}
        }
    }
    foreach ($exe in $candidates) {
        if ($exe -match "\\\.venv\\" -or $exe -match "\\\.kerniq\\") { continue }
        if (Test-Py311 $exe) { return $exe }
    }
    return $null
}

function Find-PythonOffPath {
    $candidates = @()
    $candidates += (Join-Path $Root ".kerniq\runtime\python\python.exe")
    $local = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path $local) {
        $candidates += Get-ChildItem -Path $local -Filter python.exe -Recurse -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty FullName
    }
    foreach ($exe in $candidates) {
        if ($exe -match "\\\.venv\\") { continue }
        if (Test-Py311 $exe) { return $exe }
    }
    return $null
}

function Get-Triple {
    if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { return "aarch64-pc-windows-msvc" }
    return "x86_64-pc-windows-msvc"
}

function Install-PrivatePython {
    $triple = Get-Triple
    Write-Host "Python 3.11+ was not found. Downloading a private copy into .kerniq\runtime ..."
    $headers = @{ "User-Agent" = "Kerniq-installer" }
    $api = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"
    $asset = $api.assets | Where-Object {
        $_.name -match "^cpython-3\.(1[1-4])\..+-$([regex]::Escape($triple))-install_only\.tar\.gz$"
    } | Sort-Object name -Descending | Select-Object -First 1
    if (-not $asset) { throw "Could not find a Python build for $triple" }
    $archive = Join-Path $Meta "python.tar.gz"
    Write-Host "Downloading $($asset.name)"
    curl.exe -L --fail --retry 3 -A "Kerniq-installer" -o $archive $asset.browser_download_url
    if ($LASTEXITCODE -ne 0) { throw "Python download failed" }
    $dest = Join-Path $Meta "runtime"
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    tar.exe -xzf $archive -C $dest
    Remove-Item -Force $archive
    $exe = Join-Path $dest "python\python.exe"
    if (-not (Test-Path $exe)) { throw "Downloaded Python has no python.exe" }
    return $exe
}

$createdRuntime = $false
$createdVenv = $false
$target = Find-PythonOnPath
if ($target) {
    Write-Host "Python is on PATH. Installing into that interpreter. No venv."
    Write-Host "Using $target"
} else {
    Write-Host "Python is not on PATH. Kerniq will use a project .venv."
    $base = Find-PythonOffPath
    if (-not $base) {
        $base = Install-PrivatePython
        $createdRuntime = $true
    }
    Write-Host "Using $base to create the venv"
    $venvDir = Join-Path $Root ".venv"
    $target = Join-Path $venvDir "Scripts\python.exe"
    if (-not (Test-Py311 $target)) {
        if (Test-Path $venvDir) { Remove-Item -Recurse -Force $venvDir }
        Write-Host "Creating .venv"
        & $base -m venv $venvDir
        if ($LASTEXITCODE -ne 0) { throw "python -m venv failed" }
        $createdVenv = $true
    }
    if (-not (Test-Path $target)) { throw "venv python is missing" }
}

& $target -m pip --version 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    & $target -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) { throw "pip is missing and ensurepip failed" }
}

$beforeFile = Join-Path $Meta "before.json"
$beforeJson = & $target (Join-Path $Root "scripts\env_manifest.py") freeze $target
if ($LASTEXITCODE -ne 0) { throw "could not read installed packages" }
[System.IO.File]::WriteAllText($beforeFile, ($beforeJson | Out-String).Trim())

Write-Host "Installing with python -m pip. Packages already present are left for uninstall to keep."
& $target -m pip install -e ".[dev,mcp]"
if ($LASTEXITCODE -ne 0) {
    if (-not $createdVenv) {
        Write-Host "Retrying with --break-system-packages"
        & $target -m pip install --break-system-packages -e ".[dev,mcp]"
    }
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
}

Write-Host "Scanning plugins and tool packs for Python libraries..."
& $target -c "import pathlib,sys; from Kerniq.sandbox.deps import install_product_tree; install_product_tree(pathlib.Path(sys.argv[1]))" $Root
if ($LASTEXITCODE -ne 0) {
    Write-Host "Library scan failed. Kerniq itself is installed; a plugin can still install its own libraries on load."
}

$flagVenv = $(if ($createdVenv) { "1" } else { "0" })
$flagRuntime = $(if ($createdRuntime) { "1" } else { "0" })
& $target (Join-Path $Root "scripts\env_manifest.py") commit (Join-Path $Meta "install.json") $target $flagVenv $flagRuntime $beforeFile
if ($LASTEXITCODE -ne 0) { throw "could not write install manifest" }
Remove-Item -Force $beforeFile -ErrorAction SilentlyContinue

$launcher = Join-Path $Meta "kerniq.cmd"
@(
    "@echo off",
    "`"$target`" -m Kerniq %*"
) | Set-Content -Path $launcher -Encoding ascii

Write-Host ""
& $target -m Kerniq --version
Write-Host "Done."
if ($createdVenv) {
    Write-Host "UI:  $target -m Kerniq plugins ui"
    Write-Host "Or:  $launcher plugins ui"
} else {
    Write-Host "UI:  python -m Kerniq plugins ui"
    Write-Host "Or:  $launcher plugins ui"
}
