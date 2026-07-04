# Exploration: Driver Backup Tool Architecture

## Current State
The project has been initialized with a basic `pyproject.toml`, a minimal `README.md`, and a simple CLI stub using Typer in `src/driver_backup/cli.py` which only prints a message. There is no TUI implementation, backup service, or platform-specific logic yet.

## Affected Areas
- `src/driver_backup/cli.py` — Needs to act as the central entry point, delegating to either the Textual TUI app or executing specific CLI commands.
- `src/driver_backup/app.py` — New file to implement the main Textual App class that orchestrates the overall user interface.
- `src/driver_backup/ui/` — New subdirectory containing UI screens and widgets:
  - `src/driver_backup/ui/home.py` — Home screen with option picker and dashboard.
  - `src/driver_backup/ui/backup.py` — Backup progress screen capturing live log/process output.
  - `src/driver_backup/ui/settings.py` — Settings page for adjusting configurations.
- `src/driver_backup/services/` — New subdirectory to handle driver enumeration and backup execution:
  - `src/driver_backup/services/base.py` — Base protocol/class for driver services.
  - `src/driver_backup/services/dism.py` — DISM-based driver exporter.
  - `src/driver_backup/services/pnputil.py` — PnPUtil-based driver exporter.
  - `src/driver_backup/services/backup.py` — Combined coordinator for the backup execution.
- `src/driver_backup/utils/` — New subdirectory containing helpers:
  - `src/driver_backup/utils/config.py` — JSON config manager for user preferences.
  - `src/driver_backup/utils/permissions.py` — Admin privilege detection and elevation triggers.
  - `src/driver_backup/utils/logger.py` — File-based logging utility.
- `pyproject.toml` — May need dependencies or script entrypoints verified as implementation proceeds.

## Approaches

### 1. Unified Entrypoint with Lazy Importing
Bridge Typer CLI and Textual TUI by using Typer for command parsing. The default callback (when no subcommands are supplied) runs the Textual TUI app. Textual UI modules are imported lazily inside the Typer callback to avoid loading large packages (Textual, Rich) during fast, CLI-only execution.
- **Pros**:
  - Very fast startup time for lightweight CLI commands (like `version` or `config`).
  - Single, intuitive executable entrypoint.
  - Clean separation of CLI parsing and UI drawing.
- **Cons**:
  - Requires careful handling of command arguments so they don't conflict with TUI startup.
- **Effort**: Low

### 2. Async Subprocess and Parsing for Progress
Run `DISM` or `PnPUtil` via `asyncio.create_subprocess_exec`. Use `asyncio.subprocess.PIPE` to redirect stdout/stderr. Read stdout line-by-line asynchronously to parse percentage outputs (from DISM) or driver package names (from PnPUtil) and feed updates to Textual's reactive components.
- **Pros**:
  - Non-blocking execution preserves Textual UI responsiveness (e.g. Cancel button, screen redraws).
  - Accurate progress representation for the user.
- **Cons**:
  - DISM and PnPUtil output formats can vary across Windows builds, necessitating robust regex/parsing.
  - PnPUtil doesn't output percentages, requiring an initial estimation step or a count-based progress approach.
- **Effort**: Medium

### 3. Elevated Privilege Mitigation
Check administrative status on startup using `ctypes.windll.shell32.IsUserAnAdmin()`. If running without admin rights, display an explicit "Requires Elevation" screen in the TUI, or automatically prompt for UAC elevation using `ShellExecuteW` with the `runas` verb to relaunch the process.
- **Pros**:
  - Prevents silent backup failures due to permission denied errors.
  - Seamless user experience if UAC is accepted.
- **Cons**:
  - Windows UAC prompt interrupts flow; needs graceful cancellation handling.
  - Mock drivers must be used on non-Windows platforms (macOS/Linux) where Windows-specific ctypes modules are missing.
- **Effort**: Low

## Recommendation
Implement a combined architecture using:
1. **Lazy-loaded Textual TUI** in Typer CLI callback to bridge TUI/CLI cleanly.
2. **Async subprocess spawning (`asyncio.create_subprocess_exec`)** with a custom parser layer to capture DISM/PnPUtil stdout. Since PnPUtil doesn't provide percentages but DISM does, we should support both: use DISM by default with regex percentage parsing, and fallback to PnPUtil with item-count progress where DISM is unavailable.
3. **Platform abstraction**: Define a `DriverBackupService` protocol, implementing a `WindowsDriverService` (handling ctypes checks, process execution) and a `MockDriverService` (yielding mock progress updates) so developers can run and test the UI on Linux or macOS.

## Risks
- **Command Path and Localization**: `DISM` or `PnPUtil` output might be localized depending on the Windows system language. Regex parsing must be resilient to translation or look for invariant tokens.
- **PyInstaller Bundling**: Compiling to a single EXE with PyInstaller requires correctly resolving assets (like `config.json` templates or Textual CSS styles) and ensuring that running the compiled EXE with subprocesses doesn't create recursive infinite loops.
- **Elevation Loop**: UAC prompt handling must check carefully to avoid infinite elevation loops.

## Ready for Proposal
Yes
