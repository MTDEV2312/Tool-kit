# Proposal: Driver Backup Tool Base Implementation

## Intent

Provide a lightweight Windows driver backup tool that runs both as a scriptable Command Line Interface (CLI) and an interactive Textual User Interface (TUI), abstracting Windows-specific tools (DISM/PnPUtil) and allowing mock-based testing on non-Windows platforms.

## Scope

### In Scope
- Core Windows driver backup execution service running DISM or PnPUtil asynchronously.
- Basic JSON configuration manager, elevation/admin detection check, and log file utility.
- Typer-based CLI command routing.
- Textual-based interactive TUI dashboard (home screen, config editor, backup progress monitor).
- Platform abstraction allowing a mock service to run and test TUI on Linux/macOS.

### Out of Scope
- Creating driver installation/restore functionality (only backup/export is supported).
- Cloud storage integration or backup compression (zip, 7z).

## Capabilities

### New Capabilities
- `driver-backup-core`: Core functionality to run DISM/PnPUtil commands, capture output, and export Windows drivers.
- `driver-backup-cli`: Command line interface with Typer commands (export, list, config, version).
- `driver-backup-tui`: Textual Text User Interface for configuring, executing, and monitoring backups.

### Modified Capabilities
None

## Approach

1. **CLI / TUI Bridging**: Build a Typer CLI entrypoint. When run without arguments, it lazily imports and launches the Textual TUI app to optimize startup speed.
2. **Subprocess Management**: Execute DISM/PnPUtil asynchronously via `asyncio.create_subprocess_exec` to capture stdout line-by-line.
3. **Platform Abstraction**: Implement `DriverBackupService` protocol with `WindowsDriverService` (real commands via DISM/PnPUtil) and `MockDriverService` (simulated backup updates for cross-platform local development).
4. **Elevation**: Implement admin checks using `ctypes.windll.shell32.IsUserAnAdmin()`. Show a permission error screen if run without privileges, prompting elevation via `ShellExecuteW(runas)`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/driver_backup/cli.py` | Modified | Typer central entry point and subcommand router. |
| `src/driver_backup/app.py` | New | Main Textual TUI app coordinator. |
| `src/driver_backup/ui/` | New | UI screens: Home, Settings, and Backup Progress. |
| `src/driver_backup/services/` | New | Driver backup protocols, Windows and Mock implementations. |
| `src/driver_backup/utils/` | New | Helpers for configuration, logger, and permission elevation. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Localized output from DISM/PnPUtil breaks regex progress parsing | Med | Design regexes to match invariant tokens or structure, and fallback gracefully to simple item-count progress. |
| Infinite UAC elevation loop if admin check fails | Low | Track state flag or cmd arguments to prevent re-elevating repeatedly. |
| Non-Windows developers cannot test TUI | Low | Provide a robust mock driver service selected automatically on non-Windows OS. |

## Rollback Plan

Revert all newly added files under `src/driver_backup/` and restore `src/driver_backup/cli.py` to its initial Typer stub version using `git checkout`.

## Dependencies

- `typer` (CLI parsing)
- `textual` (TUI dashboard and widgets)
- Windows OS (for live backups; mock runs on macOS/Linux)

## Success Criteria

- [ ] Command line stub correctly redirects to Textual TUI when run without options.
- [ ] real/mock driver backup runs asynchronously without locking the UI.
- [ ] Settings configuration saves and persists successfully to JSON.
- [ ] Admin privileges are detected on startup and elevation is requested if needed.
