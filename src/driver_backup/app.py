from typing import Any, ClassVar

from textual.app import App

from driver_backup.ui.home import HomeScreen
from driver_backup.utils.config import ConfigManager


class DriverBackupApp(App[None]):
    """Main Textual App coordinator class for Driver Backup."""

    TITLE = "Driver Backup Utility"
    SUB_TITLE = "Backup Windows driver packages asynchronously"

    BINDINGS: ClassVar[list[Any]] = [
        ("q", "quit", "Quit Utility"),
        ("t", "toggle_dark", "Toggle Dark Mode"),
    ]

    def on_mount(self) -> None:
        """Called when application starts. Navigates to the main Home screen."""
        config = ConfigManager()
        self.dark = config.theme == "dark"
        self.push_screen(HomeScreen())

    def action_toggle_dark(self) -> None:
        """Toggle dark mode theme and persist it in configuration."""
        self.dark = not self.dark
        try:
            config = ConfigManager()
            config.theme = "dark" if self.dark else "light"
            # Synchronize theme switch if settings screen is active
            from textual.widgets import Switch  # noqa: PLC0415

            from driver_backup.ui.settings import SettingsScreen  # noqa: PLC0415

            if isinstance(self.screen, SettingsScreen):
                try:
                    switch = self.screen.query_one("#theme-switch", Switch)
                    switch.value = self.dark
                except Exception:  # noqa: S110
                    pass
        except Exception:  # noqa: S110
            pass
