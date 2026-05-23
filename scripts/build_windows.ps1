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
$ReadmePath = Join-Path $ProjectRoot "README.md"
$ChineseReadmePath = Join-Path $ProjectRoot "README.zh.md"
$DocsPath = Join-Path $ProjectRoot "docs"
$IconPngPath = Join-Path $ProjectRoot "src\ui\assets\icons\mindtask-icon.png"
$IconIcoPath = Join-Path $ProjectRoot "src\ui\assets\icons\mindtask-icon.ico"
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
if (-not (Test-Path -LiteralPath $ReadmePath)) {
    throw "README was not found: $ReadmePath"
}
if (-not (Test-Path -LiteralPath $ChineseReadmePath)) {
    throw "Chinese README was not found: $ChineseReadmePath"
}
if (-not (Test-Path -LiteralPath $DocsPath)) {
    throw "Docs directory was not found: $DocsPath"
}
if (-not (Test-Path -LiteralPath $IconPngPath)) {
    throw "Application icon PNG was not found: $IconPngPath"
}
if (-not (Test-Path -LiteralPath $IconIcoPath)) {
    throw "Application icon ICO was not found: $IconIcoPath"
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
        --icon $IconIcoPath `
        --specpath $BuildRoot `
        --add-data "$TemplatePath;config" `
        --add-data "$SchemaPath;sql" `
        --add-data "$IconPngPath;assets/icons" `
        --collect-all qtawesome `
        --exclude-module PySide6.QtQml `
        --exclude-module PySide6.QtQuick `
        --exclude-module PySide6.QtQuickWidgets `
        $EntryPoint
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed."
    }

    $AppDir = Join-Path $DistRoot $AppName
    $ExePath = Join-Path $AppDir "$AppName.exe"
    if (-not (Test-Path -LiteralPath $ExePath)) {
        throw "Build completed but executable was not found: $ExePath"
    }

    Copy-Item -LiteralPath $ReadmePath -Destination (Join-Path $AppDir "README.md") -Force
    Copy-Item -LiteralPath $ChineseReadmePath -Destination (Join-Path $AppDir "README.zh.md") -Force
    $AppDocsPath = Join-Path $AppDir "docs"
    if (Test-Path -LiteralPath $AppDocsPath) {
        Remove-Item -LiteralPath $AppDocsPath -Recurse -Force
    }
    Copy-Item -LiteralPath $DocsPath -Destination $AppDocsPath -Recurse -Force

    $TempZipPath = Join-Path $DistRoot "$AppName-$Version-windows-x64-$([guid]::NewGuid().ToString('N')).tmp.zip"
    Compress-Archive -LiteralPath $AppDir -DestinationPath $TempZipPath
    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    Move-Item -LiteralPath $TempZipPath -Destination $ZipPath -Force

    Write-Host "Built: $ExePath"
    Write-Host "Zip:   $ZipPath"
}
finally {
    Pop-Location
}
