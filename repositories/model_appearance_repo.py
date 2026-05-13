from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from werkzeug.datastructures import FileStorage

from models import InventoryError, clean_text, now_text
from repositories._utils import file_url
from repositories.base import BaseRepository


MODEL_TYPES = {"cabinet_layer", "cabinet_base", "cabinet_top", "box_cell", "box_frame"}
STRUCTURE_TYPES = {"open_shelf", "drawer_cabinet"}

SCRIPT_MODEL_TYPE = {
    "cabinet_base": "cabinet-base",
    "cabinet_top": "cabinet-top",
    "box_cell": "box-cell",
    "box_frame": "box-frame",
}


def _load_glb_checker():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_glb_model.py"
    spec = importlib.util.spec_from_file_location("inventory_check_glb_model", script_path)
    if not spec or not spec.loader:
        raise InventoryError("GLB 检查脚本不可用")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _clean_float(value: Any, default: float | None = None) -> float | None:
    if value in (None, "", "null"):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_positive_float(value: Any, default: float) -> float:
    parsed = _clean_float(value, default)
    if parsed is None or parsed <= 0:
        raise InventoryError("尺寸必须大于 0")
    return parsed


def _asset_summary(row: Any | None, prefix: str = "") -> dict[str, Any] | None:
    if not row or row[f"{prefix}id"] is None:
        return None
    item = {
        "id": row[f"{prefix}id"],
        "name": row[f"{prefix}name"],
        "type": row[f"{prefix}type"],
        "file_path": row[f"{prefix}file_path"],
        "url": file_url(row[f"{prefix}file_path"]),
        "width_mm": row[f"{prefix}width_mm"],
        "height_mm": row[f"{prefix}height_mm"],
        "depth_mm": row[f"{prefix}depth_mm"],
    }
    return item


class ModelAppearanceRepository(BaseRepository):
    def __init__(self, db_path: Path, file_logger: Any, upload_folder: Path | None = None) -> None:
        super().__init__(db_path)
        self.file_logger = file_logger
        self.upload_folder = Path(upload_folder) if upload_folder else None

    # ------------------------------------------------------------------
    # Model assets
    # ------------------------------------------------------------------

    def list_model_assets(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(conn, "SELECT * FROM model_assets ORDER BY created_at DESC, id DESC")
            return [self._asset_to_dict(row) for row in rows]

    def get_model_asset(self, asset_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT * FROM model_assets WHERE id = ?", (asset_id,))
            if not row:
                raise InventoryError("模型不存在")
            return self._asset_to_dict(row)

    def create_model_asset_from_upload(self, file: FileStorage, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.upload_folder:
            raise InventoryError("上传目录未配置")
        if not file or not file.filename:
            raise InventoryError("missing upload file")
        original_name = Path(file.filename).name
        if Path(original_name).suffix.lower() != ".glb":
            raise InventoryError("第一版模型库只支持 .glb 文件")

        model_type = self._clean_model_type(payload.get("type"))
        name = clean_text(payload.get("name")) or Path(original_name).stem
        width_mm = _clean_float(payload.get("width_mm"))
        height_mm = _clean_float(payload.get("height_mm"))
        depth_mm = _clean_float(payload.get("depth_mm"))

        target_dir = self.upload_folder / "model_assets"
        target_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}.glb"
        target = target_dir / stored_name
        file.save(target)
        relative_path = str(Path("model_assets") / stored_name)
        file_size = target.stat().st_size

        report = self._inspect_glb(target, model_type)
        now = now_text()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO model_assets (
                    name, type, file_path, original_name, file_size, unit,
                    width_mm, height_mm, depth_mm, node_report_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'mm', ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    model_type,
                    relative_path,
                    original_name,
                    file_size,
                    width_mm,
                    height_mm,
                    depth_mm,
                    json.dumps(report, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            asset_id = cur.lastrowid
        self.file_logger.write_backend("3D", f"上传 GLB 模型: ID={asset_id}, name={name}, type={model_type}")
        return self.get_model_asset(asset_id)

    def update_model_asset(self, asset_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            existing = self._fetchone(conn, "SELECT * FROM model_assets WHERE id = ?", (asset_id,))
            if not existing:
                raise InventoryError("模型不存在")
            model_type = self._clean_model_type(payload.get("type")) if "type" in payload else existing["type"]
            name = clean_text(payload.get("name")) or existing["name"]
            width_mm = _clean_float(payload.get("width_mm"), existing["width_mm"])
            height_mm = _clean_float(payload.get("height_mm"), existing["height_mm"])
            depth_mm = _clean_float(payload.get("depth_mm"), existing["depth_mm"])
            report = existing["node_report_json"]
            if model_type != existing["type"]:
                target = self._asset_path(existing["file_path"])
                report = json.dumps(self._inspect_glb(target, model_type), ensure_ascii=False)
            conn.execute(
                """
                UPDATE model_assets
                SET name = ?, type = ?, width_mm = ?, height_mm = ?, depth_mm = ?,
                    node_report_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, model_type, width_mm, height_mm, depth_mm, report, now_text(), asset_id),
            )
        self.file_logger.write_backend("3D", f"更新模型: ID={asset_id}, name={name}, type={model_type}")
        return self.get_model_asset(asset_id)

    def delete_model_asset(self, asset_id: int) -> None:
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT * FROM model_assets WHERE id = ?", (asset_id,))
            if not row:
                raise InventoryError("模型不存在")
            if self._asset_reference_count(conn, asset_id) > 0:
                raise InventoryError("模型正在被模板引用，无法删除")
            conn.execute("DELETE FROM model_assets WHERE id = ?", (asset_id,))
        target = self._asset_path(row["file_path"])
        try:
            if target.exists():
                target.unlink()
        except OSError:
            pass
        self.file_logger.write_backend("3D", f"删除模型: ID={asset_id}, name={row['name']}")

    # ------------------------------------------------------------------
    # Cabinet templates
    # ------------------------------------------------------------------

    def list_cabinet_templates(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(conn, self._cabinet_template_sql("ORDER BY ct.name"))
            return [self._cabinet_template_to_dict(row) for row in rows]

    def get_cabinet_template(self, template_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = self._fetchone(conn, self._cabinet_template_sql("WHERE ct.id = ?"), (template_id,))
            if not row:
                raise InventoryError("柜体模板不存在")
            return self._cabinet_template_to_dict(row)

    def create_cabinet_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._clean_cabinet_template_payload(payload)
        now = now_text()
        with self.connect() as conn:
            self._validate_cabinet_template_assets(conn, data)
            cur = conn.execute(
                """
                INSERT INTO cabinet_templates (
                    name, structure_type, layer_model_asset_id, base_model_asset_id, top_model_asset_id,
                    layer_height_mm, pull_axis, pull_distance_mm,
                    slot_offset_x_mm, slot_offset_y_mm, slot_offset_z_mm, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["name"],
                    data["structure_type"],
                    data["layer_model_asset_id"],
                    data["base_model_asset_id"],
                    data["top_model_asset_id"],
                    data["layer_height_mm"],
                    data["pull_axis"],
                    data["pull_distance_mm"],
                    data["slot_offset_x_mm"],
                    data["slot_offset_y_mm"],
                    data["slot_offset_z_mm"],
                    now,
                    now,
                ),
            )
            template_id = cur.lastrowid
        self.file_logger.write_backend("3D", f"创建柜体模板: ID={template_id}, name={data['name']}")
        return self.get_cabinet_template(template_id)

    def update_cabinet_template(self, template_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            existing = self._fetchone(conn, "SELECT * FROM cabinet_templates WHERE id = ?", (template_id,))
            if not existing:
                raise InventoryError("柜体模板不存在")
            merged = dict(existing)
            merged.update(payload)
            data = self._clean_cabinet_template_payload(merged)
            self._validate_cabinet_template_assets(conn, data)
            conn.execute(
                """
                UPDATE cabinet_templates
                SET name = ?, structure_type = ?, layer_model_asset_id = ?, base_model_asset_id = ?,
                    top_model_asset_id = ?, layer_height_mm = ?, pull_axis = ?, pull_distance_mm = ?,
                    slot_offset_x_mm = ?, slot_offset_y_mm = ?, slot_offset_z_mm = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    data["name"],
                    data["structure_type"],
                    data["layer_model_asset_id"],
                    data["base_model_asset_id"],
                    data["top_model_asset_id"],
                    data["layer_height_mm"],
                    data["pull_axis"],
                    data["pull_distance_mm"],
                    data["slot_offset_x_mm"],
                    data["slot_offset_y_mm"],
                    data["slot_offset_z_mm"],
                    now_text(),
                    template_id,
                ),
            )
        self.file_logger.write_backend("3D", f"更新柜体模板: ID={template_id}, name={data['name']}")
        return self.get_cabinet_template(template_id)

    def delete_cabinet_template(self, template_id: int) -> None:
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT * FROM cabinet_templates WHERE id = ?", (template_id,))
            if not row:
                raise InventoryError("柜体模板不存在")
            used = self._fetchone(conn, "SELECT COUNT(*) AS cnt FROM cabinets WHERE template_id = ?", (template_id,))
            if used and used["cnt"] > 0:
                raise InventoryError("柜体模板正在被柜子引用，无法删除")
            conn.execute("DELETE FROM cabinet_templates WHERE id = ?", (template_id,))
        self.file_logger.write_backend("3D", f"删除柜体模板: ID={template_id}, name={row['name']}")

    # ------------------------------------------------------------------
    # Box templates
    # ------------------------------------------------------------------

    def list_box_templates(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(conn, self._box_template_sql("ORDER BY bt.name"))
            return [self._box_template_to_dict(row) for row in rows]

    def get_box_template(self, template_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = self._fetchone(conn, self._box_template_sql("WHERE bt.id = ?"), (template_id,))
            if not row:
                raise InventoryError("收纳盒模板不存在")
            return self._box_template_to_dict(row)

    def create_box_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._clean_box_template_payload(payload)
        now = now_text()
        with self.connect() as conn:
            self._validate_box_template_assets(conn, data)
            cur = conn.execute(
                """
                INSERT INTO box_templates (
                    name, cell_model_asset_id, frame_model_asset_id,
                    cell_width_mm, cell_depth_mm, cell_height_mm,
                    gap_x_mm, gap_z_mm, padding_x_mm, padding_z_mm, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["name"],
                    data["cell_model_asset_id"],
                    data["frame_model_asset_id"],
                    data["cell_width_mm"],
                    data["cell_depth_mm"],
                    data["cell_height_mm"],
                    data["gap_x_mm"],
                    data["gap_z_mm"],
                    data["padding_x_mm"],
                    data["padding_z_mm"],
                    now,
                    now,
                ),
            )
            template_id = cur.lastrowid
        self.file_logger.write_backend("3D", f"创建收纳盒模板: ID={template_id}, name={data['name']}")
        return self.get_box_template(template_id)

    def update_box_template(self, template_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            existing = self._fetchone(conn, "SELECT * FROM box_templates WHERE id = ?", (template_id,))
            if not existing:
                raise InventoryError("收纳盒模板不存在")
            merged = dict(existing)
            merged.update(payload)
            data = self._clean_box_template_payload(merged)
            self._validate_box_template_assets(conn, data)
            conn.execute(
                """
                UPDATE box_templates
                SET name = ?, cell_model_asset_id = ?, frame_model_asset_id = ?,
                    cell_width_mm = ?, cell_depth_mm = ?, cell_height_mm = ?,
                    gap_x_mm = ?, gap_z_mm = ?, padding_x_mm = ?, padding_z_mm = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    data["name"],
                    data["cell_model_asset_id"],
                    data["frame_model_asset_id"],
                    data["cell_width_mm"],
                    data["cell_depth_mm"],
                    data["cell_height_mm"],
                    data["gap_x_mm"],
                    data["gap_z_mm"],
                    data["padding_x_mm"],
                    data["padding_z_mm"],
                    now_text(),
                    template_id,
                ),
            )
        self.file_logger.write_backend("3D", f"更新收纳盒模板: ID={template_id}, name={data['name']}")
        return self.get_box_template(template_id)

    def delete_box_template(self, template_id: int) -> None:
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT * FROM box_templates WHERE id = ?", (template_id,))
            if not row:
                raise InventoryError("收纳盒模板不存在")
            used = self._fetchone(conn, "SELECT COUNT(*) AS cnt FROM boxes WHERE template_id = ?", (template_id,))
            if used and used["cnt"] > 0:
                raise InventoryError("收纳盒模板正在被收纳盒引用，无法删除")
            conn.execute("DELETE FROM box_templates WHERE id = ?", (template_id,))
        self.file_logger.write_backend("3D", f"删除收纳盒模板: ID={template_id}, name={row['name']}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _asset_path(self, relative_path: str) -> Path:
        if not self.upload_folder:
            return Path(relative_path)
        return self.upload_folder / relative_path

    def _inspect_glb(self, path: Path, model_type: str) -> dict[str, Any]:
        checker = _load_glb_checker()
        gltf, version, chunks = checker.read_glb(path)
        if model_type == "cabinet_layer":
            checks = {
                "drawer_cabinet": checker.analyze_model(gltf, "drawer-cabinet"),
                "open_shelf": checker.analyze_model(gltf, "open-shelf"),
            }
            issues = checks["drawer_cabinet"]["issues"]
            active = "drawer_cabinet"
        else:
            script_type = SCRIPT_MODEL_TYPE.get(model_type)
            checks = {model_type: checker.analyze_model(gltf, script_type)}
            issues = checks[model_type]["issues"]
            active = model_type
        return {
            "asset_type": model_type,
            "active_check": active,
            "glb": {"version": version, "chunks": chunks},
            "checks": checks,
            "issues": issues,
        }

    def _clean_model_type(self, value: Any) -> str:
        model_type = clean_text(value)
        if model_type not in MODEL_TYPES:
            raise InventoryError("模型类型不正确")
        return model_type

    def _asset_to_dict(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["url"] = file_url(item.get("file_path"))
        try:
            item["node_report"] = json.loads(item.get("node_report_json") or "{}")
        except json.JSONDecodeError:
            item["node_report"] = {}
        return item

    def _asset_reference_count(self, conn, asset_id: int) -> int:
        checks = [
            ("cabinet_templates", "layer_model_asset_id"),
            ("cabinet_templates", "base_model_asset_id"),
            ("cabinet_templates", "top_model_asset_id"),
            ("box_templates", "cell_model_asset_id"),
            ("box_templates", "frame_model_asset_id"),
        ]
        total = 0
        for table, column in checks:
            total += conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (asset_id,)).fetchone()[0]
        return total

    def _asset_exists(self, conn, asset_id: int | None, expected_type: str | None = None) -> bool:
        if asset_id is None:
            return True
        if expected_type:
            return bool(self._fetchone(conn, "SELECT id FROM model_assets WHERE id = ? AND type = ?", (asset_id, expected_type)))
        return bool(self._fetchone(conn, "SELECT id FROM model_assets WHERE id = ?", (asset_id,)))

    def _clean_asset_id(self, value: Any) -> int | None:
        if value in (None, "", "null"):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _clean_cabinet_template_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = clean_text(payload.get("name"))
        if not name:
            raise InventoryError("请填写柜体模板名称")
        structure_type = clean_text(payload.get("structure_type")) or "drawer_cabinet"
        if structure_type not in STRUCTURE_TYPES:
            raise InventoryError("柜体结构类型不正确")
        pull_axis = clean_text(payload.get("pull_axis")) or "z"
        if pull_axis not in {"x", "y", "z", "-x", "-y", "-z"}:
            raise InventoryError("抽拉方向参数不正确")
        return {
            "name": name,
            "structure_type": structure_type,
            "layer_model_asset_id": self._clean_asset_id(payload.get("layer_model_asset_id")),
            "base_model_asset_id": self._clean_asset_id(payload.get("base_model_asset_id")),
            "top_model_asset_id": self._clean_asset_id(payload.get("top_model_asset_id")),
            "layer_height_mm": _clean_positive_float(payload.get("layer_height_mm"), 80),
            "pull_axis": pull_axis,
            "pull_distance_mm": _clean_positive_float(payload.get("pull_distance_mm"), 160),
            "slot_offset_x_mm": _clean_float(payload.get("slot_offset_x_mm"), 0) or 0,
            "slot_offset_y_mm": _clean_float(payload.get("slot_offset_y_mm"), 0) or 0,
            "slot_offset_z_mm": _clean_float(payload.get("slot_offset_z_mm"), 0) or 0,
        }

    def _validate_cabinet_template_assets(self, conn, data: dict[str, Any]) -> None:
        if data["layer_model_asset_id"] and not self._asset_exists(conn, data["layer_model_asset_id"], "cabinet_layer"):
            raise InventoryError("标准层模型不存在或类型不匹配")
        if data["base_model_asset_id"] and not self._asset_exists(conn, data["base_model_asset_id"], "cabinet_base"):
            raise InventoryError("底座模型不存在或类型不匹配")
        if data["top_model_asset_id"] and not self._asset_exists(conn, data["top_model_asset_id"], "cabinet_top"):
            raise InventoryError("顶盖模型不存在或类型不匹配")

    def _clean_box_template_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = clean_text(payload.get("name"))
        if not name:
            raise InventoryError("请填写收纳盒模板名称")
        return {
            "name": name,
            "cell_model_asset_id": self._clean_asset_id(payload.get("cell_model_asset_id")),
            "frame_model_asset_id": self._clean_asset_id(payload.get("frame_model_asset_id")),
            "cell_width_mm": _clean_positive_float(payload.get("cell_width_mm"), 28),
            "cell_depth_mm": _clean_positive_float(payload.get("cell_depth_mm"), 28),
            "cell_height_mm": _clean_positive_float(payload.get("cell_height_mm"), 12),
            "gap_x_mm": _clean_float(payload.get("gap_x_mm"), 2) or 0,
            "gap_z_mm": _clean_float(payload.get("gap_z_mm"), 2) or 0,
            "padding_x_mm": _clean_float(payload.get("padding_x_mm"), 4) or 0,
            "padding_z_mm": _clean_float(payload.get("padding_z_mm"), 4) or 0,
        }

    def _validate_box_template_assets(self, conn, data: dict[str, Any]) -> None:
        if data["cell_model_asset_id"] and not self._asset_exists(conn, data["cell_model_asset_id"], "box_cell"):
            raise InventoryError("单格模型不存在或类型不匹配")
        if data["frame_model_asset_id"] and not self._asset_exists(conn, data["frame_model_asset_id"], "box_frame"):
            raise InventoryError("外框模型不存在或类型不匹配")

    def _cabinet_template_sql(self, suffix: str) -> str:
        return f"""
            SELECT
                ct.*,
                la.id AS layer_asset_id, la.name AS layer_asset_name, la.type AS layer_asset_type,
                la.file_path AS layer_asset_file_path, la.width_mm AS layer_asset_width_mm,
                la.height_mm AS layer_asset_height_mm, la.depth_mm AS layer_asset_depth_mm,
                ba.id AS base_asset_id, ba.name AS base_asset_name, ba.type AS base_asset_type,
                ba.file_path AS base_asset_file_path, ba.width_mm AS base_asset_width_mm,
                ba.height_mm AS base_asset_height_mm, ba.depth_mm AS base_asset_depth_mm,
                ta.id AS top_asset_id, ta.name AS top_asset_name, ta.type AS top_asset_type,
                ta.file_path AS top_asset_file_path, ta.width_mm AS top_asset_width_mm,
                ta.height_mm AS top_asset_height_mm, ta.depth_mm AS top_asset_depth_mm
            FROM cabinet_templates ct
            LEFT JOIN model_assets la ON la.id = ct.layer_model_asset_id
            LEFT JOIN model_assets ba ON ba.id = ct.base_model_asset_id
            LEFT JOIN model_assets ta ON ta.id = ct.top_model_asset_id
            {suffix}
        """

    def _cabinet_template_to_dict(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["layer_model_asset"] = _asset_summary(row, "layer_asset_")
        item["base_model_asset"] = _asset_summary(row, "base_asset_")
        item["top_model_asset"] = _asset_summary(row, "top_asset_")
        return item

    def _box_template_sql(self, suffix: str) -> str:
        return f"""
            SELECT
                bt.*,
                ca.id AS cell_asset_id, ca.name AS cell_asset_name, ca.type AS cell_asset_type,
                ca.file_path AS cell_asset_file_path, ca.width_mm AS cell_asset_width_mm,
                ca.height_mm AS cell_asset_height_mm, ca.depth_mm AS cell_asset_depth_mm,
                fa.id AS frame_asset_id, fa.name AS frame_asset_name, fa.type AS frame_asset_type,
                fa.file_path AS frame_asset_file_path, fa.width_mm AS frame_asset_width_mm,
                fa.height_mm AS frame_asset_height_mm, fa.depth_mm AS frame_asset_depth_mm
            FROM box_templates bt
            LEFT JOIN model_assets ca ON ca.id = bt.cell_model_asset_id
            LEFT JOIN model_assets fa ON fa.id = bt.frame_model_asset_id
            {suffix}
        """

    def _box_template_to_dict(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["cell_model_asset"] = _asset_summary(row, "cell_asset_")
        item["frame_model_asset"] = _asset_summary(row, "frame_asset_")
        return item
