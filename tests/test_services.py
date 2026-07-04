import shutil
import tempfile
import zipfile
from pathlib import Path

import pytest

from driver_backup.services.backup import get_backup_service, BackupCoordinator
from driver_backup.services.mock import MockDriverService


@pytest.mark.asyncio
async def test_mock_driver_service() -> None:
    """Verify that MockDriverService correctly yields start, running, and completion states."""
    service = MockDriverService()
    assert service.is_supported() is True

    with tempfile.TemporaryDirectory() as tmpdir:
        events = []
        async for progress in service.backup(tmpdir):
            events.append(progress)

        assert len(events) >= 3
        assert events[0].status == "starting"
        assert events[0].percentage == 0.0

        # Ensure we have running progress updates
        running_events = [e for e in events if e.status == "running"]
        assert len(running_events) == 8
        assert running_events[-1].percentage == 100.0

        # Final success event
        assert events[-1].status == "completed"
        assert events[-1].percentage == 100.0


def test_backup_factory_resolution() -> None:
    """Verify that factory resolves to MockDriverService when forced or on Unix."""
    service_mock = get_backup_service(method="dism", force_mock=True)
    assert isinstance(service_mock, MockDriverService)


@pytest.mark.asyncio
async def test_mock_driver_service_restore() -> None:
    """Verify that MockDriverService restore correctly yields states."""
    service = MockDriverService()
    assert service.is_supported() is True

    with tempfile.TemporaryDirectory() as tmpdir:
        events = []
        async for progress in service.restore(tmpdir):
            events.append(progress)

        assert len(events) >= 3
        assert events[0].status == "starting"
        assert events[0].percentage == 0.0

        # Ensure we have running progress updates
        running_events = [e for e in events if e.status == "running"]
        assert len(running_events) >= 4

        # Final success event
        assert events[-1].status == "completed"
        assert events[-1].percentage == 100.0


@pytest.mark.asyncio
async def test_backup_coordinator_zip_and_clean() -> None:
    """Verify that BackupCoordinator handles timestamp dirs, zipping, and cleaning correctly."""
    inner_service = MockDriverService()
    coordinator = BackupCoordinator(inner_service, compress_to_zip=True, clean_raw_files=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        events = []
        async for progress in coordinator.backup(tmpdir):
            events.append(progress)

        assert len(events) >= 5
        assert events[0].status == "starting"
        assert events[0].percentage == 0.0

        # Find the zip file that should have been created in tmpdir
        tmp_path = Path(tmpdir)
        zip_files = list(tmp_path.glob("DriverBackup_*.zip"))
        assert len(zip_files) == 1
        zip_file = zip_files[0]
        assert zip_file.exists()

        # Raw folder should have been cleaned up
        raw_folders = [p for p in tmp_path.iterdir() if p.is_dir()]
        assert len(raw_folders) == 0

        # Progress should have reached 100.0%
        assert events[-1].status == "completed"
        assert events[-1].percentage == 100.0

        # Verify zipping status events exist
        zipping_events = [e for e in events if e.status == "zipping"]
        assert len(zipping_events) > 0


@pytest.mark.asyncio
async def test_backup_coordinator_restore_zip() -> None:
    """Verify that BackupCoordinator correctly unzips a source and restores from it."""
    inner_service = MockDriverService()
    coordinator = BackupCoordinator(inner_service)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Create a mock backup structure
        backup_folder = tmp_path / "DriverBackup_2026-07-02_120000"
        backup_folder.mkdir()
        dummy_file = backup_folder / "dummy.inf"
        dummy_file.write_text("dummy driver package content", encoding="utf-8")

        # Zip it up
        zip_path = tmp_path / "DriverBackup_2026-07-02_120000.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.write(dummy_file, arcname=f"{backup_folder.name}/dummy.inf")

        # Clean up raw folder to make sure restore unzips it
        shutil.rmtree(backup_folder)

        events = []
        async for progress in coordinator.restore(str(zip_path)):
            events.append(progress)

        # Check extracting progress and inner restore scaling
        extracting_events = [e for e in events if e.status == "extracting"]
        assert len(extracting_events) > 0
        assert extracting_events[0].percentage == 0.0

        assert events[-1].status == "completed"
        assert events[-1].percentage == 100.0

        # Verify scaled running progress event values (between 10% and 100%)
        running_events = [e for e in events if e.status == "running"]
        assert len(running_events) > 0
        for e in running_events:
            assert 10.0 <= e.percentage <= 100.0


@pytest.mark.asyncio
async def test_backup_coordinator_zip_failure(monkeypatch) -> None:
    """Verify that BackupCoordinator handles zipping failures gracefully."""
    inner_service = MockDriverService()
    coordinator = BackupCoordinator(inner_service, compress_to_zip=True, clean_raw_files=True)

    # Mock shutil.make_archive to raise an error and touch dummy file
    def mock_make_archive(*args, **kwargs) -> None:
        base_name = kwargs.get("base_name", args[0] if args else "")
        zip_file = Path(f"{base_name}.zip")
        zip_file.touch()
        raise RuntimeError("Disk full or permission denied")

    import shutil
    monkeypatch.setattr(shutil, "make_archive", mock_make_archive)

    with tempfile.TemporaryDirectory() as tmpdir:
        events = []
        async for progress in coordinator.backup(tmpdir):
            events.append(progress)

        assert events[-1].status == "failed"
        assert "Zipping failed" in events[-1].current_item
        assert "ZIP-ERROR" in events[-1].log_line

        # Ensure incomplete zip file was cleaned up
        tmp_path = Path(tmpdir)
        zip_files = list(tmp_path.glob("DriverBackup_*.zip"))
        assert len(zip_files) == 0


@pytest.mark.asyncio
async def test_backup_coordinator_restore_unzip_failure(monkeypatch) -> None:
    """Verify that BackupCoordinator handles zip extraction failures gracefully."""
    inner_service = MockDriverService()
    coordinator = BackupCoordinator(inner_service)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        zip_path = tmp_path / "corrupted_archive.zip"
        zip_path.write_text("corrupted zip content", encoding="utf-8")

        events = []
        async for progress in coordinator.restore(str(zip_path)):
            events.append(progress)

        assert events[-1].status == "failed"
        assert "Extraction failed" in events[-1].current_item
        assert "UNZIP-ERROR" in events[-1].log_line


@pytest.mark.asyncio
async def test_mock_driver_service_filtering() -> None:
    """Verify that MockDriverService filters out Microsoft drivers when third_party_only is True."""
    # When True (default)
    service_t = MockDriverService(third_party_only=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        events_t = []
        async for progress in service_t.backup(tmpdir):
            events_t.append(progress)
        running_t = [e for e in events_t if e.status == "running"]
        # Microsoft Print To PDF should be excluded, leaving 7 drivers
        assert len(running_t) == 7
        assert all("Microsoft Print To PDF" not in e.current_item for e in running_t)

    # When False
    service_f = MockDriverService(third_party_only=False)
    with tempfile.TemporaryDirectory() as tmpdir:
        events_f = []
        async for progress in service_f.backup(tmpdir):
            events_f.append(progress)
        running_f = [e for e in events_f if e.status == "running"]
        assert len(running_f) == 8
        assert any("Microsoft Print To PDF" in e.current_item for e in running_f)


@pytest.mark.asyncio
async def test_pnputil_enum_drivers_parsing(monkeypatch) -> None:
    """Verify that _backup_pnputil correctly parses and filters oem drivers."""
    from driver_backup.services.windows import WindowsDriverService
    from unittest.mock import AsyncMock
    import asyncio

    # Set up dummy PnPUtil output
    dummy_enum_output = (
        "Microsoft PnP Utility\r\n\r\n"
        "Published Name:     oem0.inf\r\n"
        "Original Name:      prnms001.inf\r\n"
        "Provider Name:      Microsoft\r\n"
        "Class Name:         Printers\r\n\r\n"
        "Published Name:     oem1.inf\r\n"
        "Original Name:      realtek.inf\r\n"
        "Provider Name:      Realtek Semiconductor Corp.\r\n"
        "Class Name:         Net\r\n"
    )

    dummy_export_output = "Exporting driver package:    oem1.inf\r\nDriver package successfully exported."

    # Create mock processes
    mock_enum_proc = AsyncMock()
    mock_enum_proc.returncode = 0
    mock_enum_proc.communicate.return_value = (dummy_enum_output.encode("cp437"), b"")

    mock_export_proc = AsyncMock()
    mock_export_proc.returncode = 0
    mock_export_proc.communicate.return_value = (dummy_export_output.encode("cp437"), b"")

    # Mock asyncio.create_subprocess_exec
    created_processes = []
    async def mock_create_subprocess_exec(*args, **kwargs):
        if "/enum-drivers" in args:
            proc = mock_enum_proc
        else:
            proc = mock_export_proc
        created_processes.append((args, kwargs))
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_create_subprocess_exec)

    service = WindowsDriverService(method="pnputil", third_party_only=True)
    monkeypatch.setattr(service, "is_supported", lambda: True)

    with tempfile.TemporaryDirectory() as tmpdir:
        events = []
        async for progress in service.backup(tmpdir):
            events.append(progress)

        enum_calls = [c for c in created_processes if "/enum-drivers" in c[0]]
        export_calls = [c for c in created_processes if "/export-driver" in c[0]]

        assert len(enum_calls) == 1
        assert len(export_calls) == 1
        assert "oem1.inf" in export_calls[0][0]
        assert "oem0.inf" not in [c[0][2] for c in export_calls]

        completed_event = events[-1]
        assert completed_event.status == "completed"


@pytest.mark.asyncio
async def test_backup_coordinator_writes_hardware_info_uncompressed() -> None:
    """Verify that hardware_info.txt is written inside the raw backup folder in uncompressed mode."""
    inner_service = MockDriverService()
    coordinator = BackupCoordinator(inner_service, compress_to_zip=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        events = []
        async for progress in coordinator.backup(tmpdir):
            events.append(progress)

        assert events[-1].status == "completed"

        tmp_path = Path(tmpdir)
        backup_folders = [p for p in tmp_path.iterdir() if p.is_dir()]
        assert len(backup_folders) == 1
        raw_path = backup_folders[0]

        info_file = raw_path / "hardware_info.txt"
        assert info_file.exists()

        content = info_file.read_text(encoding="utf-8")
        assert "OS Version:" in content
        assert "CPU:" in content
        assert "Motherboard:" in content
        assert "RAM:" in content
        assert "GPU:" in content


@pytest.mark.asyncio
async def test_backup_coordinator_writes_hardware_info_compressed() -> None:
    """Verify that hardware_info.txt is written and included in the resulting zip archive."""
    inner_service = MockDriverService()
    # clean_raw_files=False so we can inspect both raw_path and the zip
    coordinator = BackupCoordinator(inner_service, compress_to_zip=True, clean_raw_files=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        events = []
        async for progress in coordinator.backup(tmpdir):
            events.append(progress)

        assert events[-1].status == "completed"

        tmp_path = Path(tmpdir)
        zip_files = list(tmp_path.glob("*.zip"))
        assert len(zip_files) == 1
        zip_file = zip_files[0]

        # Read zip and verify hardware_info.txt is inside the archive
        with zipfile.ZipFile(zip_file, "r") as z:
            names = z.namelist()
            # The archive should contain the hardware_info.txt under the top folder
            hardware_info_in_zip = [n for n in names if n.endswith("hardware_info.txt")]
            assert len(hardware_info_in_zip) == 1

            # Verify contents of hardware_info.txt inside the zip
            content = z.read(hardware_info_in_zip[0]).decode("utf-8")
            assert "OS Version:" in content
            assert "CPU:" in content
            assert "Motherboard:" in content
            assert "RAM:" in content
            assert "GPU:" in content


@pytest.mark.asyncio
async def test_backup_coordinator_hardware_info_robustness_outer(monkeypatch) -> None:
    """Verify that backup completes successfully even if query functions themselves raise Exceptions."""
    import driver_backup.services.backup as backup_mod

    def raise_err(*args, **kwargs):
        raise RuntimeError("Query error")

    # Monkeypatch all query helper functions to raise Exceptions
    monkeypatch.setattr(backup_mod, "_get_os_info", raise_err)
    monkeypatch.setattr(backup_mod, "_get_cpu_info", raise_err)
    monkeypatch.setattr(backup_mod, "_get_motherboard_info", raise_err)
    monkeypatch.setattr(backup_mod, "_get_ram_info", raise_err)
    monkeypatch.setattr(backup_mod, "_get_gpu_info", raise_err)

    inner_service = MockDriverService()
    coordinator = BackupCoordinator(inner_service, compress_to_zip=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        events = []
        async for progress in coordinator.backup(tmpdir):
            events.append(progress)

        assert events[-1].status == "completed"


@pytest.mark.asyncio
async def test_backup_coordinator_hardware_info_robustness_internal(monkeypatch) -> None:
    """Verify that if internal API queries fail, helper functions return placeholders and file is written."""
    import driver_backup.services.backup as backup_mod

    # Force a mock setup where system returns Windows to exercise registry/ctypes logic
    monkeypatch.setattr(backup_mod.platform, "system", lambda: "Windows")
    monkeypatch.setattr(backup_mod.platform, "processor", lambda: "")

    # We mock winreg/ctypes or other calls to raise OS/attribute error to trigger inner try-except
    try:
        import winreg
        def raise_os_error(*args, **kwargs):
            raise OSError("Registry query failed")
        monkeypatch.setattr(winreg, "OpenKey", raise_os_error)
    except ImportError:
        pass

    import ctypes
    if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "kernel32"):
        monkeypatch.setattr(ctypes.windll.kernel32, "GlobalMemoryStatusEx", lambda *a, **kw: False)

    inner_service = MockDriverService()
    coordinator = BackupCoordinator(inner_service, compress_to_zip=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        events = []
        async for progress in coordinator.backup(tmpdir):
            events.append(progress)

        assert events[-1].status == "completed"

        tmp_path = Path(tmpdir)
        backup_folders = [p for p in tmp_path.iterdir() if p.is_dir()]
        assert len(backup_folders) == 1
        raw_path = backup_folders[0]

        info_file = raw_path / "hardware_info.txt"
        assert info_file.exists()

        content = info_file.read_text(encoding="utf-8")
        assert "OS Version:" in content
        assert "CPU: Unknown CPU" in content or "CPU:" in content
        assert "Motherboard: Unknown Motherboard" in content
        assert "RAM: Unknown RAM" in content
        assert "GPU: Unknown GPU" in content




