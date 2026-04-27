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
        conn.commit()
