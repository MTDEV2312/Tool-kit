import tempfile
from pathlib import Path
from typing import Any, Generator
from unittest.mock import patch

import pytest
from textual.widgets import Switch

from driver_backup.app import DriverBackupApp
from driver_backup.ui.settings import SettingsScreen
from driver_backup.utils.config import ConfigManager


@pytest.fixture(autouse=True)
def mock_config_home() -> Generator[Path, None, None]:
    """Redirect home folder to a temp directory for test isolation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        with patch("driver_backup.utils.config.Path.home", return_value=tmp_path):
            yield tmp_path


@pytest.mark.asyncio
async def test_initial_theme_matches_config() -> None:
    """Assert initial app theme matches config value."""
    # Test default (dark)
    app: Any = DriverBackupApp()
    async with app.run_test(size=(100, 45)):
        config = ConfigManager()
        assert config.theme == "dark"
        assert app.dark is True

    # Test overridden (light)
    config = ConfigManager()
    config.theme = "light"
    app2: Any = DriverBackupApp()
    async with app2.run_test(size=(100, 45)):
        assert app2.dark is False


@pytest.mark.asyncio
async def test_keyboard_toggle_shortcut() -> None:
    """Assert keyboard shortcut "t" toggles theme and writes to config."""
    app: Any = DriverBackupApp()
    async with app.run_test(size=(100, 45)) as pilot:
        assert app.dark is True
        config = ConfigManager()
        assert config.theme == "dark"

        # Press "t" to toggle to light
        await pilot.press("t")
        assert app.dark is False

        # Load config again to check persistence
        config2 = ConfigManager()
        assert config2.theme == "light"

        # Press "t" to toggle back to dark
        await pilot.press("t")
        assert app.dark is True

        config3 = ConfigManager()
        assert config3.theme == "dark"


@pytest.mark.asyncio
async def test_settings_screen_mount_displays_correct_switch() -> None:
    """Assert that settings screen mounts and displays correct switch state."""
    app: Any = DriverBackupApp()
    async with app.run_test(size=(100, 45)) as pilot:
        # Open Settings Screen
        await pilot.click("#settings-btn")
        assert isinstance(app.screen, SettingsScreen)

        # Check theme-switch matches App dark state (True)
        switch = app.screen.query_one("#theme-switch", Switch)
        assert switch.value is True


@pytest.mark.asyncio
async def test_settings_switch_updates_theme_realtime() -> None:
    """Assert changing theme switch updates theme preview in real-time."""
    app: Any = DriverBackupApp()
    async with app.run_test(size=(100, 45)) as pilot:
        # Open Settings Screen
        await pilot.click("#settings-btn")
        assert isinstance(app.screen, SettingsScreen)

        switch = app.screen.query_one("#theme-switch", Switch)
        assert switch.value is True
        assert app.dark is True

        # Toggle the switch to False
        switch.value = False
        await pilot.pause()
        # Assert app.dark is updated in real-time
        assert app.dark is False

        # Toggle the switch back to True
        switch.value = True
        await pilot.pause()
        assert app.dark is True


@pytest.mark.asyncio
async def test_settings_cancel_rolls_back_modifications() -> None:
    """Assert that clicking Cancel button rolls back theme modifications."""
    app: Any = DriverBackupApp()
    async with app.run_test(size=(100, 45)) as pilot:
        # Open Settings Screen
        await pilot.click("#settings-btn")
        assert isinstance(app.screen, SettingsScreen)

        switch = app.screen.query_one("#theme-switch", Switch)
        assert switch.value is True
        assert app.dark is True

        # Change switch to False (light mode)
        switch.value = False
        await pilot.pause()
        assert app.dark is False

        # Click Cancel
        await pilot.click("#cancel-btn")
        # SettingsScreen should be dismissed
        assert not isinstance(app.screen, SettingsScreen)

        # Assert theme is restored to original dark state
        assert app.dark is True
        config = ConfigManager()
        assert config.theme == "dark"


@pytest.mark.asyncio
async def test_settings_save_persists_modifications() -> None:
    """Assert that clicking Save button persists modifications."""
    app: Any = DriverBackupApp()
    async with app.run_test(size=(100, 45)) as pilot:
        # Open Settings Screen
        await pilot.click("#settings-btn")
        assert isinstance(app.screen, SettingsScreen)

        switch = app.screen.query_one("#theme-switch", Switch)
        assert switch.value is True

        # Change switch to False (light mode)
        switch.value = False
        await pilot.pause()
        assert app.dark is False

        # Click Save
        await pilot.click("#save-btn")
        # SettingsScreen should be dismissed
        assert not isinstance(app.screen, SettingsScreen)

        # Assert theme is persistent and saved in config
        assert app.dark is False
        config = ConfigManager()
        assert config.theme == "light"


@pytest.mark.asyncio
async def test_settings_reset_resets_to_default_dark() -> None:
    """Assert that clicking Reset button resets theme to default dark."""
    # Write "light" to config initially
    config = ConfigManager()
    config.theme = "light"

    app: Any = DriverBackupApp()
    async with app.run_test(size=(100, 45)) as pilot:
        assert app.dark is False

        # Open Settings Screen
        await pilot.click("#settings-btn")
        assert isinstance(app.screen, SettingsScreen)

        switch = app.screen.query_one("#theme-switch", Switch)
        assert switch.value is False

        # Click Reset
        await pilot.click("#reset-btn")
        await pilot.pause()

        # Assert switch and app.dark are set to True
        assert switch.value is True
        assert app.dark is True

        # Click Save
        await pilot.click("#save-btn")
        assert not isinstance(app.screen, SettingsScreen)

        # Assert config has default dark theme
        config2 = ConfigManager()
        assert config2.theme == "dark"
        assert app.dark is True
