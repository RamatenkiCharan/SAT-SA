"""
Ingestion service - SRS §7.1 (FR-001 through FR-005).

Scope for P0-A (deliberately narrow, per SRS v2.0 tiering):
  - CSV / JSON only (FR-002). No DB/API ingestion in P0 - that's P2.
  - Every import creates a NEW dataset_version row. Never UPDATE an existing
    dataset_version's source columns (§53 Immutability Principle).
  - Provenance (source file id, import time, transformation version, schema
    version) is stored on the dataset_version row, not scattered elsewhere
    (FR-005).
  - This module does NOT do canonicalization or data-quality scoring - those
    are separate stages (analytics/canonicalization, analytics/data_quality)
    per the layered pipeline in every project doc. Keep this module's job to
    exactly one thing: safely land a versioned, provenance-tagged raw import.

Explicitly OUT of scope here (do not add speculatively):
  - Duplicate detection (FR-006, P1)
  - Incremental processing semantics beyond "new version doesn't destroy old
    ones" (FR-007, P1 - already respected structurally by versioning)
"""
from __future__ import annotations

import csv
import json
import mimetypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

# Hackathon security baseline (SRS §15.1): strict file validation on upload.
_ALLOWED_EXTENSIONS = {".csv", ".json"}
_MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024  # 200MB ceiling for the prototype; not a claimed scale target.


class IngestionValidationError(ValueError):
    """Raised on malformed/oversized/wrong-type uploads. Never silently
    coerce a bad file into an empty-but-'successful' import (AGENTS.md §52)."""


@dataclass(frozen=True)
class DatasetVersionRecord:
    dataset_version_id: UUID
    dataset_id: UUID
    version_number: int
    source_file_ref: str
    import_time: datetime
    transformation_version: str
    schema_version: str


@dataclass(frozen=True)
class RawImportResult:
    dataset_version: DatasetVersionRecord
    row_count: int
    parse_warnings: list[str]


def _validate_file(path: Path) -> None:
    if not path.exists():
        raise IngestionValidationError(f"File not found: {path}")
    if path.suffix.lower() not in _ALLOWED_EXTENSIONS:
        raise IngestionValidationError(
            f"Unsupported file type '{path.suffix}'. Only {_ALLOWED_EXTENSIONS} are accepted in P0 (FR-002)."
        )
    size = path.stat().st_size
    if size > _MAX_FILE_SIZE_BYTES:
        raise IngestionValidationError(
            f"File exceeds size limit ({size} > {_MAX_FILE_SIZE_BYTES} bytes)."
        )
    if ".." in str(path) or not path.is_absolute():
        # Basic path-traversal guard; the API layer should already have
        # resolved this to a controlled upload directory before calling here.
        raise IngestionValidationError("Refusing relative/suspicious path; resolve to an absolute, sandboxed path first.")


def _parse_csv(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise IngestionValidationError("CSV has no header row - cannot map to canonical schema.")
        for i, row in enumerate(reader):
            if None in row:  # extra unmapped columns DictReader stuffs under key None
                warnings.append(f"Row {i}: more columns than header - malformed row.")
            rows.append(row)
    return rows, warnings


def _parse_json(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    with path.open(encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise IngestionValidationError(f"Malformed JSON: {exc}") from exc
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise IngestionValidationError("Top-level JSON must be an object or an array of objects.")
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            warnings.append(f"Item {i}: not an object - skipped during row parsing, will show as missing.")
    rows = [item for item in data if isinstance(item, dict)]
    return rows, warnings


def ingest_raw_file(
    path: Path,
    dataset_id: UUID,
    next_version_number: int,
    transformation_version: str = "T1",
    schema_version: str = "S1",
) -> RawImportResult:
    """
    Land a single raw source file as a new, immutable dataset_version.

    `next_version_number` must be supplied by the caller after looking up
    the current max version for `dataset_id` (kept explicit here rather than
    computed internally, so the repository layer - which actually talks to
    Postgres - owns the single source of truth for "what's the next version").
    """
    _validate_file(path)

    if path.suffix.lower() == ".csv":
        rows, warnings = _parse_csv(path)
    else:
        rows, warnings = _parse_json(path)

    dataset_version = DatasetVersionRecord(
        dataset_version_id=uuid4(),
        dataset_id=dataset_id,
        version_number=next_version_number,
        source_file_ref=str(path),
        import_time=datetime.now(timezone.utc),
        transformation_version=transformation_version,
        schema_version=schema_version,
    )

    return RawImportResult(
        dataset_version=dataset_version,
        row_count=len(rows),
        parse_warnings=warnings,
    )
