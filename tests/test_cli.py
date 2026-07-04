import tempfile
from unittest.mock import patch

from typer.testing import CliRunner

from driver_backup.cli import app

runner = CliRunner()


def test_main_cli() -> None:
    """Test that main command routes to launching the Textual App when no args are provided."""
    with patch("driver_backup.app.DriverBackupApp.run") as mock_run:
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Starting Driver Backup TUI..." in result.stdout
        mock_run.assert_called_once()


def test_version_cli() -> None:
    """Test that version command displays version info."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Driver Backup Utility" in result.stdout
    assert "v0.1.0" in result.stdout


def test_config_cli() -> None:
    """Test config inspection printout."""
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "Current Configurations:" in result.stdout


def test_export_mock_cli() -> None:
    """Test running CLI export command in mock mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(app, ["export", "--destination", tmpdir, "--mock"])
        assert result.exit_code == 0
        assert "Exporting drivers to:" in result.stdout
        # Assert one of the mock stdout outputs is logged
        assert "Backup completed. Zip archive:" in result.stdout


def test_restore_mock_cli() -> None:
    """Test running CLI restore command in mock mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(app, ["restore", "--source", tmpdir, "--mock"])
        assert result.exit_code == 0
        assert "Restoring drivers from:" in result.stdout
        # Assert one of the mock stdout outputs is logged
        assert "Successfully restored 4 driver packages" in result.stdout


def test_export_mutually_exclusive_flags() -> None:
    """Test that specifying both --third-party-only and --all-drivers results in mutual exclusivity error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(
            app,
            ["export", "--destination", tmpdir, "--mock", "--third-party-only", "--all-drivers"],
        )
        assert result.exit_code == 1
        assert "ERROR: Options --third-party-only and --all-drivers are mutually exclusive." in result.stdout


def test_export_third_party_only_flag() -> None:
    """Test running CLI export command with --third-party-only."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("driver_backup.services.backup.get_backup_service") as mock_get_service:
            from unittest.mock import MagicMock
            mock_inner = MagicMock()
            mock_inner.is_supported.return_value = True

            async def dummy_backup(*args, **kwargs):
                from driver_backup.services.base import BackupProgress
                yield BackupProgress(status="completed", percentage=100.0, current_item="Done", log_line="Done")

            mock_inner.backup = dummy_backup
            mock_get_service.return_value = mock_inner

            result = runner.invoke(app, ["export", "--destination", tmpdir, "--mock", "--third-party-only"])
            assert result.exit_code == 0
            mock_get_service.assert_called_once_with(method="dism", force_mock=True, third_party_only=True)


def test_export_all_drivers_flag() -> None:
    """Test running CLI export command with --all-drivers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("driver_backup.services.backup.get_backup_service") as mock_get_service:
            from unittest.mock import MagicMock
            mock_inner = MagicMock()
            mock_inner.is_supported.return_value = True

            async def dummy_backup(*args, **kwargs):
                from driver_backup.services.base import BackupProgress
                yield BackupProgress(status="completed", percentage=100.0, current_item="Done", log_line="Done")

            mock_inner.backup = dummy_backup
            mock_get_service.return_value = mock_inner

            result = runner.invoke(app, ["export", "--destination", tmpdir, "--mock", "--all-drivers"])
            assert result.exit_code == 0
            mock_get_service.assert_called_once_with(method="dism", force_mock=True, third_party_only=False)


