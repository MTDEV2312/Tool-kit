from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Protocol


@dataclass
class BackupProgress:
    """Represents a progress update from the backup operation."""

    status: str  # "starting", "running", "completed", "failed", "cancelled", "zipping", "extracting"
    percentage: float  # 0.0 to 100.0
    current_item: str  # Current driver name/action
    log_line: str  # Raw subprocess output line


class DriverBackupService(Protocol):
    """Protocol defining interface for platform-specific driver backup engines."""

    def is_supported(self) -> bool:
        """Return True if this service is supported on the current platform."""
        ...

    def backup(self, backup_dir: str) -> AsyncGenerator[BackupProgress, None]:
        """Execute the backup asynchronously, yielding progress reports."""
        ...

    def restore(self, backup_dir: str) -> AsyncGenerator[BackupProgress, None]:
        """Execute the restore asynchronously, yielding progress reports."""
        ...
