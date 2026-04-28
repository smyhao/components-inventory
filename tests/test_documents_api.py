from __future__ import annotations

import io


def make_test_pdf(filename="test.pdf"):
    buf = io.BytesIO(b"%PDF-1.4 test content")
    buf.seek(0)
    buf.name = filename
    return buf


class TestUploadDocument:
    def test_upload_success(self, client, tmp_dirs):
        pdf_buf = make_test_pdf()
        data = {"file": (pdf_buf, "test.pdf")}
        resp = client.post("/api/documents/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        result = resp.get_json()["data"]
        assert "id" in result
        assert "name" in result

    def test_upload_with_component_id(self, client, sample_component_id):
        pdf_buf = make_test_pdf()
        data = {"file": (pdf_buf, "test.pdf"), "component_id": str(sample_component_id)}
        resp = client.post("/api/documents/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["component_id"] == sample_component_id

    def test_upload_missing_file_error(self, client):
        resp = client.post("/api/documents/upload")
        assert resp.get_json()["code"] == 1

    def test_upload_invalid_extension_error(self, client):
        buf = io.BytesIO(b"bad content")
        buf.name = "test.exe"
        data = {"file": (buf, "test.exe")}
        resp = client.post("/api/documents/upload", data=data, content_type="multipart/form-data")
        assert resp.get_json()["code"] == 1


class TestDeleteDocument:
    def test_delete_success(self, client, sample_component_id):
        pdf_buf = make_test_pdf()
        data = {"file": (pdf_buf, "test.pdf"), "component_id": str(sample_component_id)}
        create_resp = client.post("/api/documents/upload", data=data, content_type="multipart/form-data")
        doc_id = create_resp.get_json()["data"]["id"]

        resp = client.delete(f"/api/documents/{doc_id}")
        assert resp.status_code == 200

    def test_delete_not_found_error(self, client):
        resp = client.delete("/api/documents/99999")
        assert resp.get_json()["code"] == 1
