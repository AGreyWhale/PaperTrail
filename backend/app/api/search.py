from fastapi import APIRouter, Depends, Query

from app.api.papers import get_search_service
from app.core.auth import get_current_user_id
from app.schemas.paper import ScopedSearchRequest, SearchHitOut
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])

@router.get("", response_model=list[SearchHitOut])
def search_library(
    q: str = Query(..., min_length=1, description="Natural-language query"),
    limit: int = Query(10, ge=1, le=50),
    user_id: str = Depends(get_current_user_id),
    service: SearchService = Depends(get_search_service),
) -> list[SearchHitOut]:
    #Top-level, not paper-scoped: searches every embedded paper the user owns
    return service.search_library(owner_id=user_id, query=q, limit=limit)


@router.post("/selection", response_model=list[SearchHitOut])
def search_within_selection(
    data: ScopedSearchRequest,
    user_id: str = Depends(get_current_user_id),
    service: SearchService = Depends(get_search_service),
) -> list[SearchHitOut]:
    #Same grouping and snippets as library search, restricted to a selection
    return service.search_library(
        owner_id=user_id, query=data.q, limit=data.limit, paper_ids=data.paper_ids
    )
