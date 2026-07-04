import ctypes
import platform
import sys


def is_admin() -> bool:
    """Check if the current process is running with administrator privileges.

    Returns True on non-Windows platforms to facilitate mock testing.
    """
    if platform.system() != "Windows":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate_privileges() -> None:
    """Relaunch the script with administrator privileges (UAC prompt on Windows).

    If successful, this function exits the current process.
    """
    if platform.system() != "Windows":
        return

    is_frozen = getattr(sys, "frozen", False)

    if is_frozen:
        # If compiled with PyInstaller, relaunch the executable directly
        script = sys.executable
        params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
    else:
        # If running as standard python, relaunch python interpreter with script path
        script = sys.executable
        params = f'"{sys.argv[0]}" ' + " ".join(f'"{arg}"' for arg in sys.argv[1:])

    try:
        # Run standard ShellExecuteW with 'runas' verb
        # 1 means SW_SHOWNORMAL
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", script, params, None, 1
        )
        if int(ret) > 32:
            sys.exit(0)
    except Exception:
        # Let the caller handle the failure to elevate
        pass
