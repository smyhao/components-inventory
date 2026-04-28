from __future__ import annotations


class TestNFCBind:
    def test_bind_success(self, client, sample_box_id):
        resp = client.post(
            "/api/nfc/bind",
            json={"box_id": sample_box_id, "uid": "ABC123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["uid"] == "ABC123"

    def test_bind_missing_uid_error(self, client, sample_box_id):
        resp = client.post(
            "/api/nfc/bind",
            json={"box_id": sample_box_id},
        )
        assert resp.get_json()["code"] == 1

    def test_bind_box_not_found_error(self, client):
        resp = client.post(
            "/api/nfc/bind",
            json={"box_id": 99999, "uid": "XYZ"},
        )
        assert resp.get_json()["code"] == 1


class TestNFCWrite:
    def test_write_returns_payload(self, client, sample_box_id):
        resp = client.post(
            "/api/nfc/write",
            json={"box_id": sample_box_id},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "url" in data
        assert "text" in data

    def test_write_box_not_found_error(self, client):
        resp = client.post(
            "/api/nfc/write",
            json={"box_id": 99999},
        )
        assert resp.get_json()["code"] == 1


class TestNFCLookup:
    def test_lookup_success(self, client, sample_box_id):
        client.post(
            "/api/nfc/bind",
            json={"box_id": sample_box_id, "uid": "LOOKUP123"},
        )
        resp = client.get("/api/nfc/lookup/LOOKUP123")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["box"]["id"] == sample_box_id

    def test_lookup_not_found_error(self, client):
        resp = client.get("/api/nfc/lookup/NONEXISTENT")
        assert resp.get_json()["code"] == 1


class TestNFCBoxData:
    def test_returns_grid(self, client, sample_box_id):
        resp = client.get(f"/api/box/{sample_box_id}")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "cells" in data
