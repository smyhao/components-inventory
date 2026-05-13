from __future__ import annotations

# 本文件负责集中初始化 SQLite 结构和兼容迁移，所有数据库表定义都应在这里收口。

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER,
    icon TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS boxes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    rows INTEGER NOT NULL DEFAULT 1,
    cols INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    color TEXT DEFAULT '#84b59b',
    cabinet_id INTEGER,
    cabinet_slot INTEGER DEFAULT 0,
    template_id INTEGER,
    nfc_uid TEXT UNIQUE,
    position_x REAL DEFAULT 0,
    position_y REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cabinet_id) REFERENCES cabinets(id) ON DELETE SET NULL,
    FOREIGN KEY (template_id) REFERENCES box_templates(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS cabinets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    color TEXT DEFAULT '#8b9aae',
    template_id INTEGER,
    layer_count INTEGER NOT NULL DEFAULT 1,
    position_x REAL DEFAULT 0,
    position_y REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (template_id) REFERENCES cabinet_templates(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS model_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    original_name TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT 'mm',
    width_mm REAL,
    height_mm REAL,
    depth_mm REAL,
    node_report_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cabinet_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    structure_type TEXT NOT NULL DEFAULT 'drawer_cabinet',
    layer_model_asset_id INTEGER,
    base_model_asset_id INTEGER,
    top_model_asset_id INTEGER,
    layer_height_mm REAL NOT NULL DEFAULT 80,
    pull_axis TEXT NOT NULL DEFAULT 'z',
    pull_distance_mm REAL NOT NULL DEFAULT 160,
    slot_offset_x_mm REAL NOT NULL DEFAULT 0,
    slot_offset_y_mm REAL NOT NULL DEFAULT 0,
    slot_offset_z_mm REAL NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (layer_model_asset_id) REFERENCES model_assets(id) ON DELETE SET NULL,
    FOREIGN KEY (base_model_asset_id) REFERENCES model_assets(id) ON DELETE SET NULL,
    FOREIGN KEY (top_model_asset_id) REFERENCES model_assets(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS box_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    cell_model_asset_id INTEGER,
    frame_model_asset_id INTEGER,
    cell_width_mm REAL NOT NULL DEFAULT 28,
    cell_depth_mm REAL NOT NULL DEFAULT 28,
    cell_height_mm REAL NOT NULL DEFAULT 12,
    gap_x_mm REAL NOT NULL DEFAULT 2,
    gap_z_mm REAL NOT NULL DEFAULT 2,
    padding_x_mm REAL NOT NULL DEFAULT 4,
    padding_z_mm REAL NOT NULL DEFAULT 4,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cell_model_asset_id) REFERENCES model_assets(id) ON DELETE SET NULL,
    FOREIGN KEY (frame_model_asset_id) REFERENCES model_assets(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS compartments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    box_id INTEGER NOT NULL,
    row INTEGER NOT NULL,
    col INTEGER NOT NULL,
    label TEXT,
    FOREIGN KEY (box_id) REFERENCES boxes(id) ON DELETE CASCADE,
    UNIQUE(box_id, row, col)
);

CREATE TABLE IF NOT EXISTS components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category_id INTEGER,
    model TEXT,
    package TEXT,
    nominal_value TEXT,
    voltage_rating TEXT,
    current_rating TEXT,
    power_rating TEXT,
    tolerance TEXT,
    material_type TEXT,
    manufacturer TEXT,
    extra_specs TEXT,
    quantity INTEGER NOT NULL DEFAULT 0,
    box_id INTEGER,
    compartment_id INTEGER UNIQUE,
    description TEXT,
    min_stock INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
    FOREIGN KEY (box_id) REFERENCES boxes(id) ON DELETE SET NULL,
    FOREIGN KEY (compartment_id) REFERENCES compartments(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS component_tags (
    component_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (component_id, tag_id),
    FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER,
    path TEXT NOT NULL UNIQUE,
    thumbnail_path TEXT,
    is_primary INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER,
    path TEXT NOT NULL UNIQUE,
    original_name TEXT NOT NULL,
    mime_type TEXT,
    file_size INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS stock_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL,
    type TEXT,
    change INTEGER NOT NULL,
    quantity_after INTEGER,
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS api_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    token_hash TEXT NOT NULL UNIQUE,
    token_prefix TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_used_at TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS led_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    enabled INTEGER NOT NULL DEFAULT 0,
    blink_interval_ms INTEGER NOT NULL DEFAULT 500,
    blink_duration_ms INTEGER NOT NULL DEFAULT 10000,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS led_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 80,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS led_strips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    gpio_num INTEGER NOT NULL,
    led_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (device_id) REFERENCES led_devices(id) ON DELETE CASCADE,
    UNIQUE(device_id, gpio_num)
);

CREATE TABLE IF NOT EXISTS led_box_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    box_id INTEGER NOT NULL UNIQUE,
    strip_id INTEGER NOT NULL,
    led_index INTEGER NOT NULL,
    color TEXT NOT NULL DEFAULT '#00ff00',
    FOREIGN KEY (box_id) REFERENCES boxes(id) ON DELETE CASCADE,
    FOREIGN KEY (strip_id) REFERENCES led_strips(id) ON DELETE CASCADE,
    UNIQUE(strip_id, led_index)
);

CREATE TABLE IF NOT EXISTS nfc_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    enabled INTEGER NOT NULL DEFAULT 0,
    default_device_id INTEGER,
    default_timeout_ms INTEGER NOT NULL DEFAULT 10000,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (default_device_id) REFERENCES nfc_devices(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS nfc_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 80,
    enabled INTEGER NOT NULL DEFAULT 1,
    linked_led_device_id INTEGER,
    module_type TEXT NOT NULL DEFAULT 'PN532',
    device_token TEXT DEFAULT '',
    default_timeout_ms INTEGER NOT NULL DEFAULT 10000,
    allow_erase INTEGER NOT NULL DEFAULT 0,
    allow_lock INTEGER NOT NULL DEFAULT 0,
    last_test_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (linked_led_device_id) REFERENCES led_devices(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_components_name ON components(name);
CREATE INDEX IF NOT EXISTS idx_components_model ON components(model);
CREATE INDEX IF NOT EXISTS idx_components_category_id ON components(category_id);
CREATE INDEX IF NOT EXISTS idx_components_box_id ON components(box_id);
CREATE INDEX IF NOT EXISTS idx_components_quantity ON components(quantity);
CREATE INDEX IF NOT EXISTS idx_components_updated_at ON components(updated_at);
CREATE INDEX IF NOT EXISTS idx_compartments_box_id ON compartments(box_id);
CREATE INDEX IF NOT EXISTS idx_stock_logs_component_id ON stock_logs(component_id);
CREATE INDEX IF NOT EXISTS idx_stock_logs_created_at ON stock_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_documents_component_id ON documents(component_id);
CREATE INDEX IF NOT EXISTS idx_images_component_id ON images(component_id);
CREATE INDEX IF NOT EXISTS idx_component_tags_tag_id ON component_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_active ON api_tokens(active);
CREATE INDEX IF NOT EXISTS idx_led_strips_device_id ON led_strips(device_id);
CREATE INDEX IF NOT EXISTS idx_led_box_mapping_strip_id ON led_box_mapping(strip_id);
CREATE INDEX IF NOT EXISTS idx_nfc_devices_enabled ON nfc_devices(enabled);
CREATE INDEX IF NOT EXISTS idx_model_assets_type ON model_assets(type);
CREATE INDEX IF NOT EXISTS idx_cabinet_templates_structure_type ON cabinet_templates(structure_type);
"""


DEFAULT_CATEGORIES = [
    "电阻",
    "电容",
    "电感",
    "二极管",
    "三极管",
    "MOSFET",
    "MCU",
    "传感器",
    "连接器",
    "开关",
    "电源",
    "模块",
]


def init_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)

        box_columns = {row[1] for row in conn.execute("PRAGMA table_info(boxes)").fetchall()}
        if "color" not in box_columns:
            conn.execute("ALTER TABLE boxes ADD COLUMN color TEXT DEFAULT '#84b59b'")
        if "cabinet_id" not in box_columns:
            conn.execute("ALTER TABLE boxes ADD COLUMN cabinet_id INTEGER")
        if "cabinet_slot" not in box_columns:
            conn.execute("ALTER TABLE boxes ADD COLUMN cabinet_slot INTEGER DEFAULT 0")
        if "template_id" not in box_columns:
            conn.execute("ALTER TABLE boxes ADD COLUMN template_id INTEGER")
        conn.execute("UPDATE boxes SET color = '#84b59b' WHERE color IS NULL OR TRIM(color) = ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_boxes_cabinet_id ON boxes(cabinet_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_boxes_template_id ON boxes(template_id)")
        duplicate_slots = conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT cabinet_id, cabinet_slot
                FROM boxes
                WHERE cabinet_id IS NOT NULL
                GROUP BY cabinet_id, cabinet_slot
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        if duplicate_slots == 0:
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_boxes_cabinet_slot_unique
                ON boxes(cabinet_id, cabinet_slot)
                WHERE cabinet_id IS NOT NULL
                """
            )

        cabinet_columns = {row[1] for row in conn.execute("PRAGMA table_info(cabinets)").fetchall()}
        if "template_id" not in cabinet_columns:
            conn.execute("ALTER TABLE cabinets ADD COLUMN template_id INTEGER")
        if "layer_count" not in cabinet_columns:
            conn.execute("ALTER TABLE cabinets ADD COLUMN layer_count INTEGER NOT NULL DEFAULT 1")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cabinets_template_id ON cabinets(template_id)")
        conn.execute(
            """
            UPDATE cabinets
            SET layer_count = MAX(
                1,
                COALESCE((SELECT MAX(NULLIF(cabinet_slot, 0)) FROM boxes WHERE boxes.cabinet_id = cabinets.id), 0),
                COALESCE((SELECT COUNT(*) FROM boxes WHERE boxes.cabinet_id = cabinets.id), 0)
            )
            WHERE layer_count IS NULL OR layer_count < 1
            """
        )

        led_mapping_columns = {row[1] for row in conn.execute("PRAGMA table_info(led_box_mapping)").fetchall()}
        if "color" not in led_mapping_columns:
            conn.execute("ALTER TABLE led_box_mapping ADD COLUMN color TEXT NOT NULL DEFAULT '#00ff00'")
        conn.execute("UPDATE led_box_mapping SET color = '#00ff00' WHERE color IS NULL OR TRIM(color) = ''")

        led_config_count = conn.execute("SELECT COUNT(*) FROM led_config").fetchone()[0]
        if led_config_count == 0:
            conn.execute("INSERT INTO led_config (id, enabled) VALUES (1, 0)")

        nfc_config_count = conn.execute("SELECT COUNT(*) FROM nfc_config").fetchone()[0]
        if nfc_config_count == 0:
            conn.execute("INSERT INTO nfc_config (id, enabled, default_timeout_ms) VALUES (1, 0, 10000)")

        nfc_device_columns = {row[1] for row in conn.execute("PRAGMA table_info(nfc_devices)").fetchall()}
        if "linked_led_device_id" not in nfc_device_columns:
            conn.execute("ALTER TABLE nfc_devices ADD COLUMN linked_led_device_id INTEGER")

        existing = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if existing == 0:
            conn.executemany(
                "INSERT INTO categories (name, parent_id, icon) VALUES (?, NULL, NULL)",
                [(name,) for name in DEFAULT_CATEGORIES],
            )
        conn.commit()
