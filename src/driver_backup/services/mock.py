import asyncio
from collections.abc import AsyncGenerator

from driver_backup.services.base import BackupProgress, DriverBackupService


class MockDriverService(DriverBackupService):
    """Simulates a driver backup execution for cross-platform UI development and testing."""

    def __init__(self, third_party_only: bool = False) -> None:
        self.third_party_only = third_party_only

    def is_supported(self) -> bool:
        """Supported on all platforms for development/test purposes."""
        return True

    async def backup(self, backup_dir: str) -> AsyncGenerator[BackupProgress, None]:
        """Simulate backing up 8 drivers, yielding progress increments."""
        mock_drivers = [
            "oem0.inf (Microsoft Print To PDF)",
            "oem1.inf (NVIDIA GeForce RTX 4090)",
            "oem2.inf (Realtek High Definition Audio)",
            "oem3.inf (Intel(R) Wireless-AC 9560)",
            "oem4.inf (Logitech USB Input Device)",
            "oem5.inf (Intel(R) PCI Express Root Port)",
            "oem6.inf (Realtek PCIe GbE Family Controller)",
            "oem7.inf (USB xHCI Compliant Host Controller)",
        ]
        if self.third_party_only:
            mock_drivers = [
                d for d in mock_drivers if "Microsoft Print To PDF" not in d
            ]

        try:
            yield BackupProgress(
                status="starting",
                percentage=0.0,
                current_item="Initializing mock export...",
                log_line="[MOCK-INIT] Initializing driver export engine...",
            )
            await asyncio.sleep(0.5)

            for idx, driver in enumerate(mock_drivers):
                pct = ((idx + 1) / len(mock_drivers)) * 100.0
                yield BackupProgress(
                    status="running",
                    percentage=pct,
                    current_item=driver,
                    log_line=f"[MOCK-EXPORT] Driver package {driver} successfully copied to {backup_dir}",
                )
                await asyncio.sleep(0.3)

            yield BackupProgress(
                status="completed",
                percentage=100.0,
                current_item="Finished.",
                log_line=f"[MOCK-SUCCESS] Successfully backed up {len(mock_drivers)} driver packages to {backup_dir}",
            )
        except asyncio.CancelledError:
            yield BackupProgress(
                status="cancelled",
                percentage=0.0,
                current_item="Cancelled.",
                log_line="[MOCK-CANCEL] Backup task was cancelled by the user.",
            )
            raise
        except Exception as e:
            yield BackupProgress(
                status="failed",
                percentage=0.0,
                current_item="Error occurred.",
                log_line=f"[MOCK-ERROR] Simulated error: {e}",
            )

    async def restore(self, backup_dir: str) -> AsyncGenerator[BackupProgress, None]:
        """Simulate restoring drivers, yielding progress increments."""
        mock_drivers = [
            "oem0.inf (Microsoft Print To PDF)",
            "oem1.inf (NVIDIA GeForce RTX 4090)",
            "oem2.inf (Realtek High Definition Audio)",
            "oem3.inf (Intel(R) Wireless-AC 9560)",
        ]

        import platform

        is_windows = platform.system() == "Windows"

        try:
            yield BackupProgress(
                status="starting",
                percentage=0.0,
                current_item="Initializing mock restore...",
                log_line="[MOCK-INIT] Initializing driver restore engine...",
            )
            await asyncio.sleep(0.5)

            if not is_windows:
                yield BackupProgress(
                    status="running",
                    percentage=0.0,
                    current_item="System Warning",
                    log_line="[WARNING] Driver restoration is Windows-only. Simulating execution on non-Windows host.",
                )
                await asyncio.sleep(0.3)

            for idx, driver in enumerate(mock_drivers):
                pct = ((idx + 1) / len(mock_drivers)) * 100.0
                yield BackupProgress(
                    status="running",
                    percentage=pct,
                    current_item=driver,
                    log_line=f"[MOCK-RESTORE] Restoring driver package {driver} from {backup_dir}...",
                )
                await asyncio.sleep(0.3)

            yield BackupProgress(
                status="completed",
                percentage=100.0,
                current_item="Finished.",
                log_line=f"[MOCK-SUCCESS] Successfully restored {len(mock_drivers)} driver packages from {backup_dir}",
            )
        except asyncio.CancelledError:
            yield BackupProgress(
                status="cancelled",
                percentage=0.0,
                current_item="Cancelled.",
                log_line="[MOCK-CANCEL] Restore task was cancelled by the user.",
            )
            raise
        except Exception as e:
            yield BackupProgress(
                status="failed",
                percentage=0.0,
                current_item="Error occurred.",
                log_line=f"[MOCK-ERROR] Simulated restore error: {e}",
            )
