param(
    [string]$Python = "C:\Users\52524\AppData\Local\Programs\Python\Python310\python.exe",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$DistRoot = Join-Path $ProjectRoot "dist"
$BuildRoot = Join-Path $ProjectRoot "build"
$AppName = "MindTask"
$EntryPoint = Join-Path $ProjectRoot "MindTask_ui.py"
$TemplatePath = Join-Path $ProjectRoot "config\mindtask.ini.template"
$SchemaPath = Join-Path $ProjectRoot "sql\mindtask_db_schema.sql"
$Version = & $Python -c "import src; print(src.__version__)"
$ZipPath = Join-Path $DistRoot "$AppName-$Version-windows-x64.zip"
$PipIndexArgs = @(
    "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
    "--trusted-host", "pypi.tuna.tsinghua.edu.cn"
)

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python was not found: $Python"
}
if (-not (Test-Path -LiteralPath $EntryPoint)) {
    throw "Entry point was not found: $EntryPoint"
}
if (-not (Test-Path -LiteralPath $TemplatePath)) {
    throw "Config template was not found: $TemplatePath"
}
if (-not (Test-Path -LiteralPath $SchemaPath)) {
    throw "Schema file was not found: $SchemaPath"
}

Push-Location $ProjectRoot
try {
    if (-not $SkipInstall) {
        & $Python -m pip install @PipIndexArgs --upgrade pip
        if ($LASTEXITCODE -ne 0) {
            throw "pip failed while upgrading pip."
        }
        & $Python -m pip install @PipIndexArgs --upgrade ".[ui]" pyinstaller
        if ($LASTEXITCODE -ne 0) {
            throw "pip failed while installing build dependencies."
        }
    }

    if (Test-Path -LiteralPath $BuildRoot) {
        Remove-Item -LiteralPath $BuildRoot -Recurse -Force
    }
    if (Test-Path -LiteralPath (Join-Path $DistRoot $AppName)) {
        Remove-Item -LiteralPath (Join-Path $DistRoot $AppName) -Recurse -Force
    }
    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }

    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --windowed `
        --name $AppName `
        --specpath $BuildRoot `
        --add-data "$TemplatePath;config" `
        --add-data "$SchemaPath;sql" `
        --collect-all PySide6 `
        --collect-all qtawesome `
        $EntryPoint
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed."
    }

    $AppDir = Join-Path $DistRoot $AppName
    $ExePath = Join-Path $AppDir "$AppName.exe"
    if (-not (Test-Path -LiteralPath $ExePath)) {
        throw "Build completed but executable was not found: $ExePath"
    }

    Compress-Archive -LiteralPath $AppDir -DestinationPath $ZipPath -Force

    Write-Host "Built: $ExePath"
    Write-Host "Zip:   $ZipPath"
}
finally {
    Pop-Location
}
