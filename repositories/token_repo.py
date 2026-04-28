from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path
from typing import Any

from models import InventoryError, clean_text, now_text
from repositories.base import BaseRepository


class TokenRepository(BaseRepository):
    def __init__(self, db_path: Path, file_logger: Any) -> None:
        super().__init__(db_path)
        self.file_logger = file_logger

    def _token_hash(self, token: str) -> str:
        return hashlib.sha256(clean_text(token).encode("utf-8")).hexdigest()

    def has_api_tokens(self) -> bool:
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT COUNT(*) AS cnt FROM api_tokens")
            return bool(row and row["cnt"] > 0)

    def validate_api_token(self, token: str) -> dict[str, Any] | None:
        token_hash = self._token_hash(token)
        with self.connect() as conn:
            rows = self._fetchall(
                conn,
                "SELECT id, name, token_hash FROM api_tokens WHERE active = 1",
            )
            matched = None
            for row in rows:
                if hmac.compare_digest(row["token_hash"], token_hash):
                    matched = row
                    break
            if not matched:
                return None
            conn.execute("UPDATE api_tokens SET last_used_at = ? WHERE id = ?", (now_text(), matched["id"]))
            return {"id": matched["id"], "name": matched["name"]}

    def list_api_tokens(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(
                conn,
                """
                SELECT id, name, token_prefix, created_at, last_used_at, active
                FROM api_tokens
                WHERE active = 1
                ORDER BY id DESC
                """,
            )
            return [dict(row) for row in rows]

    def create_api_token(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = clean_text(payload.get("name"))
        if not name:
            raise InventoryError("token name is required")
        token = "ci_" + secrets.token_urlsafe(32)
        token_hash = self._token_hash(token)
        token_prefix = token[:10]
        with self.connect() as conn:
            existing = self._fetchone(conn, "SELECT id FROM api_tokens WHERE name = ?", (name,))
            if existing:
                raise InventoryError("token name already exists")
            cur = conn.execute(
                """
                INSERT INTO api_tokens (name, token_hash, token_prefix, created_at, active)
                VALUES (?, ?, ?, ?, 1)
                """,
                (name, token_hash, token_prefix, now_text()),
            )
            token_id = cur.lastrowid
        self.file_logger.write_backend("SYSTEM", f"create api token: name={name}, id={token_id}")
        return {
            "id": token_id,
            "name": name,
            "token": token,
            "token_prefix": token_prefix,
        }

    def delete_api_token(self, token_id: int) -> None:
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT id, name FROM api_tokens WHERE id = ?", (token_id,))
            if not row:
                raise InventoryError("token not found")
            deleted_name = f"{row['name']}#deleted-{token_id}"
            conn.execute(
                "UPDATE api_tokens SET active = 0, name = ? WHERE id = ?",
                (deleted_name, token_id),
            )
        self.file_logger.write_backend("SYSTEM", f"delete api token: name={row['name']}, id={token_id}")
