#!/usr/bin/env python3
import tomllib
from pathlib import Path

def main() -> None:
    # Locate pyproject.toml
    root_dir = Path(__file__).parent.parent
    pyproject_path = root_dir / "pyproject.toml"
    output_path = root_dir / "file_version_info.txt"

    if not pyproject_path.exists():
        print(f"Error: {pyproject_path} not found.")
        sys.exit(1)

    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    project = data.get("project", {})
    name = project.get("name", "driver-backup")
    version_str = project.get("version", "0.1.0")
    description = project.get("description", "Driver Backup and Restore Utility")

    # Parse version_str to 4-tuple of integers
    # e.g. "0.1.0" -> (0, 1, 0, 0)
    version_parts = []
    for part in version_str.split("."):
        clean_part = "".join(c for c in part if c.isdigit())
        version_parts.append(int(clean_part) if clean_part else 0)
    while len(version_parts) < 4:
        version_parts.append(0)
    version_tuple = tuple(version_parts[:4])

    version_tuple_str = str(version_tuple)

    content = f"""# UTF-8
#
# For more details about fixed file info 'flags' see:
# https://docs.microsoft.com/en-us/windows/win32/api/winver/ns-winver-vs_fixedfileinfo
# For language IDs see:
# https://docs.microsoft.com/en-us/windows/win32/menurc/version-information-resource
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple_str},
    prodvers={version_tuple_str},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'Your Name'),
        StringStruct('FileDescription', '{description}'),
        StringStruct('FileVersion', '{version_str}'),
        StringStruct('InternalName', '{name}'),
        StringStruct('LegalCopyright', 'Copyright (c) 2026'),
        StringStruct('OriginalFilename', '{name}.exe'),
        StringStruct('ProductName', '{name.replace("-", " ").title()}'),
        StringStruct('ProductVersion', '{version_str}')])
      ]), 
    VarFileInfo([VarStruct('Translation', [0x409, 1200])])
  ]
)
"""
    output_path.write_text(content, encoding="utf-8")
    print(f"Generated PyInstaller version info file at: {output_path} with version {version_str}")

if __name__ == "__main__":
    import sys
    main()
