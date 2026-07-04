from typing import Any, cast

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static, Switch

from driver_backup.utils.config import ConfigManager


class SettingsScreen(Screen[None]):
    """Configuration editor screen for TUI settings."""

    CSS = """
    SettingsScreen {
        align: center middle;
        background: $background;
    }

    #settings-container {
        width: 80;
        height: auto;
        border: double $accent;
        background: $surface;
        padding: 1 2;
    }

    #settings-title {
        text-align: center;
        width: 100%;
        color: $accent;
        margin-bottom: 1;
    }

    .form-group {
        margin-bottom: 1;
        height: auto;
    }

    .form-label {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 0;
    }

    #settings-actions {
        margin-top: 1;
        height: auto;
        align: center middle;
        width: 100%;
    }

    #settings-actions Button {
        margin: 0 1;
        width: 16;
    }

    #dir-input {
        width: 100%;
    }
    """

    def on_mount(self) -> None:
        """Load configuration options and set field values."""
        self.config_mgr = ConfigManager()

        app = cast(Any, self.app)
        self.original_theme_dark = app.dark

        # Load directory value
        self.query_one("#dir-input", Input).value = self.config_mgr.backup_dir

        # Load switch for force mock
        self.query_one("#mock-switch", Switch).value = bool(
            self.config_mgr.get("force_mock")
        )

        # Load switch for zip
        self.query_one("#zip-switch", Switch).value = bool(
            self.config_mgr.compress_to_zip
        )

        # Load switch for clean
        self.query_one("#clean-switch", Switch).value = bool(
            self.config_mgr.clean_raw_files
        )

        # Load switch for third party only
        self.query_one("#thirdparty-switch", Switch).value = bool(
            self.config_mgr.third_party_only
        )

        # Load switch for dark mode theme
        self.query_one("#theme-switch", Switch).value = self.config_mgr.theme == "dark"

    def compose(self) -> ComposeResult:
        """Compose Settings layout widgets."""
        yield Header(show_clock=True)

        config = ConfigManager()
        methods = [("DISM Engine", "dism"), ("PnPUtil Engine", "pnputil")]
        log_levels = [("INFO", "INFO"), ("DEBUG", "DEBUG")]

        with Container(id="settings-container"):
            yield Static(
                "▲  [bold cyan]CONFIGURATION SETTINGS[/bold cyan]  ▲",
                id="settings-title",
            )

            with Vertical(classes="form-group"):
                yield Label("Backup Target Directory:", classes="form-label")
                yield Input(placeholder="e.g. C:\\DriverBackup", id="dir-input")

            with Vertical(classes="form-group"):
                yield Label("Backup Engine Method:", classes="form-label")
                yield Select(
                    options=methods, value=config.backup_method, id="method-select"
                )

            with Vertical(classes="form-group"):
                yield Label("Logging Verbosity Level:", classes="form-label")
                yield Select(
                    options=log_levels, value=config.log_level, id="loglevel-select"
                )

            with Horizontal(classes="form-group", id="mock-row"):
                yield Label("Force Simulation Mode (Mock): ", classes="form-label")
                yield Switch(value=False, id="mock-switch")

            with Horizontal(classes="form-group", id="zip-row"):
                yield Label("Compress to ZIP: ", classes="form-label")
                yield Switch(value=True, id="zip-switch")

            with Horizontal(classes="form-group", id="clean-row"):
                yield Label("Clean Raw Files: ", classes="form-label")
                yield Switch(value=False, id="clean-switch")

            with Horizontal(classes="form-group", id="thirdparty-row"):
                yield Label("Backup Third-party Only: ", classes="form-label")
                yield Switch(value=True, id="thirdparty-switch")

            with Horizontal(classes="form-group", id="theme-row"):
                yield Label("Dark Mode Theme: ", classes="form-label")
                yield Switch(value=True, id="theme-switch")

            with Horizontal(id="settings-actions"):
                yield Button("Save Settings", variant="success", id="save-btn")
                yield Button("Reset Defaults", variant="warning", id="reset-btn")
                yield Button("Cancel", variant="error", id="cancel-btn")

        yield Footer()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Dynamically update app dark mode on-the-fly when theme switch changes."""
        if event.switch.id == "theme-switch":
            app = cast(Any, self.app)
            app.dark = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Settings action button presses."""
        app = cast(Any, self.app)
        if event.button.id == "save-btn":
            # Retrieve values
            backup_dir = self.query_one("#dir-input", Input).value.strip()
            method_select = self.query_one("#method-select", Select).value
            loglevel_select = self.query_one("#loglevel-select", Select).value
            mock_switch = self.query_one("#mock-switch", Switch).value
            zip_switch = self.query_one("#zip-switch", Switch).value
            clean_switch = self.query_one("#clean-switch", Switch).value
            thirdparty_switch = self.query_one("#thirdparty-switch", Switch).value
            theme_switch = self.query_one("#theme-switch", Switch).value

            if not backup_dir:
                # Flash or indicate error
                self.query_one(
                    "#dir-input", Input
                ).placeholder = "ERROR: Path cannot be empty!"
                return

            # Save configuration
            self.config_mgr.backup_dir = backup_dir
            if method_select is not None:
                self.config_mgr.backup_method = str(method_select)
            if loglevel_select is not None:
                self.config_mgr.log_level = str(loglevel_select)

            # Save mock config
            self.config_mgr.set("force_mock", bool(mock_switch))

            # Save zip & clean config
            self.config_mgr.compress_to_zip = bool(zip_switch)
            self.config_mgr.clean_raw_files = bool(clean_switch)
            self.config_mgr.third_party_only = bool(thirdparty_switch)

            # Save theme config
            self.config_mgr.theme = "dark" if theme_switch else "light"
            app.dark = theme_switch

            self.dismiss()

        elif event.button.id == "reset-btn":
            self.config_mgr.reset()
            # Update fields to reflect defaults
            self.query_one("#dir-input", Input).value = self.config_mgr.backup_dir
            self.query_one(
                "#method-select", Select
            ).value = self.config_mgr.backup_method
            self.query_one("#loglevel-select", Select).value = self.config_mgr.log_level
            self.query_one("#mock-switch", Switch).value = False
            self.query_one(
                "#zip-switch", Switch
            ).value = self.config_mgr.compress_to_zip
            self.query_one(
                "#clean-switch", Switch
            ).value = self.config_mgr.clean_raw_files
            self.query_one(
                "#thirdparty-switch", Switch
            ).value = self.config_mgr.third_party_only
            self.query_one("#theme-switch", Switch).value = True
            app.dark = True

        elif event.button.id == "cancel-btn":
            app.dark = self.original_theme_dark
            self.config_mgr.theme = "dark" if self.original_theme_dark else "light"
            self.dismiss()
