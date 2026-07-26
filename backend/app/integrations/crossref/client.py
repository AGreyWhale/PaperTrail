import re

import httpx

def normalize_doi(raw: str) -> str:
    #allow any doi link to be normalized to bare crossref
    doi = raw.strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    return doi.strip()

class CrossRefNotFoundError(Exception):
    """When there is no record of given DOI"""


class CrossRefUnavailableError(Exception):
    """When CrossRef errors/times out"""

class CrossRefClient:
    #Wrapper around CrossRef's public REST API.
    #Accept optional httpx.AsyncClient for tests

    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, *, contact_email: str = "", http_client: httpx.AsyncClient | None = None):
        self._contact_email = contact_email
        self._client = http_client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = http_client is None

    async def get_work(self, doi: str) -> dict:
        params = {"mailto": self._contact_email} if self._contact_email else {}
        try:
            response = await self._client.get(f"{self.BASE_URL}/{doi}", params=params)
        except httpx.TimeoutException as exc:
            raise CrossRefUnavailableError("CrossRef request timed out") from exc
        except httpx.HTTPError as exc:
            raise CrossRefUnavailableError(f"CrossRef request failed: {exc}") from exc
        
        if response.status_code == 404:
            raise CrossRefNotFoundError(f"No CrossRef record for DOI '{doi}'")
        if response.status_code >= 400:
            raise CrossRefUnavailableError(f"CrossRef returned {response.status_code}")
        
        return response.json()["message"]
    
    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
