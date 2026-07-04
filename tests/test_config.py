import tempfile
from pathlib import Path

from driver_backup.utils.config import ConfigManager, get_default_backup_dir


def test_config_manager_defaults() -> None:
    """Test that ConfigManager loads default values on a new path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "config.json"
        config = ConfigManager(config_path=tmp_path)

        assert config.backup_method == "dism"
        assert config.backup_dir == get_default_backup_dir()
        assert config.theme == "dark"
        assert config.log_level == "INFO"
        assert config.third_party_only is True
        assert config.config_path == tmp_path
        assert tmp_path.exists()


def test_config_manager_set_get() -> None:
    """Test that ConfigManager persists changes correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "config.json"
        config = ConfigManager(config_path=tmp_path)

        config.backup_method = "pnputil"
        config.backup_dir = "D:\\Drivers"
        config.theme = "light"
        config.log_level = "DEBUG"
        config.set("force_mock", True)

        # Instantiate another manager on the same file to check persistence
        config2 = ConfigManager(config_path=tmp_path)
        assert config2.backup_method == "pnputil"
        assert config2.backup_dir == "D:\\Drivers"
        assert config2.theme == "light"
        assert config2.log_level == "DEBUG"
        assert config2.get("force_mock") is True


def test_config_manager_reset() -> None:
    """Test resetting configuration to defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "config.json"
        config = ConfigManager(config_path=tmp_path)
        config.backup_method = "pnputil"
        config.compress_to_zip = False
        config.clean_raw_files = True

        config.reset()
        assert config.backup_method == "dism"
        assert config.compress_to_zip is True
        assert config.clean_raw_files is False
        assert config.third_party_only is True


def test_config_manager_zip_clean() -> None:
    """Test that compress_to_zip and clean_raw_files can be modified and persist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "config.json"
        config = ConfigManager(config_path=tmp_path)

        # Default checks
        assert config.compress_to_zip is True
        assert config.clean_raw_files is False

        # Modifying values
        config.compress_to_zip = False
        config.clean_raw_files = True

        # Re-loading values
        config2 = ConfigManager(config_path=tmp_path)
        assert config2.compress_to_zip is False
        assert config2.clean_raw_files is True


def test_config_manager_third_party_only() -> None:
    """Test that third_party_only setting can be modified and persist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "config.json"
        config = ConfigManager(config_path=tmp_path)

        # Default checks
        assert config.third_party_only is True

        # Modifying value
        config.third_party_only = False

        # Re-loading values
        config2 = ConfigManager(config_path=tmp_path)
        assert config2.third_party_only is False

