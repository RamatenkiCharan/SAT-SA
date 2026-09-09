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


def parse_raw_payload(
    contents: bytes,
    filename: str,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """
    Parses uploaded raw bytes (CSV or JSON) into a standard raw_bundle dictionary.
    Supports single-table alert CSVs and multi-entity JSON packs.
    """
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise IngestionValidationError(
            f"Unsupported file format '{ext}'. Only .csv and .json files are supported."
        )

    if len(contents) > _MAX_FILE_SIZE_BYTES:
        raise IngestionValidationError(f"File exceeds maximum size of {_MAX_FILE_SIZE_BYTES} bytes.")

    warnings: list[str] = []
    text = contents.decode("utf-8-sig", errors="replace")

    if ext == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise IngestionValidationError(f"Malformed JSON: {exc}") from exc

        if isinstance(data, dict):
            # Already a bundle or single object
            if "alerts" in data or "cse" in data or "assets" in data:
                return data, warnings
            return {"alerts": [data]}, warnings
        elif isinstance(data, list):
            # Array of alert records
            return {"alerts": data}, warnings
        else:
            raise IngestionValidationError("Top-level JSON must be an object or an array of objects.")

    elif ext == ".csv":
        import io
        f = io.StringIO(text)
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise IngestionValidationError("CSV has no header row.")

        rows: list[dict[str, Any]] = []
        for i, row in enumerate(reader):
            if None in row:
                warnings.append(f"Row {i}: excess columns mapped under None.")
            rows.append(row)

        return {"alerts": rows}, warnings

    return {"alerts": []}, warnings
