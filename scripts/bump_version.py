#!/usr/bin/env python3
import sys
import re
from pathlib import Path

def get_current_version(toml_path: Path) -> str:
    content = toml_path.read_text(encoding="utf-8")
    in_project = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("[project]"):
            in_project = True
        elif stripped.startswith("[") and stripped.endswith("]"):
            in_project = False
        
        if in_project and stripped.startswith("version"):
            match = re.search(r'version\s*=\s*"([^"]+)"', stripped)
            if match:
                return match.group(1)
    return "0.1.0"

def update_version_in_toml(toml_path: Path, new_version: str) -> None:
    content = toml_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    updated = False
    in_project = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[project]"):
            in_project = True
        elif stripped.startswith("[") and stripped.endswith("]"):
            in_project = False
        
        if in_project and stripped.startswith("version"):
            lines[i] = f'version = "{new_version}"'
            updated = True
            break
            
    if updated:
        toml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main() -> None:
    root_dir = Path(__file__).parent.parent
    toml_path = root_dir / "pyproject.toml"
    dist_dir = root_dir / "dist"
    temp_file = root_dir / ".version_temp"

    current_version = get_current_version(toml_path)

    # Check if any executables exist in dist
    has_existing_build = False
    if dist_dir.exists():
        for item in dist_dir.iterdir():
            if item.is_file() and item.name.startswith("driver-backup-"):
                has_existing_build = True
                break

    new_version = current_version
    if has_existing_build:
        print(f"\nUn ejecutable previo ya existe en 'dist/'. (Versión actual: {current_version})")
        print("Seleccioná el tipo de incremento de versión para la nueva build:")
        print("1) Bug Fix / Patch (ej. 0.1.0 -> 0.1.1)")
        print("2) Minor Fix / Minor Release (ej. 0.1.0 -> 0.2.0)")
        print("3) Major Fix / Major Release (ej. 0.1.0 -> 1.0.0)")
        print("4) Mantener versión actual (ej. 0.1.0)")
        
        try:
            choice = input("Opción (1-4) [4]: ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "4"

        if choice in ("1", "2", "3"):
            parts = current_version.split(".")
            # Ensure we have 3 digits
            while len(parts) < 3:
                parts.append("0")
            
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

            if choice == "1":
                patch += 1
            elif choice == "2":
                minor += 1
                patch = 0
            elif choice == "3":
                major += 1
                minor = 0
                patch = 0

            new_version = f"{major}.{minor}.{patch}"
            update_version_in_toml(toml_path, new_version)
            print(f"Versión actualizada exitosamente: {current_version} -> {new_version}")

    # Write the final version to a temp file for the calling script to consume
    temp_file.write_text(new_version, encoding="utf-8")

if __name__ == "__main__":
    main()
