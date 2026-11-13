import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestHealthAndPwa:
    def test_health_check_endpoint(self, client):
        response = client.get(reverse("health_check"))
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "itwadura-inventory"
        assert "SECRET_KEY" not in data  # No secrets exposed

    def test_offline_fallback_endpoint(self, client):
        response = client.get(reverse("offline_fallback"))
        assert response.status_code == 503
        assert b"offline" in response.content.lower()

    def test_pwa_manifest_file(self):
        from pathlib import Path

        manifest_path = Path("static/manifest.webmanifest")
        assert manifest_path.exists()
        content = manifest_path.read_text(encoding="utf-8")
        assert "Itwadura Inventory" in content
        assert "standalone" in content

    def test_service_worker_file(self):
        from pathlib import Path

        sw_path = Path("static/sw.js")
        assert sw_path.exists()
        content = sw_path.read_text(encoding="utf-8")
        assert "itwadura-static-v1" in content
