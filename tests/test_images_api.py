from __future__ import annotations

from tests.conftest import make_test_image


class TestUploadImage:
    def test_upload_success(self, client, tmp_dirs):
        img_buf = make_test_image()
        data = {"file": (img_buf, "test.png")}
        resp = client.post("/api/images/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        result = resp.get_json()["data"]
        assert "id" in result
        assert "url" in result

    def test_upload_with_component_id(self, client, sample_component_id):
        img_buf = make_test_image()
        data = {"file": (img_buf, "test.png"), "component_id": str(sample_component_id)}
        resp = client.post("/api/images/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["component_id"] == sample_component_id

    def test_upload_missing_file_error(self, client):
        resp = client.post("/api/images/upload")
        assert resp.get_json()["code"] == 1

    def test_upload_invalid_extension_error(self, client):
        import io

        buf = io.BytesIO(b"not an image")
        buf.name = "test.exe"
        data = {"file": (buf, "test.exe")}
        resp = client.post("/api/images/upload", data=data, content_type="multipart/form-data")
        assert resp.get_json()["code"] == 1


class TestDeleteImage:
    def test_delete_success(self, client, sample_component_id, tmp_dirs):
        img_buf = make_test_image()
        data = {"file": (img_buf, "test.png"), "component_id": str(sample_component_id)}
        create_resp = client.post("/api/images/upload", data=data, content_type="multipart/form-data")
        image_id = create_resp.get_json()["data"]["id"]

        resp = client.delete(f"/api/images/{image_id}")
        assert resp.status_code == 200

    def test_delete_not_found_error(self, client):
        resp = client.delete("/api/images/99999")
        assert resp.get_json()["code"] == 1
