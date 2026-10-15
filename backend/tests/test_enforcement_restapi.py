"""Hooks A and C through plone.restapi."""

from collective.quota.usage import get_total_usage

import base64
import pytest
import transaction


MB = 1024 * 1024
KB = 1024
UPLOAD_BLOCKED = "This file cannot be saved: the site has reached its disk quota"
ADD_BLOCKED = "New content cannot be added: the site has reached its disk quota"


@pytest.fixture
def site(functional_portal, make_file, set_quota):
    def func(hard_mb=1, policy="block_files", files=None):
        for name, size in (files or {}).items():
            make_file(functional_portal, name, size)
        set_quota(hard_mb=hard_mb, policy=policy)
        transaction.commit()
        return functional_portal

    return func


def file_payload(size, filename="f.bin"):
    return {
        "data": base64.b64encode(b"\0" * size).decode(),
        "encoding": "base64",
        "filename": filename,
        "content-type": "application/octet-stream",
    }


def committed_ids(portal):
    transaction.begin()
    return portal.objectIds()


def total(portal):
    transaction.begin()
    return get_total_usage(portal)


class TestUploads:
    def test_post_file_over_limit_400(self, site, api_session):
        portal = site(hard_mb=1)
        response = api_session("Contributor").post(
            "/", json={"@type": "File", "id": "big", "file": file_payload(2 * MB)}
        )
        assert response.status_code == 400
        assert UPLOAD_BLOCKED in response.text
        assert "(0 KB of 1.0 MB)" in response.text
        assert "'field': 'file'" in response.text
        assert "big" not in committed_ids(portal)

    def test_post_file_within_limit_201(self, site, api_session):
        portal = site(hard_mb=1)
        response = api_session("Contributor").post(
            "/", json={"@type": "File", "id": "small", "file": file_payload(100 * KB)}
        )
        assert response.status_code == 201
        assert total(portal) == 100 * KB

    def test_patch_file_over_limit_400(self, site, api_session):
        portal = site(hard_mb=1, files={"a": 100 * KB})
        response = api_session("Editor").patch(
            "/a", json={"file": file_payload(2 * MB)}
        )
        assert response.status_code == 400
        assert UPLOAD_BLOCKED in response.text
        assert total(portal) == 100 * KB

    def test_patch_resend_representation_allowed(self, site, api_session):
        portal = site(hard_mb=1, policy="block_all", files={"a": 2 * MB})
        session = api_session("Editor")
        current = session.get("/a").json()["file"]
        assert "download" in current
        response = session.patch("/a", json={"title": "Renamed", "file": current})
        assert response.status_code == 204
        assert total(portal) == 2 * MB

    def test_patch_replace_with_smaller_allowed(self, site, api_session):
        portal = site(hard_mb=1, policy="block_all", files={"a": 2 * MB})
        response = api_session("Editor").patch(
            "/a", json={"file": file_payload(500 * KB)}
        )
        assert response.status_code == 204
        assert total(portal) == 500 * KB


class TestAdds:
    @pytest.mark.parametrize(
        "policy,status", [("block_all", 400), ("block_files", 201)]
    )
    def test_post_document_blocked_under_block_all(
        self, site, api_session, policy, status
    ):
        portal = site(hard_mb=1, policy=policy, files={"a": 2 * MB})
        response = api_session("Contributor").post(
            "/", json={"@type": "Document", "id": "doc", "title": "Doc"}
        )
        assert response.status_code == status
        assert (ADD_BLOCKED in response.text) is (status == 400)
        assert ("doc" in committed_ids(portal)) is (status == 201)

    def test_post_into_folder_uses_container_deserializer(self, site, api_session):
        portal = site(hard_mb=1, policy="block_all", files={"a": 2 * MB})
        response = api_session("Contributor").post(
            "/", json={"@type": "Folder", "id": "folder", "title": "Folder"}
        )
        assert response.status_code == 400
        assert ADD_BLOCKED in response.text
        assert "folder" not in committed_ids(portal)

    def test_post_allowed_under_the_limit(self, site, api_session):
        portal = site(hard_mb=10, policy="block_all", files={"a": 2 * MB})
        response = api_session("Contributor").post(
            "/", json={"@type": "Document", "id": "doc", "title": "Doc"}
        )
        assert response.status_code == 201
        assert "doc" in committed_ids(portal)

    def test_transaction_aborted_on_400(self, site, api_session):
        """Field errors after creation leave no partial object behind."""
        portal = site(hard_mb=1)
        response = api_session("Contributor").post(
            "/",
            json={
                "@type": "File",
                "id": "partial",
                "title": "Partial",
                "file": file_payload(2 * MB),
            },
        )
        assert response.status_code == 400
        assert "partial" not in committed_ids(portal)
        assert total(portal) == 0


class TestTus:
    def _upload(self, session, size, monkeypatch, tmp_path):
        monkeypatch.setenv("TUS_TMP_FILE_DIR", str(tmp_path))
        metadata = ",".join(
            f"{key} {base64.b64encode(value.encode()).decode()}"
            for key, value in (
                ("filename", "tus.bin"),
                ("content-type", "application/octet-stream"),
                ("@type", "File"),
            )
        )
        headers = {"Tus-Resumable": "1.0.0", "Accept": "application/json"}
        created = session.post(
            "/@tus-upload",
            headers={
                **headers,
                "Upload-Length": str(size),
                "Upload-Metadata": metadata,
            },
        )
        assert created.status_code == 201
        location = created.headers["Location"].split("/++api++", 1)[1]
        return session.patch(
            location,
            data=b"\0" * size,
            headers={
                **headers,
                "Upload-Offset": "0",
                "Content-Type": "application/offset+octet-stream",
            },
        )

    def test_tus_upload_over_limit_400(self, site, api_session, monkeypatch, tmp_path):
        portal = site(hard_mb=1)
        response = self._upload(
            api_session("Contributor"), 2 * MB, monkeypatch, tmp_path
        )
        assert response.status_code == 400
        assert UPLOAD_BLOCKED in response.text
        assert "tus.bin" not in committed_ids(portal)
        assert total(portal) == 0

    def test_tus_upload_within_limit(self, site, api_session, monkeypatch, tmp_path):
        portal = site(hard_mb=1)
        response = self._upload(
            api_session("Contributor"), 100 * KB, monkeypatch, tmp_path
        )
        assert response.status_code == 204
        assert total(portal) == 100 * KB
