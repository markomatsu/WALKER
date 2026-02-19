$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$rootBackend = (Resolve-Path (Join-Path $appRoot "..\walker")).Path
$appBackend = Join-Path $appRoot "backend"
$venvPy = Join-Path $rootBackend ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    Write-Error "Python venv not found at $venvPy. Create it first and install dependencies."
}

& $venvPy -m pip show pyinstaller *> $null
if ($LASTEXITCODE -ne 0) {
    & $venvPy -m pip install pyinstaller
}

$llvmBin = $env:LLVM_BIN
if (-not $llvmBin) {
    $defaultLlvm = "C:\Program Files\LLVM\bin"
    if (Test-Path $defaultLlvm) {
        $llvmBin = $defaultLlvm
    }
}

if (-not $llvmBin) {
    Write-Error "LLVM bin directory not found. Set LLVM_BIN or install LLVM."
}

$libclangDll = Join-Path $llvmBin "libclang.dll"
if (-not (Test-Path $libclangDll)) {
    Write-Error "libclang.dll not found at $libclangDll"
}

New-Item -ItemType Directory -Path $appBackend -Force | Out-Null
Remove-Item -Recurse -Force `
    (Join-Path $appBackend "walker-backend"), `
    (Join-Path $appBackend "build"), `
    (Join-Path $appBackend "walker-backend.spec") `
    -ErrorAction SilentlyContinue

$workPath = Join-Path $appBackend "build"
$scriptPath = Join-Path $rootBackend "test_engine.py"
$llvmGlob = Join-Path $llvmBin "*.dll"

& $venvPy -m PyInstaller `
  --name walker-backend `
  --clean `
  --distpath $appBackend `
  --workpath $workPath `
  --specpath $appBackend `
  --add-binary "$llvmGlob;." `
  $scriptPath

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Backend built at $(Join-Path $appBackend 'walker-backend')"
