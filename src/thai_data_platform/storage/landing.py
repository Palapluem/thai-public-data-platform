"""Safe local-first raw landing."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from thai_data_platform.ingestion.metadata import sha256_file


@dataclass(frozen=True)
class LandedFile:
    dataset_name: str
    path: Path
    sha256: str


def land_file(source_path: str | Path, dataset_name: str, raw_root: str | Path) -> LandedFile:
    """Copy a source file without overwriting a different release at the same name."""
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError(source)
    if not re.fullmatch(r"[a-z0-9_]+", dataset_name):
        raise ValueError(f"Unsafe dataset name: {dataset_name!r}")

    source_hash = sha256_file(source)
    target_dir = Path(raw_root) / dataset_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if target.exists():
        if sha256_file(target) != source_hash:
            target = target_dir / f"{source.stem}.{source_hash[:12]}{source.suffix}"
        elif target.resolve() == source.resolve():
            return LandedFile(dataset_name, target, source_hash)
    if not target.exists():
        shutil.copy2(source, target)
    return LandedFile(dataset_name, target, source_hash)
