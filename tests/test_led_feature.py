from __future__ import annotations

# 本文件覆盖 LED 定位功能的数据库、仓储、服务和 API 关键路径。

import sqlite3

import pytest

from init_db import init_database
from models import InventoryError
from services.led_service import LedService


class FakeLedProxy:
    """测试用 ESP32 代理，记录请求并可按设备模拟失败。"""

    def __init__(self, fail_names: set[str] | None = None) -> None:
        self.fail_names = fail_names or set()
        self.set_calls = []
        self.clear_calls = []
        self.push_strip_calls = []
        self.remove_strip_calls = []
        self.push_full_config_calls = []

    def health(self, device):
        return {"connected": True, "latency_ms": 12, "strips": [{"gpio": 8, "led_count": 30}]}

    def set_leds(self, device, leds):
        if device.get("name") in self.fail_names:
            raise InventoryError(f"设备 {device.get('name')} 返回错误: 500")
        self.set_calls.append((device, leds))
        return {"ok": True}

    def clear(self, device):
        self.clear_calls.append(device)
        return {"ok": True}

    def get_config(self, device):
        return {"status": "ok", "strips": [], "http_port": 80}

    def push_strip(self, device, gpio, led_count):
        if device.get("name") in self.fail_names:
            raise InventoryError(f"设备 {device.get('name')} 连接失败")
        self.push_strip_calls.append((device, gpio, led_count))
        return {"status": "ok", "gpio": gpio, "led_count": led_count}

    def remove_strip(self, device, gpio):
        if device.get("name") in self.fail_names:
            raise InventoryError(f"设备 {device.get('name')} 连接失败")
        self.remove_strip_calls.append((device, gpio))
        return {"status": "ok", "removed_gpio": gpio}

    def push_full_config(self, device, strips, http_port=80, extra_config=None):
        if device.get("name") in self.fail_names:
            raise InventoryError(f"设备 {device.get('name')} 连接失败")
        self.push_full_config_calls.append((device, strips, http_port, extra_config or {}))
        return {"status": "ok", "strips": strips}


def _led_mapping(repo, sample_box_id):
    device = repo.create_led_device({"name": "desk-left", "host": "192.168.1.50", "port": 80})
    strip = repo.create_led_strip({"device_id": device["id"], "name": "top", "gpio_num": 8, "led_count": 10})
    repo.save_led_mappings([{"box_id": sample_box_id, "strip_id": strip["id"], "led_index": 2, "color": "#FFAA00"}])
    return device, strip


def test_init_database_creates_led_tables_and_default_config(db):
    with sqlite3.connect(db) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert {"led_config", "led_devices", "led_strips", "led_box_mapping"} <= tables
        config = conn.execute("SELECT enabled, blink_interval_ms, blink_duration_ms FROM led_config WHERE id = 1").fetchone()
        assert config == (0, 500, 10000)


def test_init_database_migrates_led_mapping_color(tmp_path):
    db_path = tmp_path / "old.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE led_box_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                box_id INTEGER NOT NULL UNIQUE,
                strip_id INTEGER NOT NULL,
                led_index INTEGER NOT NULL
            )
            """
        )
    init_database(db_path)
    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(led_box_mapping)")}
        assert "color" in columns


def test_led_device_crud_validation_and_cascade(repo, sample_box_id):
    with pytest.raises(InventoryError):
        repo.create_led_device({"name": "", "host": "192.168.1.50"})
    device, strip = _led_mapping(repo, sample_box_id)
    with pytest.raises(InventoryError):
        repo.create_led_device({"name": device["name"], "host": "192.168.1.51"})

    repo.delete_led_device(device["id"])
    assert repo.list_led_strips() == []
    assert repo.get_led_mappings() == []


def test_led_strip_validation(repo):
    with pytest.raises(InventoryError):
        repo.create_led_strip({"device_id": 999, "name": "missing", "gpio_num": 1})
    device = repo.create_led_device({"name": "desk", "host": "192.168.1.50"})
    repo.create_led_strip({"device_id": device["id"], "name": "a", "gpio_num": 8})
    with pytest.raises(InventoryError):
        repo.create_led_strip({"device_id": device["id"], "name": "b", "gpio_num": 8})


def test_save_led_mappings_validates_and_normalizes(repo, sample_box_id):
    device, strip = _led_mapping(repo, sample_box_id)
    mappings = repo.get_led_mappings()
    assert mappings[0]["color"] == "#ffaa00"

    with pytest.raises(InventoryError):
        repo.save_led_mappings([{"box_id": 999, "strip_id": strip["id"], "led_index": 1}])
    with pytest.raises(InventoryError):
        repo.save_led_mappings([{"box_id": sample_box_id, "strip_id": strip["id"], "led_index": 99}])

    other_box = repo.create_box({"name": "Other Box", "rows": 1, "cols": 1})
    with pytest.raises(InventoryError):
        repo.save_led_mappings(
            [
                {"box_id": sample_box_id, "strip_id": strip["id"], "led_index": 1},
                {"box_id": other_box["id"], "strip_id": strip["id"], "led_index": 1},
            ]
        )


def test_locate_box_paths(repo, file_logger, sample_box_id):
    service = LedService(repo, file_logger, FakeLedProxy())
    with pytest.raises(InventoryError, match="未配置"):
        service.locate_box(sample_box_id)

    device, _strip = _led_mapping(repo, sample_box_id)
    repo.update_led_device(device["id"], {"enabled": False, "name": device["name"], "host": device["host"], "port": device["port"]})
    with pytest.raises(InventoryError, match="未启用"):
        service.locate_box(sample_box_id)

    repo.update_led_device(device["id"], {"enabled": True, "name": device["name"], "host": device["host"], "port": device["port"]})
    proxy = FakeLedProxy()
    result = LedService(repo, file_logger, proxy).locate_box(sample_box_id)
    assert result["led_count"] == 1
    assert proxy.set_calls[0][1][0]["gpio"] == 8
    assert proxy.set_calls[0][1][0]["color"] == "#ffaa00"


def test_locate_component_without_box(repo, file_logger, sample_component_id):
    with pytest.raises(InventoryError, match="未关联收纳盒"):
        LedService(repo, file_logger, FakeLedProxy()).locate_component(sample_component_id)


def test_locate_bom_groups_by_device_and_reports_partial_errors(repo, file_logger, sample_box_id):
    device, strip = _led_mapping(repo, sample_box_id)
    other_box = repo.create_box({"name": "BOM Box", "rows": 1, "cols": 1})
    bad_device = repo.create_led_device({"name": "bad-device", "host": "192.168.1.99"})
    bad_strip = repo.create_led_strip({"device_id": bad_device["id"], "name": "bad", "gpio_num": 6, "led_count": 10})
    repo.save_led_mappings(
        [
            {"box_id": sample_box_id, "strip_id": strip["id"], "led_index": 2, "color": "#00ff00"},
            {"box_id": other_box["id"], "strip_id": bad_strip["id"], "led_index": 3, "color": "#ff0000"},
        ]
    )
    proxy = FakeLedProxy({"bad-device"})
    result = LedService(repo, file_logger, proxy).locate_bom([sample_box_id, other_box["id"], 999, sample_box_id])
    assert result["led_count"] == 1
    assert result["box_ids"] == [sample_box_id, other_box["id"]]
    assert result["errors"]
    assert len(proxy.set_calls) == 1


def test_led_settings_api(client, sample_box_id):
    resp = client.get("/api/settings/led")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["config"]["enabled"] == 0

    resp = client.put("/api/settings/led", json={"enabled": True, "blink_duration_ms": 1500})
    assert resp.status_code == 200
    assert resp.get_json()["data"]["enabled"] == 1

    device = client.post("/api/settings/led/devices", json={"name": "api-device", "host": "127.0.0.1"}).get_json()["data"]
    strip = client.post(
        "/api/settings/led/strips",
        json={"device_id": device["id"], "name": "api-strip", "gpio_num": 5, "led_count": 8},
    ).get_json()["data"]
    resp = client.put(
        "/api/settings/led/mappings",
        json={"mappings": [{"box_id": sample_box_id, "strip_id": strip["id"], "led_index": 0, "color": "#ABCDEF"}]},
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"][0]["color"] == "#abcdef"


# ── 灯带同步测试 ──


def test_create_strip_syncs_to_esp32(repo, file_logger):
    device = repo.create_led_device({"name": "desk", "host": "192.168.1.50", "port": 80})
    proxy = FakeLedProxy()
    service = LedService(repo, file_logger, proxy)
    strip = service.create_strip_with_sync({"device_id": device["id"], "name": "top", "gpio_num": 8, "led_count": 30})
    assert "sync_warning" not in strip
    assert len(proxy.push_strip_calls) == 1
    assert proxy.push_strip_calls[0][1] == 8
    assert proxy.push_strip_calls[0][2] == 30


def test_create_strip_sync_failure_returns_warning(repo, file_logger):
    device = repo.create_led_device({"name": "offline", "host": "192.168.1.99", "port": 80})
    proxy = FakeLedProxy({"offline"})
    service = LedService(repo, file_logger, proxy)
    strip = service.create_strip_with_sync({"device_id": device["id"], "name": "top", "gpio_num": 8, "led_count": 30})
    assert "sync_warning" in strip
    assert repo.list_led_strips()[0]["gpio_num"] == 8


def test_create_strip_skips_sync_when_device_disabled(repo, file_logger):
    device = repo.create_led_device({"name": "desk", "host": "192.168.1.50", "port": 80, "enabled": False})
    proxy = FakeLedProxy()
    service = LedService(repo, file_logger, proxy)
    strip = service.create_strip_with_sync({"device_id": device["id"], "name": "top", "gpio_num": 8, "led_count": 30})
    assert "sync_warning" not in strip
    assert len(proxy.push_strip_calls) == 0


def test_update_strip_syncs_to_esp32(repo, file_logger):
    device = repo.create_led_device({"name": "desk", "host": "192.168.1.50", "port": 80})
    strip = repo.create_led_strip({"device_id": device["id"], "name": "top", "gpio_num": 8, "led_count": 10})
    proxy = FakeLedProxy()
    service = LedService(repo, file_logger, proxy)
    updated = service.update_strip_with_sync(strip["id"], {"device_id": device["id"], "name": "top", "gpio_num": 8, "led_count": 30})
    assert "sync_warning" not in updated
    assert proxy.push_strip_calls[0][2] == 30


def test_delete_strip_syncs_to_esp32(repo, file_logger):
    device = repo.create_led_device({"name": "desk", "host": "192.168.1.50", "port": 80})
    strip = repo.create_led_strip({"device_id": device["id"], "name": "top", "gpio_num": 8, "led_count": 10})
    proxy = FakeLedProxy()
    service = LedService(repo, file_logger, proxy)
    result = service.delete_strip_with_sync(strip["id"])
    assert "sync_warning" not in result
    assert len(proxy.remove_strip_calls) == 1
    assert proxy.remove_strip_calls[0][1] == 8
    assert repo.list_led_strips() == []


def test_delete_strip_sync_failure_returns_warning(repo, file_logger):
    device = repo.create_led_device({"name": "offline", "host": "192.168.1.99", "port": 80})
    strip = repo.create_led_strip({"device_id": device["id"], "name": "top", "gpio_num": 8, "led_count": 10})
    proxy = FakeLedProxy({"offline"})
    service = LedService(repo, file_logger, proxy)
    result = service.delete_strip_with_sync(strip["id"])
    assert "sync_warning" in result
    assert repo.list_led_strips() == []


def test_sync_device_strips_sends_full_config(repo, file_logger):
    device = repo.create_led_device({"name": "desk", "host": "192.168.1.50", "port": 80})
    repo.create_led_strip({"device_id": device["id"], "name": "a", "gpio_num": 8, "led_count": 30})
    repo.create_led_strip({"device_id": device["id"], "name": "b", "gpio_num": 6, "led_count": 20})
    proxy = FakeLedProxy()
    service = LedService(repo, file_logger, proxy)
    result = service.sync_device_strips(device["id"])
    assert result["synced_strips"] == 2
    assert len(proxy.push_full_config_calls) == 1
    strips = proxy.push_full_config_calls[0][1]
    assert {"gpio": 8, "led_count": 30} in strips
    assert {"gpio": 6, "led_count": 20} in strips


def test_sync_device_strips_includes_linked_nfc_config(repo, file_logger):
    device = repo.create_led_device({"name": "combo", "host": "192.168.1.60", "port": 80})
    repo.create_led_strip({"device_id": device["id"], "name": "a", "gpio_num": 8, "led_count": 30})
    repo.create_nfc_device(
        {
            "name": "combo-nfc",
            "host": "192.168.1.60",
            "linked_led_device_id": device["id"],
            "module_type": "PN532",
            "allow_erase": True,
        }
    )
    proxy = FakeLedProxy()
    result = LedService(repo, file_logger, proxy).sync_device_strips(device["id"])
    assert result["synced_strips"] == 1
    extra_config = proxy.push_full_config_calls[0][3]
    assert extra_config["nfc"]["device_name"] == "combo-nfc"
    assert extra_config["nfc"]["operation"]["allow_erase"] is True


def test_sync_device_strips_reports_esp32_error(repo, file_logger):
    device = repo.create_led_device({"name": "offline", "host": "192.168.1.99", "port": 80})
    repo.create_led_strip({"device_id": device["id"], "name": "a", "gpio_num": 8, "led_count": 30})
    proxy = FakeLedProxy({"offline"})
    service = LedService(repo, file_logger, proxy)
    result = service.sync_device_strips(device["id"])
    assert "sync_error" in result


def test_sync_device_strips_requires_enabled_device(repo, file_logger):
    device = repo.create_led_device({"name": "desk", "host": "192.168.1.50", "port": 80, "enabled": False})
    proxy = FakeLedProxy()
    service = LedService(repo, file_logger, proxy)
    with pytest.raises(InventoryError, match="未启用"):
        service.sync_device_strips(device["id"])
