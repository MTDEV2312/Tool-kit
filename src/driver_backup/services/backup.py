import asyncio
import datetime
import platform
import shutil
import tempfile
import zipfile
from collections.abc import AsyncGenerator
from pathlib import Path

from driver_backup.services.base import BackupProgress, DriverBackupService
from driver_backup.services.mock import MockDriverService
from driver_backup.services.windows import WindowsDriverService
from driver_backup.utils.logger import logger


def _get_os_info() -> str:
    try:
        return f"{platform.system()} {platform.release()}"
    except Exception:
        return "Unknown OS Version"


def _get_cpu_info() -> str:
    try:
        if platform.system() == "Windows":
            import winreg

            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
                ) as key:
                    name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                    return str(name).strip()
            except Exception:
                pass
        elif platform.system() == "Linux":
            try:
                p = Path("/proc/cpuinfo")
                if p.exists():
                    for line in p.read_text(
                        encoding="utf-8", errors="ignore"
                    ).splitlines():
                        if line.strip().lower().startswith("model name"):
                            parts = line.split(":", 1)
                            if len(parts) > 1:
                                return parts[1].strip()
            except Exception:
                pass
        return platform.processor() or "Unknown CPU"
    except Exception:
        return platform.processor() or "Unknown CPU"


def _get_motherboard_info() -> str:
    try:
        if platform.system() == "Windows":
            import winreg

            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS"
                ) as key:
                    try:
                        manufacturer, _ = winreg.QueryValueEx(
                            key, "BaseBoardManufacturer"
                        )
                    except Exception:
                        manufacturer = ""
                    try:
                        product, _ = winreg.QueryValueEx(key, "BaseBoardProduct")
                    except Exception:
                        product = ""
                    res = f"{manufacturer} {product}".strip()
                    if res:
                        return res
            except Exception:
                pass
        elif platform.system() == "Linux":
            try:
                vendor_path = Path("/sys/class/dmi/id/board_vendor")
                name_path = Path("/sys/class/dmi/id/board_name")
                vendor = (
                    vendor_path.read_text(encoding="utf-8", errors="ignore").strip()
                    if vendor_path.exists()
                    else ""
                )
                name = (
                    name_path.read_text(encoding="utf-8", errors="ignore").strip()
                    if name_path.exists()
                    else ""
                )
                res = f"{vendor} {name}".strip()
                if res:
                    return res
            except Exception:
                pass
        return "Unknown Motherboard"
    except Exception:
        return "Unknown Motherboard"


def _get_ram_info() -> str:
    try:
        if platform.system() == "Windows":
            import ctypes

            try:

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]

                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    total_gb = stat.ullTotalPhys / (1024**3)
                    return f"{total_gb:.2f} GB"
            except Exception:
                pass
        elif platform.system() == "Linux":
            try:
                p = Path("/proc/meminfo")
                if p.exists():
                    for line in p.read_text(
                        encoding="utf-8", errors="ignore"
                    ).splitlines():
                        if line.strip().lower().startswith("memtotal"):
                            parts = line.split(":", 1)
                            if len(parts) > 1:
                                mem_str = parts[1].strip()
                                mem_parts = mem_str.split()
                                if mem_parts:
                                    val = int(mem_parts[0])
                                    if (
                                        len(mem_parts) > 1
                                        and mem_parts[1].lower() == "kb"
                                    ):
                                        total_gb = val / (1024**2)
                                    else:
                                        total_gb = val / (1024**3)
                                    return f"{total_gb:.2f} GB"
            except Exception:
                pass
        return "Unknown RAM"
    except Exception:
        return "Unknown RAM"


def _get_gpu_info() -> str:
    try:
        if platform.system() == "Windows":
            import winreg

            gpus = []
            try:
                class_key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, class_key_path) as key:
                    idx = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, idx)
                            if subkey_name.isdigit():
                                try:
                                    with winreg.OpenKey(key, subkey_name) as subkey:
                                        desc, _ = winreg.QueryValueEx(
                                            subkey, "DriverDesc"
                                        )
                                        if desc:
                                            gpus.append(str(desc).strip())
                                except Exception:
                                    pass
                            idx += 1
                        except OSError:
                            break
            except Exception:
                pass
            if gpus:
                return ", ".join(gpus)
        return "Unknown GPU"
    except Exception:
        return "Unknown GPU"


class BackupCoordinator:
    """Wraps a DriverBackupService to coordinate timestamp directories, zipping, and unzipping."""

    def __init__(
        self,
        inner_service: DriverBackupService,
        compress_to_zip: bool = True,
        clean_raw_files: bool = False,
    ) -> None:
        self.inner_service = inner_service
        self.compress_to_zip = compress_to_zip
        self.clean_raw_files = clean_raw_files

    def is_supported(self) -> bool:
        """Supported if the underlying service is supported."""
        return self.inner_service.is_supported()

    async def _write_hardware_info(self, raw_backup_path: Path) -> None:
        """Writes hardware query information to hardware_info.txt inside raw_backup_path."""

        def write_sync() -> None:
            try:
                info_file = raw_backup_path / "hardware_info.txt"
                os_info = _get_os_info()
                cpu_info = _get_cpu_info()
                mb_info = _get_motherboard_info()
                ram_info = _get_ram_info()
                gpu_info = _get_gpu_info()

                content = (
                    f"OS Version: {os_info}\n"
                    f"CPU: {cpu_info}\n"
                    f"Motherboard: {mb_info}\n"
                    f"RAM: {ram_info}\n"
                    f"GPU: {gpu_info}\n"
                )
                info_file.write_text(content, encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to write hardware info: {e}")

        await asyncio.to_thread(write_sync)

    async def backup(self, backup_dir: str) -> AsyncGenerator[BackupProgress, None]:
        """Perform backup. Generates a timestamp folder, backs up to it, and optionally zips/cleans."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        folder_name = f"DriverBackup_{timestamp}"
        raw_backup_path = Path(backup_dir) / folder_name
        try:
            raw_backup_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create backup directory {raw_backup_path}: {e}")
            yield BackupProgress(
                status="failed",
                percentage=0.0,
                current_item="Directory creation failed",
                log_line=f"ERROR: Could not create directory {raw_backup_path}. {e}",
            )
            return

        if self.compress_to_zip:
            async for progress in self.inner_service.backup(str(raw_backup_path)):
                if progress.status == "completed":
                    yield BackupProgress(
                        status="running",
                        percentage=90.0,
                        current_item="Backup files exported.",
                        log_line=progress.log_line,
                    )
                elif progress.status in ("failed", "cancelled"):
                    yield progress
                    return
                else:
                    yield BackupProgress(
                        status=progress.status,
                        percentage=progress.percentage * 0.9,
                        current_item=progress.current_item,
                        log_line=progress.log_line,
                    )

            # Write hardware info right before starting the zipping phase
            await self._write_hardware_info(raw_backup_path)

            # Start zipping phase
            yield BackupProgress(
                status="zipping",
                percentage=90.0,
                current_item="Zipping backup folder...",
                log_line="[ZIP] Creating zip archive...",
            )

            try:
                # make_archive appends .zip automatically, so base_name is path without suffix
                await asyncio.to_thread(
                    shutil.make_archive,
                    base_name=str(raw_backup_path),
                    format="zip",
                    root_dir=str(raw_backup_path.parent),
                    base_dir=raw_backup_path.name,
                )
            except Exception as e:
                zip_output = Path(f"{raw_backup_path}.zip")
                if zip_output.exists():
                    try:
                        zip_output.unlink()
                    except Exception as unlink_err:
                        logger.warning(
                            f"Failed to delete incomplete zip file {zip_output}: {unlink_err}"
                        )
                yield BackupProgress(
                    status="failed",
                    percentage=90.0,
                    current_item="Zipping failed",
                    log_line=f"[ZIP-ERROR] Zipping failed: {e}",
                )
                return

            yield BackupProgress(
                status="zipping",
                percentage=99.0,
                current_item="Zipping complete",
                log_line="[ZIP] Zip archive created successfully.",
            )

            if self.clean_raw_files:
                yield BackupProgress(
                    status="zipping",
                    percentage=99.5,
                    current_item="Cleaning raw files...",
                    log_line=f"[ZIP] Removing uncompressed backup folder: {raw_backup_path}",
                )
                try:
                    await asyncio.to_thread(shutil.rmtree, raw_backup_path)
                except Exception as e:
                    logger.warning(
                        f"Failed to remove raw backup folder {raw_backup_path}: {e}"
                    )

            yield BackupProgress(
                status="completed",
                percentage=100.0,
                current_item="Finished.",
                log_line=f"[SUCCESS] Backup completed. Zip archive: {raw_backup_path}.zip",
            )
        else:
            async for progress in self.inner_service.backup(str(raw_backup_path)):
                if progress.status == "completed":
                    await self._write_hardware_info(raw_backup_path)
                yield progress

    async def restore(self, backup_dir: str) -> AsyncGenerator[BackupProgress, None]:
        """Perform restore. Unzips if zip file is specified, then restores from directory."""
        path = Path(backup_dir)
        if path.is_file() and path.suffix.lower() == ".zip":
            yield BackupProgress(
                status="extracting",
                percentage=0.0,
                current_item="Extracting ZIP archive...",
                log_line=f"[UNZIP] Extracting {path.name}...",
            )

            temp_dir_str = tempfile.mkdtemp()
            temp_dir = Path(temp_dir_str)
            try:

                def unzip_func() -> None:
                    with zipfile.ZipFile(path, "r") as zip_ref:
                        zip_ref.extractall(temp_dir_str)

                try:
                    await asyncio.to_thread(unzip_func)
                except Exception as e:
                    yield BackupProgress(
                        status="failed",
                        percentage=0.0,
                        current_item="Extraction failed",
                        log_line=f"[UNZIP-ERROR] Extraction failed: {e}",
                    )
                    return

                yield BackupProgress(
                    status="extracting",
                    percentage=10.0,
                    current_item="Extraction complete",
                    log_line="[UNZIP] ZIP extraction completed successfully.",
                )

                inner_restore_dir = temp_dir / path.stem
                if not inner_restore_dir.is_dir():
                    subdirs = [p for p in temp_dir.iterdir() if p.is_dir()]
                    if len(subdirs) == 1:
                        inner_restore_dir = subdirs[0]
                    else:
                        inner_restore_dir = temp_dir

                async for progress in self.inner_service.restore(
                    str(inner_restore_dir)
                ):
                    scaled_pct = 10.0 + (progress.percentage * 0.9)
                    if progress.status == "completed":
                        yield BackupProgress(
                            status="completed",
                            percentage=100.0,
                            current_item=progress.current_item,
                            log_line=progress.log_line,
                        )
                    elif progress.status in ("failed", "cancelled"):
                        yield progress
                        return
                    else:
                        yield BackupProgress(
                            status=progress.status,
                            percentage=scaled_pct,
                            current_item=progress.current_item,
                            log_line=progress.log_line,
                        )
            finally:
                try:
                    await asyncio.to_thread(shutil.rmtree, temp_dir_str)
                except Exception as e:
                    logger.warning(
                        f"Failed to clean up temp restore directory {temp_dir_str}: {e}"
                    )
        else:
            async for progress in self.inner_service.restore(backup_dir):
                yield progress


def get_backup_service(
    method: str = "dism", force_mock: bool = False, third_party_only: bool = True
) -> DriverBackupService:
    """Retrieve the appropriate DriverBackupService implementation for backup and restore.

    If force_mock is True or the current platform is not Windows,
    MockDriverService is returned. Otherwise, WindowsDriverService is returned.
    """
    if force_mock or platform.system() != "Windows":
        logger.info(
            "Using MockDriverService (forced or running on non-Windows platform)"
        )
        return MockDriverService(third_party_only=third_party_only)

    logger.info(
        f"Using WindowsDriverService (method: {method}, third_party_only: {third_party_only})"
    )
    return WindowsDriverService(method=method, third_party_only=third_party_only)
