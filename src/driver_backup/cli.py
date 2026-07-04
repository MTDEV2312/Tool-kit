import asyncio
import platform
import sys
from typing import Any

import typer
from rich.console import Console

from driver_backup.utils.config import ConfigManager
from driver_backup.utils.logger import logger, setup_logger
from driver_backup.utils.permissions import elevate_privileges, is_admin

app = typer.Typer(
    help="Driver Backup and Restore TUI/CLI Utility",
    no_args_is_help=False,
)
console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Launch the Textual TUI when run without commands, otherwise route CLI commands."""
    if ctx.invoked_subcommand is not None:
        return

    # Set up config and loggers before running the TUI app
    config = ConfigManager()
    setup_logger(config.log_level, enable_console=False)

    console.print("[bold green]Starting Driver Backup TUI...[/bold green]")

    # Lazy-load Textual App to speed up CLI startups
    from driver_backup.app import DriverBackupApp

    app_instance = DriverBackupApp()
    app_instance.run()


@app.command()
def export(
    destination: str | None = typer.Option(
        None, "--destination", "-d", help="Directory path to save the driver export."
    ),
    method: str | None = typer.Option(
        None, "--method", "-m", help="Backup engine: dism or pnputil."
    ),
    mock: bool = typer.Option(
        False, "--mock", help="Force simulated mock driver export."
    ),
    zip_backup: bool | None = typer.Option(
        None,
        "--zip/--no-zip",
        show_default=False,
        help="Compress the backup folder into a ZIP file.",
    ),
    clean: bool | None = typer.Option(
        None,
        "--clean/--no-clean",
        show_default=False,
        help="Clean/remove raw backup folder after zipping.",
    ),
    third_party_only: bool = typer.Option(
        False,
        "--third-party-only",
        help="Backup third-party drivers only.",
    ),
    all_drivers: bool = typer.Option(
        False,
        "--all-drivers",
        help="Backup all drivers (not just third-party).",
    ),
) -> None:
    """Export Windows driver packages directly from the command line."""
    config = ConfigManager()
    setup_logger(config.log_level, enable_console=True)

    if third_party_only and all_drivers:
        console.print(
            "[bold red]ERROR: Options --third-party-only and --all-drivers are mutually exclusive.[/bold red]"
        )
        sys.exit(1)

    dest = destination or config.backup_dir
    meth = method or config.backup_method

    compress_to_zip = zip_backup if zip_backup is not None else config.compress_to_zip
    clean_raw_files = clean if clean is not None else config.clean_raw_files

    if third_party_only:
        final_third_party = True
    elif all_drivers:
        final_third_party = False
    else:
        final_third_party = config.third_party_only

    logger.info(
        f"CLI export requested. Destination: {dest}, Method: {meth}, Mock: {mock}, "
        f"Zip: {compress_to_zip}, Clean: {clean_raw_files}, ThirdPartyOnly: {final_third_party}"
    )

    # Privilege check
    if not mock and not is_admin():
        console.print(
            "[bold red]ERROR: Administrator privileges are required to export drivers.[/bold red]"
        )
        console.print("Attempting to elevate privileges via UAC...")
        elevate_privileges()
        return

    from driver_backup.services.backup import BackupCoordinator, get_backup_service

    inner_service = get_backup_service(
        method=meth, force_mock=mock, third_party_only=final_third_party
    )
    service = BackupCoordinator(
        inner_service=inner_service,
        compress_to_zip=compress_to_zip,
        clean_raw_files=clean_raw_files,
    )

    async def run_backup() -> None:
        console.print(f"[yellow]Exporting drivers to: {dest}[/yellow]")
        async for progress in service.backup(dest):
            if progress.status in ("running", "zipping"):
                console.print(
                    f"[blue]Progress: {progress.percentage:.1f}% - {progress.current_item}[/blue]"
                )
            elif progress.status == "completed":
                console.print(f"[bold green]{progress.log_line}[/bold green]")
            elif progress.status == "failed":
                console.print(f"[bold red]{progress.log_line}[/bold red]")
                sys.exit(1)
            elif progress.status == "cancelled":
                console.print("[bold yellow]Backup cancelled by user.[/bold yellow]")
                sys.exit(1)

    try:
        asyncio.run(run_backup())
    except KeyboardInterrupt:
        console.print("[bold yellow]\nBackup interrupted.[/bold yellow]")
        sys.exit(1)


@app.command()
def restore(
    source: str | None = typer.Option(
        None,
        "--source",
        "-s",
        help="Directory path to load drivers from for restoration.",
    ),
    method: str | None = typer.Option(
        None, "--method", "-m", help="Restore engine: dism or pnputil."
    ),
    mock: bool = typer.Option(
        False, "--mock", help="Force simulated mock driver restore."
    ),
) -> None:
    """Restore Windows driver packages directly from the command line."""
    config = ConfigManager()
    setup_logger(config.log_level, enable_console=True)

    src = source or config.backup_dir
    meth = method or config.backup_method

    logger.info(f"CLI restore requested. Source: {src}, Method: {meth}, Mock: {mock}")

    # Privilege check
    if not mock and not is_admin():
        console.print(
            "[bold red]ERROR: Administrator privileges are required to restore drivers.[/bold red]"
        )
        console.print("Attempting to elevate privileges via UAC...")
        elevate_privileges()
        return

    from driver_backup.services.backup import BackupCoordinator, get_backup_service

    inner_service = get_backup_service(method=meth, force_mock=mock)
    service = BackupCoordinator(inner_service)

    async def run_restore() -> None:
        console.print(f"[yellow]Restoring drivers from: {src}[/yellow]")
        async for progress in service.restore(src):
            if progress.status in ("running", "extracting"):
                console.print(
                    f"[blue]Progress: {progress.percentage:.1f}% - {progress.current_item}[/blue]"
                )
            elif progress.status == "completed":
                console.print(f"[bold green]{progress.log_line}[/bold green]")
            elif progress.status == "failed":
                console.print(f"[bold red]{progress.log_line}[/bold red]")
                sys.exit(1)
            elif progress.status == "cancelled":
                console.print("[bold yellow]Restore cancelled by user.[/bold yellow]")
                sys.exit(1)

    try:
        asyncio.run(run_restore())
    except KeyboardInterrupt:
        console.print("[bold yellow]\nRestore interrupted.[/bold yellow]")
        sys.exit(1)


@app.command(name="list")
def list_drivers(
    mock: bool = typer.Option(False, "--mock", help="Force mock listing."),
) -> None:
    """List OEM driver packages currently installed on the host system."""
    if not mock and not is_admin():
        console.print(
            "[bold red]ERROR: Administrator privileges are required to list drivers.[/bold red]"
        )
        return

    console.print("[bold]Checking driver packages...[/bold]")
    if mock or platform.system() != "Windows":
        console.print("Mock Drivers:")
        console.print(" - oem0.inf (Microsoft Print To PDF)")
        console.print(" - oem1.inf (NVIDIA GeForce RTX 4090)")
        console.print(" - oem2.inf (Realtek High Definition Audio)")
        console.print(" - oem3.inf (Intel(R) Wireless-AC 9560)")
    else:
        import subprocess

        try:
            result = subprocess.run(
                ["pnputil", "/enum-drivers"],
                capture_output=True,
                text=True,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                lines = result.stdout.splitlines()[:25]
                for line in lines:
                    console.print(line)
                if len(result.stdout.splitlines()) > 25:
                    console.print("... (output truncated for readability)")
            else:
                console.print(f"[red]Error listing drivers: {result.stderr}[/red]")
        except Exception as e:
            console.print(f"[red]Failed to execute listing: {e}[/red]")


@app.command()
def config(
    key: str | None = typer.Argument(None, help="Config key to inspect or set."),
    value: str | None = typer.Argument(None, help="New value to apply to the key."),
) -> None:
    """Inspect or update JSON configuration keys."""
    config_mgr = ConfigManager()

    if key is None:
        console.print("[bold]Current Configurations:[/bold]")
        for k, v in config_mgr._config.items():
            console.print(f"  {k}: {v}")
        console.print(
            f"\nConfiguration Path: [underline]{config_mgr.config_path}[/underline]"
        )
        return

    key = key.lower().strip()
    if value is None:
        val = config_mgr.get(key)
        if val is not None:
            console.print(f"{key}: {val}")
        else:
            console.print(f"[red]Key '{key}' does not exist in configuration.[/red]")
    else:
        # Cast logic for booleans
        if value.lower() in ("true", "yes", "1"):
            typed_value: Any = True
        elif value.lower() in ("false", "no", "0"):
            typed_value = False
        else:
            typed_value = value

        config_mgr.set(key, typed_value)
        console.print(
            f"[green]Key '{key}' successfully updated to '{typed_value}'.[/green]"
        )


@app.command()
def version() -> None:
    """Print the application version."""
    console.print("Driver Backup Utility [bold]v0.1.0[/bold]")


if __name__ == "__main__":
    app()
