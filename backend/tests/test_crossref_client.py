import httpx
import pytest

from app.integrations.crossref.client import (
    CrossRefClient,
    CrossRefNotFoundError,
    CrossRefUnavailableError,
    normalize_doi,
)


def _client_with_response(handler) -> CrossRefClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return CrossRefClient(http_client=http_client)


@pytest.mark.anyio
async def test_get_work_returns_message_on_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok", "message": {"title": ["A Paper"]}})

    client = _client_with_response(handler)
    result = await client.get_work("10.1038/nphys1170")

    assert result == {"title": ["A Paper"]}


@pytest.mark.anyio
async def test_get_work_raises_not_found_on_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"status": "not-found"})

    client = _client_with_response(handler)

    with pytest.raises(CrossRefNotFoundError):
        await client.get_work("10.9999/does-not-exist")


@pytest.mark.anyio
async def test_get_work_raises_unavailable_on_server_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = _client_with_response(handler)

    with pytest.raises(CrossRefUnavailableError):
        await client.get_work("10.1038/nphys1170")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("10.1038/nphys1170", "10.1038/nphys1170"),
        ("https://doi.org/10.1038/nphys1170", "10.1038/nphys1170"),
        ("http://dx.doi.org/10.1038/nphys1170", "10.1038/nphys1170"),
        ("doi:10.1038/nphys1170", "10.1038/nphys1170"),
        ("  10.1038/nphys1170  ", "10.1038/nphys1170"),
    ],
)
def test_normalize_doi(raw, expected):
    assert normalize_doi(raw) == expected
