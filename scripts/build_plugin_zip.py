#!/usr/bin/env python3
"""Build a reproducible PyMOL Plugin Manager archive."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VERSION_TEXT = (ROOT / "pymol_plip" / "constants.py").read_text(encoding="utf-8")
VERSION = re.search(r'^PLUGIN_VERSION = "([^"]+)"', VERSION_TEXT, re.MULTILINE).group(1)
OUTPUT = ROOT / "dist" / f"PyMOL_Pose_Inspector-{VERSION}.zip"


def files_to_package() -> list[Path]:
    files = sorted((ROOT / "pymol_plip").rglob("*.py"))
    files.append(ROOT / "pymol_ligand_review.py")
    files.extend([ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "environment.yml"])
    return files


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in files_to_package():
            relative = source.relative_to(ROOT)
            info = zipfile.ZipInfo(str(relative), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source.read_bytes())
    print(OUTPUT)


if __name__ == "__main__":
    main()
