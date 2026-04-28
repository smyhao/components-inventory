from __future__ import annotations

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
    nfc_uid TEXT UNIQUE,
    position_x REAL DEFAULT 0,
    position_y REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cabinet_id) REFERENCES cabinets(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS cabinets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    color TEXT DEFAULT '#8b9aae',
    position_x REAL DEFAULT 0,
    position_y REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
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

CREATE INDEX IF NOT EXISTS idx_components_name ON components(name);
CREATE INDEX IF NOT EXISTS idx_components_model ON components(model);
CREATE INDEX IF NOT EXISTS idx_components_category_id ON components(category_id);
CREATE INDEX IF NOT EXISTS idx_components_box_id ON components(box_id);
CREATE INDEX IF NOT EXISTS idx_components_quantity ON components(quantity);
CREATE INDEX IF NOT EXISTS idx_compartments_box_id ON compartments(box_id);
CREATE INDEX IF NOT EXISTS idx_stock_logs_component_id ON stock_logs(component_id);
CREATE INDEX IF NOT EXISTS idx_documents_component_id ON documents(component_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_active ON api_tokens(active);

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
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)

        box_columns = {row[1] for row in conn.execute("PRAGMA table_info(boxes)").fetchall()}
        if "color" not in box_columns:
            conn.execute("ALTER TABLE boxes ADD COLUMN color TEXT DEFAULT '#84b59b'")
        if "cabinet_id" not in box_columns:
            conn.execute("ALTER TABLE boxes ADD COLUMN cabinet_id INTEGER")
        if "cabinet_slot" not in box_columns:
            conn.execute("ALTER TABLE boxes ADD COLUMN cabinet_slot INTEGER DEFAULT 0")
        conn.execute("UPDATE boxes SET color = '#84b59b' WHERE color IS NULL OR TRIM(color) = ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_boxes_cabinet_id ON boxes(cabinet_id)")

        existing = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if existing == 0:
            conn.executemany(
                "INSERT INTO categories (name, parent_id, icon) VALUES (?, NULL, NULL)",
                [(name,) for name in DEFAULT_CATEGORIES],
            )

        led_cfg_count = conn.execute("SELECT COUNT(*) FROM led_config").fetchone()[0]
        if led_cfg_count == 0:
            conn.execute("INSERT INTO led_config (id, enabled) VALUES (1, 0)")

        led_mapping_columns = {row[1] for row in conn.execute("PRAGMA table_info(led_box_mapping)").fetchall()}
        if "color" not in led_mapping_columns:
            conn.execute("ALTER TABLE led_box_mapping ADD COLUMN color TEXT NOT NULL DEFAULT '#00ff00'")

        conn.commit()
