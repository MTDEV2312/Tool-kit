#!/bin/bash
set -e

echo "Verifying PyInstaller installation..."
if ! command -v pyinstaller &> /dev/null; then
    echo "ERROR: PyInstaller is not installed."
    echo "Please run 'pip install -r requirements.txt' or 'pip install .[dev]' first."
    exit 1
fi

echo "Managing version bump..."
python3 scripts/bump_version.py

TEMP_FILE=".version_temp"
if [ -f "$TEMP_FILE" ]; then
    VERSION=$(cat "$TEMP_FILE")
    rm -f "$TEMP_FILE"
else
    VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
fi

NAME="driver-backup-v$VERSION"

echo "Packaging $NAME executable..."
pyinstaller --onefile --name "$NAME" --clean src/driver_backup/cli.py

echo "Build Succeeded! The binary is located at: dist/$NAME"
