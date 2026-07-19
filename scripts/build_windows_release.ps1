param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$SpecFile = Join-Path $ProjectRoot "packaging\AI_Notion.spec"
$InnoScript = Join-Path $ProjectRoot "packaging\AI_Notion_Setup.iss"
$BuildDir = Join-Path $ProjectRoot "build"
$DistDir = Join-Path $ProjectRoot "dist"
$ReleaseDir = Join-Path $ProjectRoot "release"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Project virtual environment not found: $Python"
}

if (-not $Version) {
    $VersionOutput = & $Python -c "from src.version import __version__; print(__version__)"
    if ($LASTEXITCODE -ne 0) { throw "Unable to read the application version." }
    $Version = $VersionOutput.Trim()
}

foreach ($Target in @($BuildDir, $DistDir, $ReleaseDir)) {
    $FullTarget = [System.IO.Path]::GetFullPath($Target)
    $FullRoot = [System.IO.Path]::GetFullPath($ProjectRoot) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $FullTarget.StartsWith($FullRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a path outside the project: $FullTarget"
    }
    if (Test-Path -LiteralPath $FullTarget) {
        Remove-Item -LiteralPath $FullTarget -Recurse -Force
    }
}

New-Item -ItemType Directory -Path $ReleaseDir | Out-Null

& $Python -c "import PyInstaller"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed. Run: .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt"
}

Push-Location $ProjectRoot
try {
    & $Python -m PyInstaller --noconfirm --clean $SpecFile
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
}
finally {
    Pop-Location
}

$InnoCandidates = @(
    (Get-Command iscc.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) }

$Iscc = $InnoCandidates | Select-Object -First 1
if (-not $Iscc) {
    throw "Inno Setup 6 was not found. Install it and run this script again."
}

& $Iscc "/DMyAppVersion=$Version" "/DSourceDir=$DistDir\AI_Notion_Note_Organizer" "/DOutputDir=$ReleaseDir" $InnoScript
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed to create the installer." }

$Installer = Join-Path $ReleaseDir "AI_Notion_Note_Organizer_Setup.exe"
if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
    throw "Generated installer not found: $Installer"
}

Write-Host ""
Write-Host "Build complete: $Installer" -ForegroundColor Green
Write-Host "One-click download URL after publishing a GitHub Release:" -ForegroundColor Cyan
Write-Host "https://github.com/Allen1208tw/AI-notion-note-organizer/releases/latest/download/AI_Notion_Note_Organizer_Setup.exe"
