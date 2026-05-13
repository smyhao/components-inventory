from __future__ import annotations

import io
import json
import struct


def build_glb(gltf: dict) -> bytes:
    payload = json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload += b" " * ((4 - len(payload) % 4) % 4)
    total_length = 12 + 8 + len(payload)
    return b"glTF" + struct.pack("<II", 2, total_length) + struct.pack("<I4s", len(payload), b"JSON") + payload


def make_glb_file(filename: str = "model.glb") -> io.BytesIO:
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "ROOT"}],
    }
    buf = io.BytesIO(build_glb(gltf))
    buf.name = filename
    return buf


def upload_asset(client, name: str = "Cell", model_type: str = "box_cell") -> dict:
    resp = client.post(
        "/api/model-assets/upload",
        data={
            "file": (make_glb_file(), "cell.glb"),
            "name": name,
            "type": model_type,
            "width_mm": "10",
            "height_mm": "8",
            "depth_mm": "12",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    return resp.get_json()["data"]


def test_upload_only_allows_glb(client):
    resp = client.post(
        "/api/model-assets/upload",
        data={
            "file": (io.BytesIO(b"not glb"), "bad.txt"),
            "name": "Bad",
            "type": "box_cell",
        },
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert ".glb" in resp.get_json()["message"]


def test_model_node_report_is_saved_and_returned(client):
    asset = upload_asset(client)

    assert asset["node_report"]["asset_type"] == "box_cell"
    assert asset["node_report"]["glb"]["version"] == 2
    assert asset["url"].endswith(".glb")


def test_model_referenced_by_template_cannot_be_deleted(client):
    asset = upload_asset(client)
    template_resp = client.post(
        "/api/box-templates",
        json={"name": "Box Template", "cell_model_asset_id": asset["id"]},
    )
    assert template_resp.status_code == 200

    resp = client.delete(f"/api/model-assets/{asset['id']}")

    assert resp.status_code == 400
    assert "引用" in resp.get_json()["message"]


def test_box_template_referenced_by_box_cannot_be_deleted(client):
    template_resp = client.post("/api/box-templates", json={"name": "Box Template"})
    assert template_resp.status_code == 200
    template_id = template_resp.get_json()["data"]["id"]
    box_resp = client.post("/api/boxes", json={"name": "Templated Box", "rows": 2, "cols": 2, "template_id": template_id})
    assert box_resp.status_code == 200

    resp = client.delete(f"/api/box-templates/{template_id}")

    assert resp.status_code == 400
    assert "引用" in resp.get_json()["message"]


def test_cabinet_template_referenced_by_cabinet_cannot_be_deleted(client):
    template_resp = client.post("/api/cabinet-templates", json={"name": "Cabinet Template"})
    assert template_resp.status_code == 200
    template_id = template_resp.get_json()["data"]["id"]
    cabinet_resp = client.post("/api/cabinets", json={"name": "Templated Cabinet", "template_id": template_id})
    assert cabinet_resp.status_code == 200

    resp = client.delete(f"/api/cabinet-templates/{template_id}")

    assert resp.status_code == 400
    assert "引用" in resp.get_json()["message"]


def test_cabinet_layer_count_and_slot_rules(client):
    cabinet_resp = client.post("/api/cabinets", json={"name": "Layered Cabinet", "layer_count": 2})
    assert cabinet_resp.status_code == 200
    cabinet_id = cabinet_resp.get_json()["data"]["id"]
    assert client.post("/api/boxes", json={"name": "Slot 1", "rows": 1, "cols": 1, "cabinet_id": cabinet_id, "cabinet_slot": 1}).status_code == 200
    assert client.post("/api/boxes", json={"name": "Slot 2", "rows": 1, "cols": 1, "cabinet_id": cabinet_id, "cabinet_slot": 2}).status_code == 200

    duplicate = client.post("/api/boxes", json={"name": "Duplicate", "rows": 1, "cols": 1, "cabinet_id": cabinet_id, "cabinet_slot": 2})
    assert duplicate.status_code == 400
    full = client.post("/api/boxes", json={"name": "Full", "rows": 1, "cols": 1, "cabinet_id": cabinet_id})
    assert full.status_code == 400
    out_of_range = client.post("/api/boxes", json={"name": "Out", "rows": 1, "cols": 1, "cabinet_id": cabinet_id, "cabinet_slot": 3})
    assert out_of_range.status_code == 400
    shrink = client.put(f"/api/cabinets/{cabinet_id}", json={"layer_count": 1})
    assert shrink.status_code == 400


def test_default_models_still_work_without_templates(client):
    cabinet_resp = client.post("/api/cabinets", json={"name": "Default Cabinet"})
    box_resp = client.post("/api/boxes", json={"name": "Default Box", "rows": 2, "cols": 3})
    map_resp = client.get("/api/map")

    assert cabinet_resp.status_code == 200
    assert box_resp.status_code == 200
    assert map_resp.status_code == 200
    data = map_resp.get_json()["data"]
    assert data["cabinets"][0]["template"] is None
    assert data["boxes"][0]["template"] is None
