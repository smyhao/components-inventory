from __future__ import annotations

import importlib.util
import json
import struct
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_glb_model.py"
spec = importlib.util.spec_from_file_location("check_glb_model", SCRIPT_PATH)
check_glb_model = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules["check_glb_model"] = check_glb_model
spec.loader.exec_module(check_glb_model)


def build_glb(gltf: dict) -> bytes:
    payload = json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload += b" " * ((4 - len(payload) % 4) % 4)
    total_length = 12 + 8 + len(payload)
    return b"glTF" + struct.pack("<II", 2, total_length) + struct.pack("<I4s", len(payload), b"JSON") + payload


def test_drawer_model_accepts_exported_suffixes_and_reports_pull_vector():
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [
            {"name": "root", "children": [1, 2, 3, 4, 5, 6, 7]},
            {"name": "FIXED_FRAME-1"},
            {"name": "DRAWER_PART-1"},
            {"name": "NAMEPLATE_ANCHOR-1", "translation": [0, 0, 0]},
            {"name": "LED_ANCHOR-1", "translation": [1, 0, 0]},
            {"name": "BOX_SLOT_ANCHOR-1", "translation": [2, 0, 0]},
            {"name": "DRAWER_CLOSED_ANCHOR-1", "translation": [0, 0, 0]},
            {"name": "DRAWER_OPEN_ANCHOR -1", "translation": [0.25, 0, 0]},
        ],
    }

    parsed, version, chunks = check_glb_model.parse_glb_bytes(build_glb(gltf))
    report = check_glb_model.analyze_model(parsed, "drawer-cabinet")

    assert version == 2
    assert chunks[0]["type"] == "JSON"
    assert report["missing"] == []
    assert report["drawer_pull"]["available"] is True
    assert report["drawer_pull"]["distance"] == 0.25
    assert any("建议改成标准名" in issue["message"] for issue in report["issues"])


def test_drawer_model_reports_missing_required_nodes():
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "root", "children": [1]}, {"name": "FIXED_FRAME"}],
    }

    parsed, _, _ = check_glb_model.parse_glb_bytes(build_glb(gltf))
    report = check_glb_model.analyze_model(parsed, "drawer-cabinet")

    assert "DRAWER_PART" in report["missing"]
    assert any(issue["level"] == "error" for issue in report["issues"])
