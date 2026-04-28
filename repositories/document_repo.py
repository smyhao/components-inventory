from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from models import InventoryError
from repositories.base import BaseRepository


class DocumentRepository(BaseRepository):
    def __init__(self, db_path: Path, file_logger: Any, upload_folder: Path | None = None) -> None:
        super().__init__(db_path)
        self.file_logger = file_logger
        self.upload_folder = Path(upload_folder) if upload_folder else None

    def _image_url(self, relative_path: str | None) -> str | None:
        if not relative_path:
            return None
        return "/uploads/" + relative_path.replace("\\", "/")

    def _file_url(self, relative_path: str | None) -> str | None:
        return self._image_url(relative_path)

    def _delete_image_files(self, rows: Iterable) -> None:
        if not self.upload_folder:
            return
        for row in rows:
            for key in ("path", "thumbnail_path"):
                relative = row[key]
                if not relative:
                    continue
                target = self.upload_folder / relative
                try:
                    if target.exists():
                        target.unlink()
                except OSError:
                    continue

    def _delete_document_files(self, rows: Iterable) -> None:
        if not self.upload_folder:
            return
        for row in rows:
            relative = row["path"]
            if not relative:
                continue
            target = self.upload_folder / relative
            try:
                if target.exists():
                    target.unlink()
            except OSError:
                continue

    def create_image_record(
        self,
        relative_path: str,
        thumbnail_path: str | None,
        component_id: int | None = None,
        is_primary: bool = False,
    ) -> dict[str, Any]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO images (component_id, path, thumbnail_path, is_primary)
                VALUES (?, ?, ?, ?)
                """,
                (component_id, relative_path, thumbnail_path, 1 if is_primary else 0),
            )
            image_id = cur.lastrowid
            if component_id and is_primary:
                conn.execute("UPDATE images SET is_primary = 0 WHERE component_id = ? AND id != ?", (component_id, image_id))
            row = self._fetchone(
                conn,
                "SELECT id, component_id, path, thumbnail_path, is_primary FROM images WHERE id = ?",
                (image_id,),
            )
        self.file_logger.write_backend("IMAGE", f"上传图片: 组件ID={component_id or '未绑定'}, 文件={relative_path}")
        return {
            "id": row["id"],
            "component_id": row["component_id"],
            "url": self._image_url(row["path"]),
            "thumbnail_url": self._image_url(row["thumbnail_path"]),
            "is_primary": bool(row["is_primary"]),
        }

    def delete_image(self, image_id: int) -> None:
        with self.connect() as conn:
            image = self._fetchone(
                conn,
                "SELECT id, component_id, path, thumbnail_path FROM images WHERE id = ?",
                (image_id,),
            )
            if not image:
                raise InventoryError("image not found")
            self._delete_image_files([image])
            conn.execute("DELETE FROM images WHERE id = ?", (image_id,))
        self.file_logger.write_backend("IMAGE", f"删除图片: ID={image_id}")

    def create_document_record(
        self,
        relative_path: str,
        original_name: str,
        mime_type: str | None,
        file_size: int,
        component_id: int | None = None,
    ) -> dict[str, Any]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO documents (component_id, path, original_name, mime_type, file_size)
                VALUES (?, ?, ?, ?, ?)
                """,
                (component_id, relative_path, original_name, mime_type, file_size),
            )
            document_id = cur.lastrowid
            row = self._fetchone(
                conn,
                "SELECT id, component_id, path, original_name, mime_type, file_size, created_at FROM documents WHERE id = ?",
                (document_id,),
            )
        self.file_logger.write_backend("COMPONENT", f"上传文档: 组件ID={component_id or '未绑定'}, 文件={original_name}")
        return {
            "id": row["id"],
            "component_id": row["component_id"],
            "name": row["original_name"],
            "url": self._file_url(row["path"]),
            "mime_type": row["mime_type"],
            "file_size": row["file_size"],
            "created_at": row["created_at"],
        }

    def delete_document(self, document_id: int) -> None:
        with self.connect() as conn:
            document = self._fetchone(
                conn,
                "SELECT id, component_id, path, original_name FROM documents WHERE id = ?",
                (document_id,),
            )
            if not document:
                raise InventoryError("document not found")
            self._delete_document_files([document])
            conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        self.file_logger.write_backend("COMPONENT", f"删除文档: ID={document_id}, 文件={document['original_name']}")
