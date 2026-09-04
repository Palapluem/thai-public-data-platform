"""Source identity and pipeline run metadata."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def new_run_id() -> str:
    return str(uuid.uuid4())


def sha256_file(path: str | Path) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass(frozen=True)
class SourceFileMetadata:
    dataset_name: str
    source_name: str
    path: Path
    sha256: str
    source_page_url: str | None = None
    file_url: str | None = None
    fiscal_year: int | None = None
    fiscal_year_be: int | None = None
    as_of_date: str | None = None

    @classmethod
    def from_file(
        cls,
        *,
        dataset_name: str,
        source_name: str,
        path: str | Path,
        source_page_url: str | None = None,
        file_url: str | None = None,
        fiscal_year: int | None = None,
        fiscal_year_be: int | None = None,
        as_of_date: str | None = None,
    ) -> SourceFileMetadata:
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        return cls(
            dataset_name=dataset_name,
            source_name=source_name,
            path=file_path,
            sha256=sha256_file(file_path),
            source_page_url=source_page_url,
            file_url=file_url,
            fiscal_year=fiscal_year,
            fiscal_year_be=fiscal_year_be,
            as_of_date=as_of_date,
        )

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def file_size_bytes(self) -> int:
        return self.path.stat().st_size

    def as_dict(self) -> dict[str, object]:
        return {
            "dataset_name": self.dataset_name,
            "source_name": self.source_name,
            "filename": self.filename,
            "path": str(self.path),
            "sha256": self.sha256,
            "source_page_url": self.source_page_url,
            "file_url": self.file_url,
            "fiscal_year": self.fiscal_year,
            "fiscal_year_be": self.fiscal_year_be,
            "as_of_date": self.as_of_date,
            "file_size_bytes": self.file_size_bytes,
        }
