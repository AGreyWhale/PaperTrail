from app.api.papers import get_doi_lookup_service
from app.main import app
from app.schemas.paper import PaperCreate


class _FakeDoiLookupService:
    async def lookup(self, doi: str) -> PaperCreate:
        return PaperCreate(
            title="Attention Is All You Need",
            authors=["Ashish Vaswani", "Noam Shazeer"],
            venue="NeurIPS",
            year=2017,
        )


def test_lookup_by_doi_returns_preview(client):
    app.dependency_overrides[get_doi_lookup_service] = lambda: _FakeDoiLookupService()

    response = client.get("/api/papers/lookup", params={"doi": "10.1038/nphys1170"})

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Attention Is All You Need"
    assert body["year"] == 2017


def test_lookup_does_not_save_anything(client):
    app.dependency_overrides[get_doi_lookup_service] = lambda: _FakeDoiLookupService()

    client.get("/api/papers/lookup", params={"doi": "10.1038/nphys1170"})

    # A lookup is a preview only — nothing should have been persisted.
    list_response = client.get("/api/papers")
    assert list_response.json() == []


def test_lookup_requires_authentication():
    from app.core.auth import get_current_user_id

    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides[get_doi_lookup_service] = lambda: _FakeDoiLookupService()

    from fastapi.testclient import TestClient

    with TestClient(app) as unauth_client:
        response = unauth_client.get("/api/papers/lookup", params={"doi": "10.1038/nphys1170"})

    assert response.status_code == 401
    app.dependency_overrides.clear()
