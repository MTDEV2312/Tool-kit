# Driver Backup TUI & CLI Utility

A high-performance terminal user interface (TUI) and command-line interface (CLI) tool designed to export and backup Windows driver packages asynchronously using DISM and PnPUtil.

Designed with platform abstractions, it includes a robust Mock service enabling developers to run, test, and iterate on macOS or Linux systems.

## Features

- **Dual Modes**: Launches an interactive, premium Textual TUI when run without arguments, or handles scriptable CLI commands.
- **Asynchronous Execution**: Executes DISM/PnPUtil in background subprocesses, keeping the UI fully responsive (supporting cancelling/aborting).
- **Real-Time Parsing**: Employs precise regex parsers to translate live subprocess stdout lines into percentages and item counts.
- **Dynamic Elevation**: Automatically checks for admin permissions on Windows and requests UAC elevation if needed.
- **Mock Fallback**: Runs simulated exports for local UI design and development on macOS/Linux (or when forced via Settings/CLI options).

## Quick Start

### Installation

Install in editable mode with development dependencies:

```bash
pip install -e ".[dev]"
```

Alternatively, install only core dependencies:

```bash
pip install -r requirements.txt
```

### Running the TUI

Launch the interactive Textual interface:

```bash
driver-backup
```

*(Note: Running this command on Windows will check for admin elevation and request it via a UAC pop-up if running from a non-privileged terminal).*

### Command Line Interface (CLI)

Run specific subcommands:

```bash
# Export drivers immediately using DISM
driver-backup export --destination C:\MyDrivers --method dism

# Force mock simulation (runs on macOS/Linux/Windows without elevation)
driver-backup export --destination ./MockDrivers --mock

# List installed OEM driver packages
driver-backup list

# Get/set configuration items
driver-backup config
driver-backup config backup_dir
driver-backup config backup_method pnputil
driver-backup config force_mock true

# View version
driver-backup version
```

## Configuration

Settings are saved in a JSON configuration file located at `~/.driver_backup/config.json`.
- `backup_dir`: Target directory for exported drivers.
- `backup_method`: Backup engine (`dism` or `pnputil`).
- `log_level`: Logger verbosity (`INFO` or `DEBUG`).
- `force_mock`: Boolean flag to run mock services instead of real system calls.

## Development & Quality Assurance

Run linter, type checks, and test suite:

```bash
# Code style audit
ruff check .

# Static type checking
mypy src

# Run test suite
pytest
```

## Compilation (Packaging)

Build a standalone, single-file executable using PyInstaller:

**On Windows (PowerShell):**
```powershell
./build.ps1
```

**On Linux / macOS:**
```bash
chmod +x build.sh
./build.sh
```

The compiled binaries will be outputted to the `dist/` directory.
