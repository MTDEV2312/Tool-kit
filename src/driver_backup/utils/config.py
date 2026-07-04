import json
import platform
from pathlib import Path
from typing import Any


def get_default_backup_dir() -> str:
    """Get the default backup directory based on the platform."""
    if platform.system() == "Windows":
        return "C:\\DriverBackup"
    return str(Path.home() / "DriverBackup")


DEFAULT_CONFIG: dict[str, Any] = {
    "backup_method": "dism",
    "backup_dir": get_default_backup_dir(),
    "theme": "dark",
    "log_level": "INFO",
    "compress_to_zip": True,
    "clean_raw_files": False,
    "third_party_only": True,
}


class ConfigManager:
    """Manages the application configuration load, save, and updates."""

    def __init__(self, config_path: Path | None = None) -> None:
        if config_path is None:
            self.config_path = Path.home() / ".driver_backup" / "config.json"
        else:
            self.config_path = config_path
        self._config: dict[str, Any] = DEFAULT_CONFIG.copy()
        self.load()

    def load(self) -> None:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # Merge with defaults to ensure all keys exist
                        merged = DEFAULT_CONFIG.copy()
                        merged.update(data)
                        self._config = merged
            except Exception:
                self._config = DEFAULT_CONFIG.copy()
        else:
            self.save()

    def save(self) -> None:
        """Save current configuration to file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=4)
        except Exception:
            pass

    def get(self, key: str) -> Any:
        """Get a configuration value."""
        return self._config.get(key, DEFAULT_CONFIG.get(key))

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value and save it."""
        self._config[key] = value
        self.save()

    def reset(self) -> None:
        """Reset configuration to default values."""
        self._config = DEFAULT_CONFIG.copy()
        self.save()

    @property
    def backup_method(self) -> str:
        """The backup method (dism or pnputil)."""
        return str(self.get("backup_method"))

    @backup_method.setter
    def backup_method(self, value: str) -> None:
        self.set("backup_method", value)

    @property
    def backup_dir(self) -> str:
        """The directory path where backups are stored."""
        return str(self.get("backup_dir"))

    @backup_dir.setter
    def backup_dir(self, value: str) -> None:
        self.set("backup_dir", value)

    @property
    def theme(self) -> str:
        """The TUI color theme."""
        return str(self.get("theme"))

    @theme.setter
    def theme(self, value: str) -> None:
        self.set("theme", value)

    @property
    def log_level(self) -> str:
        """The logging severity level."""
        return str(self.get("log_level"))

    @log_level.setter
    def log_level(self, value: str) -> None:
        self.set("log_level", value)

    @property
    def compress_to_zip(self) -> bool:
        """Whether to compress the backup folder into a ZIP file."""
        return bool(self.get("compress_to_zip"))

    @compress_to_zip.setter
    def compress_to_zip(self, value: bool) -> None:
        self.set("compress_to_zip", value)

    @property
    def clean_raw_files(self) -> bool:
        """Whether to clean/remove the raw backup folder after zipping."""
        return bool(self.get("clean_raw_files"))

    @clean_raw_files.setter
    def clean_raw_files(self, value: bool) -> None:
        self.set("clean_raw_files", value)

    @property
    def third_party_only(self) -> bool:
        """Whether to backup third-party drivers only."""
        return bool(self.get("third_party_only"))

    @third_party_only.setter
    def third_party_only(self, value: bool) -> None:
        self.set("third_party_only", value)
