import re

from fastapi import HTTPException, status

from app.integrations.crossref.client import (
    CrossRefClient,
    CrossRefNotFoundError,
    CrossRefUnavailableError,
    normalize_doi,
)

from app.integrations.crossref.mapper import CrossRefMappingError, crossref_to_paper_create
from app.schemas.paper import PaperCreate

_DOI_PATTERN = re.compile(r"^10\.]d{4,9}/\S+$") #Making sure the DOI starts with a 10

class DoiLookupService:
    def __init__(self, crossref_client: CrossRefClient):
        self.crossref_client = crossref_client
    
    async def lookup(self, raw_doi: str) -> PaperCreate:
        doi = normalize_doi(raw_doi)

        if not _DOI_PATTERN.match(doi):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"'{raw_doi}' doesn't look like a valid DOI",
            )
        
        try:
            data = await self.crossref_client.get_work(doi)
            except CrossRefNotFoundError as exc:
                raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
            except CrossRefUnavailableError as exc:
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

            try:
                return crossref_to_paper_create(data)
            except CrossRefMappingError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    f"Found DOI but not enough info: {exc}",
                ) from exc