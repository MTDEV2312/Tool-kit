# Build script for Windows using PyInstaller
$ErrorActionPreference = "Stop"

Write-Host "Verifying PyInstaller installation..." -ForegroundColor Cyan
if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: PyInstaller is not installed." -ForegroundColor Red
    Write-Host "Please run 'pip install -r requirements.txt' or 'pip install .[dev]' first." -ForegroundColor Yellow
    exit 1
}

Write-Host "Managing version bump..." -ForegroundColor Cyan
python scripts/bump_version.py

$TEMP_FILE = ".version_temp"
if (Test-Path $TEMP_FILE) {
    $VERSION = Get-Content $TEMP_FILE -Raw
    $VERSION = $VERSION.Trim()
    Remove-Item $TEMP_FILE
} else {
    $VERSION = python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"
}

Write-Host "Generating version info..." -ForegroundColor Cyan
python scripts/generate_version_info.py

$NAME = "driver-backup-v$VERSION"

Write-Host "Packaging $NAME executable..." -ForegroundColor Cyan
pyinstaller --onefile --name $NAME --version-file=file_version_info.txt --clean src/driver_backup/cli.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Build Succeeded! The binary is located at: dist\$NAME.exe" -ForegroundColor Green
} else {
    Write-Host "ERROR: PyInstaller build failed." -ForegroundColor Red
    exit 1
}
