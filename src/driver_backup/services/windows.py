import asyncio
import contextlib
import os
import platform
import re
from collections.abc import AsyncGenerator
from pathlib import Path

from driver_backup.services.base import BackupProgress, DriverBackupService
from driver_backup.utils.logger import logger


class WindowsDriverService(DriverBackupService):
    """Executes live driver backups on Windows using DISM or PnPUtil."""

    def __init__(self, method: str = "dism", third_party_only: bool = False) -> None:
        self.method = method.lower()
        self.third_party_only = third_party_only

    def is_supported(self) -> bool:
        """Supported only on Windows."""
        return platform.system() == "Windows"

    async def backup(self, backup_dir: str) -> AsyncGenerator[BackupProgress, None]:
        """Perform the driver backup asynchronously to the specified directory."""
        if not self.is_supported():
            raise OSError("WindowsDriverService is only supported on Windows.")

        # Ensure destination folder exists
        try:
            Path(backup_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create backup directory {backup_dir}: {e}")
            yield BackupProgress(
                status="failed",
                percentage=0.0,
                current_item="Directory creation failed",
                log_line=f"ERROR: Could not create directory {backup_dir}. {e}",
            )
            return

        if self.method == "dism":
            async for prog in self._backup_dism(backup_dir):
                yield prog
        else:
            async for prog in self._backup_pnputil(backup_dir):
                yield prog

    async def _backup_dism(
        self, backup_dir: str
    ) -> AsyncGenerator[BackupProgress, None]:
        """Run DISM backup command and parse percentage/driver progress."""
        system32 = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32")
        sysnative = os.path.join(
            os.environ.get("SystemRoot", "C:\\Windows"), "sysnative"
        )

        # Bypass System32 redirection on WOW64 if sysnative exists
        dism_path = os.path.join(system32, "dism.exe")
        if os.path.exists(os.path.join(sysnative, "dism.exe")):
            dism_path = os.path.join(sysnative, "dism.exe")

        logger.info(f"Starting DISM backup to {backup_dir}. Executable: {dism_path}")
        if not self.third_party_only:
            logger.info(
                "DISM backup requested for all drivers, but DISM natively only exports third-party/OEM driver packages."
            )

        yield BackupProgress(
            status="starting",
            percentage=0.0,
            current_item="Initializing DISM engine...",
            log_line="[DISM-INIT] Spawning DISM subprocess...",
        )

        try:
            # dism.exe /online /export-driver /destination:<path>
            args = ["/online", "/export-driver", f"/destination:{backup_dir}"]
            process = await asyncio.create_subprocess_exec(
                dism_path,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
        except Exception as e:
            logger.error(f"Failed to start DISM: {e}")
            yield BackupProgress(
                status="failed",
                percentage=0.0,
                current_item="Failed to launch DISM",
                log_line=f"[DISM-ERROR] Could not start dism.exe process: {e}",
            )
            return

        # Matches: "Exporting 12 of 80 - oem12.inf: The driver package was successfully exported."
        dism_item_re = re.compile(
            r"Exporting\s+(\d+)\s+of\s+(\d+)\s+-\s+([a-zA-Z0-9\._\-]+)", re.IGNORECASE
        )
        # Matches percentage bar updates: "5.0%"
        dism_pct_re = re.compile(r"(\d+\.\d+)%")

        total_drivers = 0
        exported_drivers = 0

        try:
            assert process.stdout is not None
            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes:
                    break

                # Decode using CP437 (typical Windows command prompt OEM encoding)
                line = line_bytes.decode("cp437", errors="replace").strip()
                if not line:
                    continue

                logger.debug(f"DISM: {line}")

                item_match = dism_item_re.search(line)
                pct_match = dism_pct_re.search(line)

                if item_match:
                    current = int(item_match.group(1))
                    total = int(item_match.group(2))
                    driver_name = item_match.group(3)

                    total_drivers = total
                    exported_drivers = current
                    pct = (current / total) * 100.0

                    yield BackupProgress(
                        status="running",
                        percentage=pct,
                        current_item=f"Exporting {driver_name} ({current}/{total})",
                        log_line=line,
                    )
                elif pct_match:
                    pct_val = float(pct_match.group(1))
                    if total_drivers == 0:
                        yield BackupProgress(
                            status="running",
                            percentage=pct_val,
                            current_item="Running...",
                            log_line=line,
                        )
                else:
                    # Generic progress report
                    pct = (
                        (exported_drivers / total_drivers * 100.0)
                        if total_drivers > 0
                        else 0.0
                    )
                    yield BackupProgress(
                        status="running",
                        percentage=pct,
                        current_item="Executing..."
                        if total_drivers == 0
                        else f"Exported {exported_drivers}/{total_drivers}",
                        log_line=line,
                    )

            # Wait for execution to finish fully
            _, stderr_bytes = await process.communicate()
            return_code = process.returncode

            if return_code == 0:
                logger.info("DISM completed successfully.")
                yield BackupProgress(
                    status="completed",
                    percentage=100.0,
                    current_item="Completed.",
                    log_line=f"[DISM-SUCCESS] Successfully exported drivers. Total: {exported_drivers} packages.",
                )
            else:
                stderr_text = stderr_bytes.decode("cp437", errors="replace").strip()
                logger.error(
                    f"DISM failed. Return code: {return_code}. Stderr: {stderr_text}"
                )
                yield BackupProgress(
                    status="failed",
                    percentage=0.0,
                    current_item="Failed",
                    log_line=f"[DISM-FAILED] DISM exited with code {return_code}. {stderr_text}",
                )

        except asyncio.CancelledError:
            logger.warning("DISM task cancelled by caller.")
            try:
                process.terminate()
            except Exception:
                pass
            yield BackupProgress(
                status="cancelled",
                percentage=0.0,
                current_item="Cancelled",
                log_line="[DISM-CANCEL] Backup task was cancelled by the user.",
            )
            raise
        except Exception as e:
            logger.error(f"Exception during DISM run: {e}")
            yield BackupProgress(
                status="failed",
                percentage=0.0,
                current_item="Error",
                log_line=f"[DISM-ERROR] Exception: {e}",
            )

    async def _backup_pnputil(
        self, backup_dir: str
    ) -> AsyncGenerator[BackupProgress, None]:
        """Run PnPUtil backup command and parse package progress."""
        system32 = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32")
        sysnative = os.path.join(
            os.environ.get("SystemRoot", "C:\\Windows"), "sysnative"
        )

        pnputil_path = os.path.join(system32, "pnputil.exe")
        if os.path.exists(os.path.join(sysnative, "pnputil.exe")):
            pnputil_path = os.path.join(sysnative, "pnputil.exe")

        logger.info(
            f"Starting PnPUtil backup to {backup_dir}. Executable: {pnputil_path}"
        )

        if self.third_party_only:
            yield BackupProgress(
                status="starting",
                percentage=0.0,
                current_item="Enumerating drivers...",
                log_line="[PNPUTIL] Enumerating driver packages using /enum-drivers...",
            )
            try:
                process = await asyncio.create_subprocess_exec(
                    pnputil_path,
                    "/enum-drivers",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=0x08000000,
                )
                stdout_bytes, stderr_bytes = await process.communicate()
                if process.returncode != 0:
                    stderr_text = stderr_bytes.decode("cp437", errors="replace").strip()
                    logger.error(
                        f"Failed to enumerate drivers. Code: {process.returncode}. Stderr: {stderr_text}"
                    )
                    yield BackupProgress(
                        status="failed",
                        percentage=0.0,
                        current_item="Failed to enumerate drivers",
                        log_line=f"[PNPUTIL-ERROR] /enum-drivers failed: {stderr_text}",
                    )
                    return
            except Exception as e:
                logger.error(f"Exception enumerating drivers: {e}")
                yield BackupProgress(
                    status="failed",
                    percentage=0.0,
                    current_item="Error enumerating drivers",
                    log_line=f"[PNPUTIL-ERROR] Exception: {e}",
                )
                return

            stdout_str = stdout_bytes.decode("cp437", errors="replace")
            current_published: str | None = None
            current_provider: str | None = None
            drivers: list[tuple[str, str]] = []
            for line in stdout_str.splitlines():
                line = line.strip()
                if not line:
                    continue
                if ":" in line:
                    parts = line.split(":", 1)
                    key = parts[0].strip().lower()
                    val = parts[1].strip()
                    if "published name" in key:
                        if current_published:
                            drivers.append((current_published, current_provider or ""))
                        current_published = val
                        current_provider = None
                    elif "provider name" in key:
                        current_provider = val
            if current_published:
                drivers.append((current_published, current_provider or ""))

            oem_drivers = [
                pub for pub, prov in drivers if "microsoft" not in prov.lower()
            ]

            if not oem_drivers:
                logger.info("No third-party OEM drivers found to backup.")
                yield BackupProgress(
                    status="completed",
                    percentage=100.0,
                    current_item="Completed.",
                    log_line="[PNPUTIL-INFO] No third-party OEM drivers found.",
                )
                return

            total = len(oem_drivers)
            logger.info(f"Found {total} third-party OEM driver packages to export.")
            try:
                for idx, driver_inf in enumerate(oem_drivers):
                    pct = ((idx + 1) / total) * 100.0
                    yield BackupProgress(
                        status="running",
                        percentage=pct,
                        current_item=f"Exporting {driver_inf} ({idx + 1}/{total})",
                        log_line=f"[PNPUTIL] Exporting driver package: {driver_inf}",
                    )
                    args = ["/export-driver", driver_inf, backup_dir]
                    export_proc = await asyncio.create_subprocess_exec(
                        pnputil_path,
                        *args,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        creationflags=0x08000000,
                    )
                    try:
                        out_bytes, err_bytes = await export_proc.communicate()
                        if export_proc.returncode != 0:
                            err_text = err_bytes.decode(
                                "cp437", errors="replace"
                            ).strip()
                            logger.warning(
                                f"Failed to export driver {driver_inf}: {err_text}"
                            )
                    except asyncio.CancelledError:
                        try:
                            export_proc.terminate()
                        except Exception:
                            pass
                        raise
            except asyncio.CancelledError:
                logger.warning("PnPUtil backup task cancelled by caller.")
                yield BackupProgress(
                    status="cancelled",
                    percentage=0.0,
                    current_item="Cancelled",
                    log_line="[PNPUTIL-CANCEL] Backup task was cancelled by the user.",
                )
                raise

            yield BackupProgress(
                status="completed",
                percentage=100.0,
                current_item="Completed.",
                log_line=f"[PNPUTIL-SUCCESS] Exported {total} third-party OEM drivers.",
            )
            return

        yield BackupProgress(
            status="starting",
            percentage=0.0,
            current_item="Initializing PnPUtil...",
            log_line="[PNPUTIL-INIT] Spawning PnPUtil subprocess...",
        )

        try:
            # pnputil.exe /export-driver * <path>
            args = ["/export-driver", "*", backup_dir]
            process = await asyncio.create_subprocess_exec(
                pnputil_path,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
        except Exception as e:
            logger.error(f"Failed to start PnPUtil: {e}")
            yield BackupProgress(
                status="failed",
                percentage=0.0,
                current_item="Failed to launch PnPUtil",
                log_line=f"[PNPUTIL-ERROR] Could not start pnputil.exe process: {e}",
            )
            return

        # Matches: "Exporting driver package:    oem12.inf"
        pnputil_item_re = re.compile(
            r"Exporting driver package:\s+([a-zA-Z0-9\._\-]+)", re.IGNORECASE
        )

        exported_count = 0

        try:
            assert process.stdout is not None
            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes:
                    break

                line = line_bytes.decode("cp437", errors="replace").strip()
                if not line:
                    continue

                logger.debug(f"PnPUtil: {line}")

                item_match = pnputil_item_re.search(line)
                if item_match:
                    driver_name = item_match.group(1)
                    exported_count += 1
                    # Soft-increase percentage to keep progress moving
                    pct = min(99.0, exported_count * 1.5)
                    yield BackupProgress(
                        status="running",
                        percentage=pct,
                        current_item=f"Exporting {driver_name} (#{exported_count})",
                        log_line=line,
                    )
                else:
                    pct = min(99.0, exported_count * 1.5)
                    yield BackupProgress(
                        status="running",
                        percentage=pct,
                        current_item=f"Exporting... (Count: {exported_count})",
                        log_line=line,
                    )

            # Wait for execution to finish fully
            _, stderr_bytes = await process.communicate()
            return_code = process.returncode

            if return_code == 0:
                logger.info("PnPUtil completed successfully.")
                yield BackupProgress(
                    status="completed",
                    percentage=100.0,
                    current_item="Completed.",
                    log_line=f"[PNPUTIL-SUCCESS] Exported drivers. Total: {exported_count} packages.",
                )
            else:
                stderr_text = stderr_bytes.decode("cp437", errors="replace").strip()
                logger.error(
                    f"PnPUtil failed. Return code: {return_code}. Stderr: {stderr_text}"
                )
                yield BackupProgress(
                    status="failed",
                    percentage=0.0,
                    current_item="Failed",
                    log_line=f"[PNPUTIL-FAILED] PnPUtil exited with code {return_code}. {stderr_text}",
                )

        except asyncio.CancelledError:
            logger.warning("PnPUtil task cancelled by caller.")
            try:
                process.terminate()
            except Exception:
                pass
            yield BackupProgress(
                status="cancelled",
                percentage=0.0,
                current_item="Cancelled",
                log_line="[PNPUTIL-CANCEL] Backup task was cancelled by the user.",
            )
            raise
        except Exception as e:
            logger.error(f"Exception during PnPUtil run: {e}")
            yield BackupProgress(
                status="failed",
                percentage=0.0,
                current_item="Error",
                log_line=f"[PNPUTIL-ERROR] Exception: {e}",
            )

    async def restore(self, backup_dir: str) -> AsyncGenerator[BackupProgress, None]:
        """Perform the driver restore asynchronously from the specified directory."""
        if not self.is_supported():
            raise OSError("WindowsDriverService is only supported on Windows.")

        # Ensure source folder exists
        if not Path(backup_dir).exists():
            yield BackupProgress(
                status="failed",
                percentage=0.0,
                current_item="Directory not found",
                log_line=f"ERROR: Backup directory does not exist: {backup_dir}",
            )
            return

        if self.method == "dism":
            logger.warning(
                "DISM does not support adding drivers to an online running system (Error 50). "
                "Falling back to PnPUtil for restoration."
            )
            yield BackupProgress(
                status="running",
                percentage=0.0,
                current_item="DISM online not supported. Using PnPUtil...",
                log_line="[RESTORE-WARNING] DISM does not support adding drivers online (Error 50). Falling back to PnPUtil.",
            )
            async for prog in self._restore_pnputil(backup_dir):
                yield prog
        else:
            async for prog in self._restore_pnputil(backup_dir):
                yield prog

    async def _restore_dism(
        self, backup_dir: str
    ) -> AsyncGenerator[BackupProgress, None]:
        """Run DISM restore command and parse percentage/driver progress."""
        system32 = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32")
        sysnative = os.path.join(
            os.environ.get("SystemRoot", "C:\\Windows"), "sysnative"
        )

        dism_path = os.path.join(system32, "dism.exe")
        if os.path.exists(os.path.join(sysnative, "dism.exe")):
            dism_path = os.path.join(sysnative, "dism.exe")

        logger.info(f"Starting DISM restore from {backup_dir}. Executable: {dism_path}")

        yield BackupProgress(
            status="starting",
            percentage=0.0,
            current_item="Initializing DISM restore...",
            log_line="[DISM-INIT] Spawning DISM subprocess for restore...",
        )

        try:
            # dism.exe /online /Add-Driver /Driver:<backup_dir> /Recurse
            args = ["/online", "/Add-Driver", f"/Driver:{backup_dir}", "/Recurse"]
            process = await asyncio.create_subprocess_exec(
                dism_path,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
        except Exception as e:
            logger.error(f"Failed to start DISM: {e}")
            yield BackupProgress(
                status="failed",
                percentage=0.0,
                current_item="Failed to launch DISM",
                log_line=f"[DISM-ERROR] Could not start dism.exe process for restore: {e}",
            )
            return

        # Matches: "Installing 1 of 80 - C:\Backup\oem12.inf: The driver package was successfully installed."
        dism_item_re = re.compile(
            r"Installing\s+(\d+)\s+of\s+(\d+)\s+-\s+(.+)", re.IGNORECASE
        )
        dism_pct_re = re.compile(r"(\d+\.\d+)%")

        total_drivers = 0
        installed_drivers = 0

        try:
            assert process.stdout is not None
            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes:
                    break

                line = line_bytes.decode("cp437", errors="replace").strip()
                if not line:
                    continue

                logger.debug(f"DISM restore: {line}")

                item_match = dism_item_re.search(line)
                pct_match = dism_pct_re.search(line)

                if item_match:
                    current = int(item_match.group(1))
                    total = int(item_match.group(2))
                    # Extract inf file name safely
                    inf_part = item_match.group(3).split(":")[0].strip()
                    driver_name = Path(inf_part).name

                    total_drivers = total
                    installed_drivers = current
                    pct = (current / total) * 100.0

                    yield BackupProgress(
                        status="running",
                        percentage=pct,
                        current_item=f"Restoring {driver_name} ({current}/{total})",
                        log_line=line,
                    )
                elif pct_match:
                    pct_val = float(pct_match.group(1))
                    if total_drivers == 0:
                        yield BackupProgress(
                            status="running",
                            percentage=pct_val,
                            current_item="Running...",
                            log_line=line,
                        )
                else:
                    pct = (
                        (installed_drivers / total_drivers * 100.0)
                        if total_drivers > 0
                        else 0.0
                    )
                    yield BackupProgress(
                        status="running",
                        percentage=pct,
                        current_item="Executing..."
                        if total_drivers == 0
                        else f"Restored {installed_drivers}/{total_drivers}",
                        log_line=line,
                    )

            _, stderr_bytes = await process.communicate()
            return_code = process.returncode

            if return_code == 0:
                logger.info("DISM restore completed successfully.")
                yield BackupProgress(
                    status="completed",
                    percentage=100.0,
                    current_item="Completed.",
                    log_line=f"[DISM-SUCCESS] Successfully restored drivers. Total: {installed_drivers} packages.",
                )
            else:
                stderr_text = stderr_bytes.decode("cp437", errors="replace").strip()
                logger.error(
                    f"DISM restore failed. Return code: {return_code}. Stderr: {stderr_text}"
                )
                yield BackupProgress(
                    status="failed",
                    percentage=0.0,
                    current_item="Failed",
                    log_line=(
                        f"[DISM-FAILED] DISM exited with code "
                        f"{return_code}. {stderr_text}"
                    ),
                )

        except asyncio.CancelledError:
            logger.warning("DISM restore task cancelled by caller.")
            with contextlib.suppress(Exception):
                process.terminate()
            yield BackupProgress(
                status="cancelled",
                percentage=0.0,
                current_item="Cancelled",
                log_line="[DISM-CANCEL] Restore task was cancelled by the user.",
            )
            raise
        except Exception as e:
            logger.error(f"Exception during DISM restore: {e}")
            yield BackupProgress(
                status="failed",
                percentage=0.0,
                current_item="Error",
                log_line=f"[DISM-ERROR] Exception: {e}",
            )

    async def _restore_pnputil(
        self, backup_dir: str
    ) -> AsyncGenerator[BackupProgress, None]:
        """Run PnPUtil restore command and parse package progress."""
        system32 = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32")
        sysnative = os.path.join(
            os.environ.get("SystemRoot", "C:\\Windows"), "sysnative"
        )

        pnputil_path = os.path.join(system32, "pnputil.exe")
        if os.path.exists(os.path.join(sysnative, "pnputil.exe")):
            pnputil_path = os.path.join(sysnative, "pnputil.exe")

        logger.info(
            f"Starting PnPUtil restore from {backup_dir}. Executable: {pnputil_path}"
        )

        yield BackupProgress(
            status="starting",
            percentage=0.0,
            current_item="Initializing PnPUtil...",
            log_line="[PNPUTIL-INIT] Spawning PnPUtil subprocess for restore...",
        )

        try:
            # pnputil.exe /add-driver <backup_dir>\*.inf /subdirs /install
            path_pattern = os.path.join(backup_dir, "*.inf")
            args = ["/add-driver", path_pattern, "/subdirs", "/install"]
            process = await asyncio.create_subprocess_exec(
                pnputil_path,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
        except Exception as e:
            logger.error(f"Failed to start PnPUtil: {e}")
            yield BackupProgress(
                status="failed",
                percentage=0.0,
                current_item="Failed to launch PnPUtil",
                log_line=f"[PNPUTIL-ERROR] Could not start pnputil.exe process for restore: {e}",
            )
            return

        # Matches output line: "Adding driver package:    oem12.inf" or "Processing inf:    oem12.inf"
        pnputil_item_re = re.compile(
            r"(Adding driver package:|Processing inf:)\s+([a-zA-Z0-9\._\-]+)",
            re.IGNORECASE,
        )

        restored_count = 0

        try:
            assert process.stdout is not None
            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes:
                    break

                line = line_bytes.decode("cp437", errors="replace").strip()
                if not line:
                    continue

                logger.debug(f"PnPUtil restore: {line}")

                item_match = pnputil_item_re.search(line)
                if item_match:
                    driver_name = item_match.group(2)
                    restored_count += 1
                    pct = min(99.0, restored_count * 1.5)
                    yield BackupProgress(
                        status="running",
                        percentage=pct,
                        current_item=f"Restoring {driver_name} (#{restored_count})",
                        log_line=line,
                    )
                else:
                    pct = min(99.0, restored_count * 1.5)
                    yield BackupProgress(
                        status="running",
                        percentage=pct,
                        current_item=f"Restoring... (Count: {restored_count})",
                        log_line=line,
                    )

            _, stderr_bytes = await process.communicate()
            return_code = process.returncode

            if return_code in (0, 3010):  # 3010 means ERROR_SUCCESS_REBOOT_REQUIRED
                logger.info(
                    f"PnPUtil restore completed successfully (exit code: {return_code})."
                )
                reboot_msg = " (Reboot required)" if return_code == 3010 else ""
                yield BackupProgress(
                    status="completed",
                    percentage=100.0,
                    current_item="Completed.",
                    log_line=f"[PNPUTIL-SUCCESS] Restored drivers{reboot_msg}. Total: {restored_count} packages.",
                )
            else:
                stderr_text = stderr_bytes.decode("cp437", errors="replace").strip()
                logger.error(
                    f"PnPUtil restore failed. Return code: {return_code}. Stderr: {stderr_text}"
                )
                yield BackupProgress(
                    status="failed",
                    percentage=0.0,
                    current_item="Failed",
                    log_line=(
                        f"[PNPUTIL-FAILED] PnPUtil exited with code "
                        f"{return_code}. {stderr_text}"
                    ),
                )

        except asyncio.CancelledError:
            logger.warning("PnPUtil restore task cancelled by caller.")
            with contextlib.suppress(Exception):
                process.terminate()
            yield BackupProgress(
                status="cancelled",
                percentage=0.0,
                current_item="Cancelled",
                log_line="[PNPUTIL-CANCEL] Restore task was cancelled by the user.",
            )
            raise
        except Exception as e:
            logger.error(f"Exception during PnPUtil restore: {e}")
            yield BackupProgress(
                status="failed",
                percentage=0.0,
                current_item="Error",
                log_line=f"[PNPUTIL-ERROR] Exception: {e}",
            )
