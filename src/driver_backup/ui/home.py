import platform
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Static

from driver_backup.utils.config import ConfigManager
from driver_backup.utils.permissions import elevate_privileges, is_admin


class HomeScreen(Screen[None]):
    """The landing dashboard screen displaying status, config info, and navigation."""

    CSS = """
    HomeScreen {
        align: center middle;
        background: $background;
    }

    #home-container {
        width: 80;
        height: auto;
        border: double $accent;
        background: $surface;
        padding: 1 2;
    }

    #home-title {
        text-align: center;
        width: 100%;
        color: $accent;
        margin-bottom: 1;
    }

    #status-container {
        border: round $primary-lighten-2;
        background: $panel;
        padding: 1;
        margin-bottom: 1;
        height: auto;
    }

    #status-title {
        color: $primary-lighten-1;
        text-style: bold;
        margin-bottom: 1;
    }

    #status-card {
        content-align: left middle;
        height: auto;
    }

    #home-actions {
        height: auto;
        align: center middle;
        width: 100%;
    }

    #home-actions Button {
        margin: 0 1;
        width: 13;
    }
    """

    def on_mount(self) -> None:
        """Called when the screen is mounted. Refreshes status display."""
        self.update_status()

    def update_status(self) -> None:
        """Load configuration details and system status, updating the UI elements."""
        config = ConfigManager()

        # Check privileges
        if is_admin():
            admin_status = "[bold green]Administrator[/bold green]"
            show_elevate = False
        else:
            admin_status = "[bold red]Standard User (Elevation Required)[/bold red]"
            show_elevate = True

        status_text = (
            f"  [bold]Platform OS:[/bold]    {platform.system()} {platform.release()}\n"
            f"  [bold]User Role:[/bold]      {admin_status}\n"
            f"  [bold]Backup Path:[/bold]    {config.backup_dir}\n"
            f"  [bold]Backup Engine:[/bold]  {config.backup_method.upper()}\n"
            f"  [bold]Logging Level:[/bold]  {config.log_level}\n"
        )

        self.query_one("#status-card", Static).update(status_text)

        # Adjust button visibilities
        self.query_one("#elevate-btn", Button).display = show_elevate

        # If not admin and not Windows, we don't need elevation
        if platform.system() != "Windows":
            self.query_one("#elevate-btn", Button).display = False

    def compose(self) -> ComposeResult:
        """Compose the widget hierarchy."""
        yield Header(show_clock=True)

        with Container(id="home-container"):
            yield Static(
                "▲  [bold cyan]DRIVER BACKUP DASHBOARD[/bold cyan]  ▲\n"
                "[dim]Secure, lightweight Windows driver export tool[/dim]",
                id="home-title",
            )

            with Vertical(id="status-container"):
                yield Label("System Status Information", id="status-title")
                yield Static("", id="status-card")

            with Horizontal(id="home-actions"):
                yield Button("Start Backup", variant="success", id="start-btn")
                yield Button("Start Restore", variant="warning", id="restore-btn")
                yield Button("Elevate Admin", variant="warning", id="elevate-btn")
                yield Button("Settings", variant="primary", id="settings-btn")
                yield Button("Exit", variant="error", id="exit-btn")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "start-btn":
            from driver_backup.ui.backup import BackupScreen

            self.app.push_screen(BackupScreen(), callback=self.action_after_screen)
        elif event.button.id == "restore-btn":
            from driver_backup.ui.restore import RestoreScreen

            self.app.push_screen(RestoreScreen(), callback=self.action_after_screen)
        elif event.button.id == "elevate-btn":
            elevate_privileges()
            self.update_status()
        elif event.button.id == "settings-btn":
            from driver_backup.ui.settings import SettingsScreen

            self.app.push_screen(SettingsScreen(), callback=self.action_after_screen)
        elif event.button.id == "exit-btn":
            self.app.exit()

    def action_after_screen(self, result: Any) -> None:
        """Callback to refresh configuration settings when popping back to home."""
        self.update_status()
