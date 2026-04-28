from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from init_db import init_database
from logger import FileLogger
from models import InventoryRepository


@pytest.fixture
def tmp_dirs(tmp_path):
    data_dir = tmp_path / "data"
    upload_dir = tmp_path / "uploads"
    thumb_dir = upload_dir / "thumbnails"
    doc_dir = upload_dir / "documents"
    log_dir = tmp_path / "log"
    for d in (data_dir, upload_dir, thumb_dir, doc_dir, log_dir):
        d.mkdir(parents=True, exist_ok=True)
    return {
        "data_dir": data_dir,
        "upload_dir": upload_dir,
        "thumb_dir": thumb_dir,
        "doc_dir": doc_dir,
        "log_dir": log_dir,
        "db_path": data_dir / "test_inventory.db",
        "log_file": log_dir / "backend.log",
        "frontend_log_file": log_dir / "frontend.log",
    }


@pytest.fixture
def file_logger(tmp_dirs):
    return FileLogger(tmp_dirs["log_file"], tmp_dirs["frontend_log_file"])


@pytest.fixture
def db(tmp_dirs):
    db_path = tmp_dirs["db_path"]
    init_database(db_path)
    return db_path


@pytest.fixture
def repo(db, file_logger, tmp_dirs):
    return InventoryRepository(db, file_logger, tmp_dirs["upload_dir"])


# Modules that need path/auth patching
_PATCH_MODULES = ["config", "routes.tags", "routes.map", "routes.auth", "routes.pages"]

_saved = {}


@pytest.fixture
def app(db, file_logger, tmp_dirs, repo):
    import app as app_module
    import config

    _saved["repo"] = app_module.repo
    _saved["file_logger"] = app_module.file_logger
    _saved["config_UPLOAD_FOLDER"] = config.UPLOAD_FOLDER
    _saved["config_DOCUMENT_FOLDER"] = config.DOCUMENT_FOLDER
    _saved["config_API_TOKEN"] = config.API_TOKEN
    _saved["config_API_TOKEN_REQUIRE_ALL"] = config.API_TOKEN_REQUIRE_ALL

    # Patch app-level globals
    app_module.repo = repo
    app_module.file_logger = file_logger

    # Patch config-level constants
    config.UPLOAD_FOLDER = tmp_dirs["upload_dir"]
    config.DOCUMENT_FOLDER = tmp_dirs["doc_dir"]
    config.API_TOKEN = ""
    config.API_TOKEN_REQUIRE_ALL = False

    # Patch all blueprint modules that imported these from config
    import importlib

    for mod_name in _PATCH_MODULES:
        mod = importlib.import_module(mod_name)
        if hasattr(mod, "UPLOAD_FOLDER"):
            _saved[f"{mod_name}.UPLOAD_FOLDER"] = mod.UPLOAD_FOLDER
            mod.UPLOAD_FOLDER = tmp_dirs["upload_dir"]
        if hasattr(mod, "DOCUMENT_FOLDER"):
            _saved[f"{mod_name}.DOCUMENT_FOLDER"] = mod.DOCUMENT_FOLDER
            mod.DOCUMENT_FOLDER = tmp_dirs["doc_dir"]
        if hasattr(mod, "API_TOKEN"):
            _saved[f"{mod_name}.API_TOKEN"] = mod.API_TOKEN
            mod.API_TOKEN = ""
        if hasattr(mod, "API_TOKEN_REQUIRE_ALL"):
            _saved[f"{mod_name}.API_TOKEN_REQUIRE_ALL"] = mod.API_TOKEN_REQUIRE_ALL
            mod.API_TOKEN_REQUIRE_ALL = False

    test_app = app_module.app
    test_app.config["TESTING"] = True

    yield test_app

    # Restore
    app_module.repo = _saved["repo"]
    app_module.file_logger = _saved["file_logger"]
    config.UPLOAD_FOLDER = _saved["config_UPLOAD_FOLDER"]
    config.DOCUMENT_FOLDER = _saved["config_DOCUMENT_FOLDER"]
    config.API_TOKEN = _saved["config_API_TOKEN"]
    config.API_TOKEN_REQUIRE_ALL = _saved["config_API_TOKEN_REQUIRE_ALL"]

    for mod_name in _PATCH_MODULES:
        mod = importlib.import_module(mod_name)
        for attr in ("UPLOAD_FOLDER", "DOCUMENT_FOLDER", "API_TOKEN", "API_TOKEN_REQUIRE_ALL"):
            key = f"{mod_name}.{attr}"
            if key in _saved:
                setattr(mod, attr, _saved[key])


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_token(repo):
    result = repo.create_api_token({"name": "test-token"})
    return result["token"]


@pytest.fixture
def auth_headers(auth_token):
    return {
        "Authorization": f"Bearer {auth_token}",
        "X-Inventory-Source": "inventory-cli",
    }


@pytest.fixture
def sample_category_id(client):
    resp = client.post("/api/categories", json={"name": "Test Category"})
    assert resp.status_code == 200
    return resp.get_json()["data"]["id"]


@pytest.fixture
def sample_cabinet_id(client):
    resp = client.post("/api/cabinets", json={"name": "Test Cabinet"})
    assert resp.status_code == 200
    return resp.get_json()["data"]["id"]


@pytest.fixture
def sample_box_id(client):
    resp = client.post("/api/boxes", json={"name": "Test Box", "rows": 3, "cols": 3})
    assert resp.status_code == 200
    return resp.get_json()["data"]["id"]


@pytest.fixture
def sample_component_id(client, sample_category_id):
    resp = client.post(
        "/api/components",
        json={
            "name": "Test Component",
            "quantity": 100,
            "category_id": sample_category_id,
        },
    )
    assert resp.status_code == 200
    return resp.get_json()["data"]["id"]


def make_test_image(filename="test.png"):
    img = Image.new("RGB", (10, 10), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    buf.name = filename
    return buf


def make_test_csv(content: str, filename="test.csv"):
    buf = io.BytesIO(content.encode("utf-8"))
    buf.seek(0)
    buf.name = filename
    return buf
