from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

from models import now_text


def image_url(relative_path: str | None) -> str | None:
    if not relative_path:
        return None
    return "/uploads/" + relative_path.replace("\\", "/")


def file_url(relative_path: str | None) -> str | None:
    return image_url(relative_path)


def delete_files(upload_folder: Path | None, rows: Iterable, keys: tuple[str, ...] = ("path",)) -> None:
    if not upload_folder:
        return
    for row in rows:
        for key in keys:
            relative = row[key]
            if not relative:
                continue
            target = upload_folder / relative
            try:
                if target.exists():
                    target.unlink()
            except OSError:
                continue


def append_stock_log(
    conn: sqlite3.Connection,
    component_id: int,
    change: int,
    quantity_after: int,
    log_type: str,
    reason: str,
) -> None:
    conn.execute(
        """
        INSERT INTO stock_logs (component_id, type, change, quantity_after, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (component_id, log_type, change, quantity_after, reason, now_text()),
    )
