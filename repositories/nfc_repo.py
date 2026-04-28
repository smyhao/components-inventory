from __future__ import annotations

from pathlib import Path
from typing import Any

from models import InventoryError, clean_text
from repositories.base import BaseRepository
from repositories.box_repo import BoxRepository


class NfcRepository(BaseRepository):
    def __init__(self, db_path: Path, file_logger: Any, box_repo: BoxRepository) -> None:
        super().__init__(db_path)
        self.file_logger = file_logger
        self.box_repo = box_repo

    def bind_nfc(self, box_id: int, uid: str) -> dict[str, Any]:
        uid = clean_text(uid).upper()
        if not uid:
            raise InventoryError("UID 不能为空")
        with self.connect() as conn:
            box = self._fetchone(conn, "SELECT id, name, nfc_uid FROM boxes WHERE id = ?", (box_id,))
            if not box:
                raise InventoryError("收纳盒不存在")
            existing = self._fetchone(conn, "SELECT id FROM boxes WHERE nfc_uid = ?", (uid,))
            if existing and existing["id"] != box_id:
                raise InventoryError("该 UID 已绑定其他收纳盒")
            conn.execute("UPDATE boxes SET nfc_uid = ? WHERE id = ?", (uid, box_id))
        self.file_logger.write_backend("NFC", f"绑定 NFC: 盒子ID={box_id}, UID={uid}")
        return {"box_id": box_id, "uid": uid}

    def get_nfc_payload(self, box_id: int, server_url: str) -> dict[str, Any]:
        box = self.box_repo.get_box(box_id)
        url = f"{server_url.rstrip('/')}/box/{box_id}"
        text = f"{box['name']} | {box['rows']}x{box['cols']} | {box['occupied_count']}/{box['total_slots']}"
        self.file_logger.write_backend("NFC", f"生成 NDEF 内容: 盒子ID={box_id}")
        return {"box_id": box_id, "url": url, "text": text}

    def lookup_nfc(self, uid: str) -> dict[str, Any]:
        uid = clean_text(uid).upper()
        with self.connect() as conn:
            box = self._fetchone(conn, "SELECT id FROM boxes WHERE nfc_uid = ?", (uid,))
        if not box:
            raise InventoryError("no box is bound to this uid")
        return {
            "box": self.box_repo.get_box(box["id"]),
            "grid": self.box_repo.get_box_grid(box["id"]),
        }
