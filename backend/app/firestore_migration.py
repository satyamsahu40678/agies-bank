"""Copy the SQLite application tables to Firestore without modifying the source."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.schema import Table

from . import models as _models
from .config import ROOT
from .db import Base


BATCH_SIZE = 400
DEFAULT_SOURCE = ROOT / "data" / "aegis.db"


def _encode(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _encode(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported Firestore migration value: {type(value).__name__}")


def _source_engine(source: Path) -> Engine:
    path = source.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError("The SQLite source database does not exist.")
    uri_path = quote(path.as_posix(), safe="/")
    return create_engine(f"sqlite:///file:{uri_path}?mode=ro&uri=true")


def _validate_source(engine: Engine) -> None:
    from sqlalchemy import inspect

    existing = set(inspect(engine).get_table_names())
    missing = sorted(
        table.name
        for table in Base.metadata.sorted_tables
        if table.name not in existing
    )
    if missing:
        raise RuntimeError(
            "The SQLite source is missing application tables; migrate it before export."
        )
    with engine.connect() as connection:
        violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(
            "The SQLite source has foreign-key violations; resolve them before export."
        )


def _primary_key(table: Table):
    columns = list(table.primary_key.columns)
    if len(columns) != 1:
        raise RuntimeError(
            f"Firestore migration requires a single-column primary key for {table.name}."
        )
    return columns[0]


def _record_rows(connection, table: Table):
    primary_key = _primary_key(table)
    statement = select(table).order_by(primary_key)
    for row in connection.execute(statement).mappings():
        document_id = str(row[primary_key.name])
        values = {column.name: _encode(row[column.name]) for column in table.columns}
        values["_aegis_schema_version"] = 1
        yield document_id, values


def migrate_sqlite_to_firestore(
    source: Path,
    client: Any | None = None,
    *,
    apply: bool = False,
) -> dict[str, dict[str, int]]:
    """Report row counts or import rows, skipping identical documents and refusing conflicts."""
    if apply and client is None:
        raise ValueError("A Firestore client is required when applying the import.")
    engine = _source_engine(source)
    try:
        _validate_source(engine)
        results: dict[str, dict[str, int]] = {}
        with engine.connect() as connection:
            for table in Base.metadata.sorted_tables:
                source_count = 0
                written = 0
                skipped = 0
                batch = client.batch() if apply else None
                batch_size = 0
                for document_id, values in _record_rows(connection, table):
                    source_count += 1
                    if not apply:
                        continue
                    reference = client.collection(table.name).document(document_id)
                    existing = reference.get()
                    if existing.exists:
                        if existing.to_dict() != values:
                            raise RuntimeError(
                                f"Firestore migration conflict in collection {table.name}; refusing to overwrite."
                            )
                        skipped += 1
                        continue
                    if batch is None:
                        raise RuntimeError("Firestore migration batch was not initialized.")
                    batch.set(reference, values)
                    batch_size += 1
                    written += 1
                    if batch_size == BATCH_SIZE:
                        batch.commit()
                        batch = client.batch()
                        batch_size = 0
                if apply and batch_size:
                    batch.commit()
                if apply:
                    target_count = sum(
                        1 for _ in client.collection(table.name).stream()
                    )
                    if target_count != source_count:
                        raise RuntimeError(
                            f"Firestore migration verification failed for collection {table.name}."
                        )
                results[table.name] = {
                    "source": source_count,
                    "written": written,
                    "skipped_identical": skipped,
                }
        return results
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="SQLite database to copy (read-only); defaults to backend/data/aegis.db.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write missing documents to Firestore; without this flag only inspect SQLite.",
    )
    parser.add_argument(
        "--project",
        default="",
        help="Firestore project ID; defaults to GOOGLE_CLOUD_PROJECT.",
    )
    parser.add_argument(
        "--database",
        default="",
        help="Firestore database ID; defaults to FIRESTORE_DATABASE or (default).",
    )
    args = parser.parse_args()
    if args.apply:
        import os

        from google.cloud import firestore

        project = args.project.strip() or os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
        database = (
            args.database.strip()
            or os.getenv("FIRESTORE_DATABASE", "(default)").strip()
            or "(default)"
        )
        if not project:
            parser.error("--project or GOOGLE_CLOUD_PROJECT is required with --apply.")
        client = firestore.Client(project=project, database=database)
    else:
        client = None
    results = migrate_sqlite_to_firestore(args.source, client, apply=args.apply)
    total = sum(item["source"] for item in results.values())
    action = "Imported and verified" if args.apply else "Dry run found"
    print(f"{action} {total} rows in {len(results)} application collections.")
    for collection, result in results.items():
        print(
            f"{collection}: source={result['source']} "
            f"written={result['written']} skipped_identical={result['skipped_identical']}"
        )


if __name__ == "__main__":
    main()
