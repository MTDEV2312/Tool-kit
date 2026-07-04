import asyncio
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Log, ProgressBar, Static

from driver_backup.services.backup import get_backup_service
from driver_backup.utils.config import ConfigManager
from driver_backup.utils.logger import logger, setup_logger
from driver_backup.utils.permissions import is_admin


class BackupScreen(Screen[None]):
    """Monitors active driver backup progress, showing logs and progress bars."""

    CSS = """
    BackupScreen {
        align: center middle;
        background: $background;
    }

    #backup-container {
        width: 90;
        height: 28;
        border: double $accent;
        background: $surface;
        padding: 1 2;
    }

    #backup-title {
        text-align: center;
        width: 100%;
        color: $accent;
        margin-bottom: 1;
    }

    #status-label {
        width: 100%;
        margin-bottom: 1;
        content-align: center middle;
        text-align: center;
    }

    #progress-bar {
        width: 100%;
        margin-bottom: 1;
    }

    #log-widget {
        height: 14;
        border: solid $primary-darken-1;
        background: $panel;
        color: $text;
        margin-bottom: 1;
    }

    #backup-actions {
        height: auto;
        align: center middle;
        width: 100%;
    }

    #backup-actions Button {
        width: 24;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.backup_active = True
        self.backup_worker: Any = None

    def compose(self) -> ComposeResult:
        """Compose Backup execution screen widgets."""
        yield Header(show_clock=True)

        with Container(id="backup-container"):
            yield Static(
                "▲  [bold cyan]DRIVER EXPORT PROCESS[/bold cyan]  ▲", id="backup-title"
            )
            yield Label("Preparing backup...", id="status-label")
            yield ProgressBar(id="progress-bar", total=100.0, show_percentage=True)
            yield Log(id="log-widget", highlight=True)

            with Horizontal(id="backup-actions"):
                yield Button("Cancel Backup", variant="error", id="action-btn")

        yield Footer()

    def on_mount(self) -> None:
        """Launch the backup operation in a background worker thread on mount."""
        self.backup_worker = self.run_worker(self.perform_backup(), exclusive=True)

    async def perform_backup(self) -> None:
        """Perform the backup asynchronously by checking permissions and streaming service yields."""
        config = ConfigManager()
        force_mock = bool(config.get("force_mock"))

        # Ensure loggers are active
        setup_logger(config.log_level, enable_console=False)

        from driver_backup.services.backup import BackupCoordinator

        inner_service = get_backup_service(
            method=config.backup_method,
            force_mock=force_mock,
            third_party_only=config.third_party_only,
        )
        service = BackupCoordinator(
            inner_service=inner_service,
            compress_to_zip=config.compress_to_zip,
            clean_raw_files=config.clean_raw_files,
        )
        log_widget = self.query_one("#log-widget", Log)
        progress_bar = self.query_one("#progress-bar", ProgressBar)

        # Basic validations
        if not force_mock and not service.is_supported():
            self.update_status(
                "ERROR: Backup engine not supported on this platform.", is_error=True
            )
            log_widget.write_line(
                "[SYSTEM-ERROR] The requested backup engine requires Windows OS."
            )
            self.finish_backup(success=False)
            return

        if not force_mock and not is_admin():
            self.update_status(
                "ERROR: Administrative permissions are required.", is_error=True
            )
            log_widget.write_line(
                "[SYSTEM-ERROR] High privileges (Administrator UAC elevation) are required."
            )
            self.finish_backup(success=False)
            return

        log_widget.write_line(f"[SYSTEM-INFO] Destination Folder: {config.backup_dir}")
        log_widget.write_line(
            f"[SYSTEM-INFO] Method Selected: {config.backup_method.upper()}"
        )
        log_widget.write_line(f"[SYSTEM-INFO] Force Mock Flag: {force_mock}")
        log_widget.write_line("[SYSTEM-INFO] Backup process started...")

        try:
            async for progress in service.backup(config.backup_dir):
                progress_bar.progress = progress.percentage

                # Check status
                if progress.status == "starting":
                    self.update_status(
                        f"[cyan]Initializing: {progress.current_item}[/cyan]"
                    )
                elif progress.status == "running":
                    self.update_status(
                        f"[yellow]Backing Up: {progress.current_item}[/yellow]"
                    )
                elif progress.status == "zipping":
                    self.update_status(
                        f"[magenta]Compressing: {progress.current_item}[/magenta]"
                    )
                elif progress.status == "completed":
                    log_widget.write_line(progress.log_line)
                    self.finish_backup(success=True)
                    return
                elif progress.status == "failed":
                    log_widget.write_line(progress.log_line)
                    self.finish_backup(success=False)
                    return
                elif progress.status == "cancelled":
                    log_widget.write_line(progress.log_line)
                    self.finish_backup(success=False, cancelled=True)
                    return

                log_widget.write_line(progress.log_line)
                # Small yield to UI loop
                await asyncio.sleep(0.001)

        except asyncio.CancelledError:
            logger.warning("Backup worker coroutine received CancelledError.")
            log_widget.write_line("[SYSTEM-CANCEL] Backup task cancellation executed.")
            self.finish_backup(success=False, cancelled=True)
        except Exception as e:
            logger.exception(f"Unexpected exception in backup worker: {e}")
            log_widget.write_line(f"[SYSTEM-EXCEPTION] Fatal error occurred: {e}")
            self.finish_backup(success=False)

    def update_status(self, text: str, is_error: bool = False) -> None:
        """Update status label message."""
        label = self.query_one("#status-label", Label)
        if is_error:
            label.update(f"[bold red]{text}[/bold red]")
        else:
            label.update(text)

    def finish_backup(self, success: bool, cancelled: bool = False) -> None:
        """Finalize the backup UI state (adjust action button label)."""
        self.backup_active = False
        btn = self.query_one("#action-btn", Button)
        btn.label = "Back to Home"
        btn.variant = "primary"

        if success:
            self.update_status(
                "[bold green]Backup Completed Successfully![/bold green]"
            )
        elif cancelled:
            self.update_status("[bold yellow]Backup Operation Cancelled.[/bold yellow]")
        else:
            self.update_status("[bold red]Backup Operation Failed.[/bold red]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Cancel / Back button clicks."""
        if event.button.id == "action-btn":
            if self.backup_active:
                if self.backup_worker:
                    self.backup_worker.cancel()
                    self.update_status(
                        "[bold yellow]Cancelling backup...[/bold yellow]"
                    )
            else:
                self.dismiss()
