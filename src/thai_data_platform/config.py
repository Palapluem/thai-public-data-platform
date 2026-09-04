"""Project configuration loaded from public, non-secret repository metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thai_data_platform.ingestion.metadata import SourceFileMetadata


@dataclass(frozen=True)
class SourceDefinition:
    source_name: str
    dataset_name: str
    source_page_url: str
    baseline_path: Path
    fiscal_year: int | None
    fiscal_year_be: int | None
    as_of_date: str | None
    sha256: str
    expected_parsed_rows: int | None


def load_source_definitions(
    manifest_path: str | Path = "config/source_manifest.json",
) -> dict[str, SourceDefinition]:
    path = Path(manifest_path)
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    definitions: dict[str, SourceDefinition] = {}
    for dataset_name, item in payload.get("sources", {}).items():
        definitions[dataset_name] = SourceDefinition(
            source_name=str(item["source_name"]),
            dataset_name=dataset_name,
            source_page_url=str(item["source_page_url"]),
            baseline_path=Path(str(item["path"])),
            fiscal_year=item.get("fiscal_year"),
            fiscal_year_be=item.get("fiscal_year_be"),
            as_of_date=item.get("as_of_date"),
            sha256=str(item["sha256"]),
            expected_parsed_rows=item.get("expected_parsed_rows"),
        )
    return definitions


def source_metadata(
    dataset_name: str,
    path: str | Path,
    manifest_path: str | Path = "config/source_manifest.json",
) -> SourceFileMetadata:
    definitions = load_source_definitions(manifest_path)
    try:
        definition = definitions[dataset_name]
    except KeyError as exc:
        raise KeyError(f"No source definition for {dataset_name}") from exc
    return SourceFileMetadata.from_file(
        dataset_name=definition.dataset_name,
        source_name=definition.source_name,
        path=path,
        source_page_url=definition.source_page_url,
        fiscal_year=definition.fiscal_year,
        fiscal_year_be=definition.fiscal_year_be,
        as_of_date=definition.as_of_date,
    )


def expected_row_counts(
    sources: list[SourceFileMetadata],
    manifest_path: str | Path = "config/source_manifest.json",
) -> dict[str, int]:
    """Return baseline row expectations only when the content hash is identical."""
    definitions = load_source_definitions(manifest_path)
    return {
        source.dataset_name: int(definition.expected_parsed_rows)
        for source in sources
        if (definition := definitions.get(source.dataset_name))
        and definition.sha256 == source.sha256
        and definition.expected_parsed_rows
    }
