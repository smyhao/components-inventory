from __future__ import annotations

# 本文件覆盖 ESP32-S3 NFC 远程读写后端能力：表初始化、设备仓储、服务编排和 API 设置入口。

import sqlite3

import pytest

from init_db import init_database
from models import InventoryError
from services.nfc_device_service import NfcDeviceService, normalize_uid


class FakeNfcProxy:
    """测试用 NFC 代理，避免单元测试依赖真实局域网硬件。"""

    def __init__(self) -> None:
        self.health_calls = []
        self.config_calls = []
        self.read_calls = []
        self.write_calls = []
        self.erase_calls = []
        self.cancel_calls = []

    def health(self, device):
        self.health_calls.append(device)
        return {"connected": True, "latency_ms": 8, "nfc": {"ready": True, "busy": False}}

    def push_config(self, device, payload):
        self.config_calls.append((device, payload))
        return {"saved": True, "restart_required": False}

    def read(self, device, payload):
        self.read_calls.append((device, payload))
        return {
            "request_id": payload["request_id"],
            "operation": "read",
            "tag": {"uid": "04:a1:b2:c3", "type": "NTAG213", "ndef": {"records": []}},
            "duration_ms": 120,
        }

    def write(self, device, payload):
        self.write_calls.append((device, payload))
        return {
            "request_id": payload["request_id"],
            "operation": "write",
            "tag": {"uid": "04 A1 B2 C3", "type": "NTAG213"},
            "written": {"record_count": len(payload["ndef"]["records"]), "payload_bytes": 64, "verified": True, "locked": False},
            "duration_ms": 180,
        }

    def erase(self, device, payload):
        self.erase_calls.append((device, payload))
        return {
            "request_id": payload["request_id"],
            "operation": "erase",
            "tag": {"uid": "04-A1-B2-C3", "type": "NTAG213"},
            "erased": True,
            "verified": True,
        }

    def cancel(self, device, payload):
        self.cancel_calls.append((device, payload))
        return {"cancelled": True, "request_id": payload["request_id"]}


def _nfc_device(repo):
    return repo.create_nfc_device(
        {
            "name": "nfc-reader-1",
            "host": "192.168.1.120",
            "port": 80,
            "module_type": "PN532",
            "device_token": "secret",
            "default_timeout_ms": 15000,
            "allow_erase": True,
        }
    )


def test_init_database_creates_nfc_tables_and_default_config(db):
    with sqlite3.connect(db) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert {"nfc_config", "nfc_devices"} <= tables
        config = conn.execute("SELECT enabled, default_timeout_ms FROM nfc_config WHERE id = 1").fetchone()
        assert config == (0, 10000)


def test_nfc_device_crud_masks_token(repo):
    device = _nfc_device(repo)
    assert device["device_token_configured"] is True
    assert "device_token" not in device

    stored = repo.get_nfc_device(device["id"])
    assert stored["device_token"] == "secret"

    updated = repo.update_nfc_device(device["id"], {"name": "nfc-reader-1", "host": "192.168.1.121", "enabled": False})
    assert updated["enabled"] == 0
    assert repo.get_nfc_device(device["id"])["device_token"] == "secret"

    repo.delete_nfc_device(device["id"])
    assert repo.list_nfc_devices() == []


def test_nfc_device_can_link_led_device(repo):
    led = repo.create_led_device({"name": "combo-led", "host": "192.168.1.120", "port": 80})
    device = repo.create_nfc_device(
        {"name": "combo-nfc", "host": "192.168.1.120", "port": 80, "linked_led_device_id": led["id"]}
    )
    assert device["linked_led_device_id"] == led["id"]
    assert repo.find_nfc_device_for_led_device(led["id"])["id"] == device["id"]
    with pytest.raises(InventoryError, match="LED 设备不存在"):
        repo.create_nfc_device({"name": "bad-link", "host": "192.168.1.121", "linked_led_device_id": 999})


def test_nfc_config_validates_default_device(repo):
    device = _nfc_device(repo)
    config = repo.update_nfc_config({"enabled": True, "default_device_id": device["id"], "default_timeout_ms": 900})
    assert config["enabled"] == 1
    assert config["default_timeout_ms"] == 1000
    with pytest.raises(InventoryError, match="不存在"):
        repo.update_nfc_config({"default_device_id": 999})


def test_remote_read_adds_lookup_summary(repo, file_logger, sample_box_id):
    device = _nfc_device(repo)
    repo.bind_nfc(sample_box_id, "04A1B2C3")
    proxy = FakeNfcProxy()
    result = NfcDeviceService(repo, file_logger, proxy).read_device(device["id"], {"timeout_ms": 1200})
    assert result["uid"] == "04A1B2C3"
    assert result["lookup"]["bound"] is True
    assert result["lookup"]["box_id"] == sample_box_id
    assert proxy.read_calls[0][1]["timeout_ms"] == 1200


def test_write_box_writes_project_payload_and_binds_uid(repo, file_logger, sample_box_id):
    device = _nfc_device(repo)
    proxy = FakeNfcProxy()
    result = NfcDeviceService(repo, file_logger, proxy).write_box(device["id"], {"box_id": sample_box_id, "overwrite": True})
    assert result["uid"] == "04A1B2C3"
    assert result["binding"]["box_id"] == sample_box_id
    records = proxy.write_calls[0][1]["ndef"]["records"]
    assert records[0]["type"] == "uri"
    assert records[1]["type"] == "text"
    assert repo.lookup_nfc_summary("04A1B2C3")["bound"] is True


def test_nfc_sync_includes_led_strips_when_linked(repo, file_logger):
    led = repo.create_led_device({"name": "combo-led", "host": "192.168.1.120", "port": 80})
    repo.create_led_strip({"device_id": led["id"], "name": "front", "gpio_num": 8, "led_count": 16})
    device = repo.create_nfc_device({"name": "combo-nfc", "host": "192.168.1.120", "linked_led_device_id": led["id"]})
    proxy = FakeNfcProxy()
    result = NfcDeviceService(repo, file_logger, proxy).sync_device(device["id"])
    assert result["synced"] is True
    payload = proxy.config_calls[0][1]
    assert {"gpio": 8, "led_count": 16} in payload["strips"]
    assert payload["led"]["strips"] == payload["strips"]


def test_custom_write_validates_records_and_lock_setting(repo, file_logger):
    device = _nfc_device(repo)
    proxy = FakeNfcProxy()
    result = NfcDeviceService(repo, file_logger, proxy).write_custom(
        device["id"],
        {"ndef": {"records": [{"type": "text", "value": "测试标签"}]}},
    )
    assert result["written"]["record_count"] == 1

    with pytest.raises(InventoryError, match="锁定能力"):
        NfcDeviceService(repo, file_logger, proxy).write_custom(
            device["id"],
            {"lock_after_write": True, "ndef": {"records": [{"type": "text", "value": "x"}]}},
        )


def test_erase_requires_allow_erase(repo, file_logger):
    device = _nfc_device(repo)
    proxy = FakeNfcProxy()
    result = NfcDeviceService(repo, file_logger, proxy).erase_device(device["id"], {})
    assert result["erased"] is True

    locked = repo.create_nfc_device({"name": "no-erase", "host": "192.168.1.130", "allow_erase": False})
    with pytest.raises(InventoryError, match="擦除能力"):
        NfcDeviceService(repo, file_logger, proxy).erase_device(locked["id"], {})


def test_settings_api_crud(client):
    resp = client.get("/api/settings/nfc")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["config"]["enabled"] == 0

    device = client.post(
        "/api/settings/nfc/devices",
        json={"name": "api-nfc", "host": "127.0.0.1", "device_token": "abc"},
    ).get_json()["data"]
    assert device["device_token_configured"] is True
    assert "device_token" not in device

    resp = client.put("/api/settings/nfc", json={"enabled": True, "default_device_id": device["id"]})
    assert resp.status_code == 200
    assert resp.get_json()["data"]["default_device_id"] == device["id"]

    resp = client.delete(f"/api/settings/nfc/devices/{device['id']}")
    assert resp.status_code == 200
    assert client.get("/api/settings/nfc").get_json()["data"]["devices"] == []


def test_normalize_uid_strict_rules():
    assert normalize_uid("0x04:a1-b2 c3") == "04A1B2C3"
    with pytest.raises(InventoryError):
        normalize_uid("LOOKUP123")
