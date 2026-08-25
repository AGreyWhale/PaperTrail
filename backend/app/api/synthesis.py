from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.papers import get_llm_client, get_search_service
from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.integrations.llm.client import LLMClient
from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import (
    ComparisonOut,
    LiteratureReviewOut,
    MultiAskAnswerOut,
    MultiAskRequest,
    MultiPaperRequest,
)
from app.services.compare_service import CompareService
from app.services.literature_review_service import LiteratureReviewService
from app.services.multi_ask_service import MultiAskService
from app.services.search_service import SearchService

router = APIRouter(prefix="/papers", tags=["synthesis"])

def get_compare_service(
    db: Session = Depends(get_db),
    search_service: SearchService = Depends(get_search_service),
    llm_client: LLMClient = Depends(get_llm_client),
) -> CompareService:
    return CompareService(PaperRepository(db), search_service, llm_client)

def get_literature_review_service(
    db: Session = Depends(get_db),
    search_service: SearchService = Depends(get_search_service),
    llm_client: LLMClient = Depends(get_llm_client),
) -> LiteratureReviewService:
    return LiteratureReviewService(PaperRepository(db), search_service, llm_client)

@router.post("/compare", response_model=ComparisonOut)
def compare_papers(
    data: MultiPaperRequest,
    user_id: str = Depends(get_current_user_id),
    service: CompareService = Depends(get_compare_service),
) -> ComparisonOut:
    #Structured rows, not markdown, so the frontend renders a real table
    return service.compare(data.paper_ids, owner_id=user_id)

@router.post("/literature-review", response_model=LiteratureReviewOut)
def generate_literature_review(
    data: MultiPaperRequest,
    user_id: str = Depends(get_current_user_id),
    service: LiteratureReviewService = Depends(get_literature_review_service),
) -> LiteratureReviewOut:
    return service.generate(data.paper_ids, owner_id=user_id)


def get_multi_ask_service(
    db: Session = Depends(get_db),
    search_service: SearchService = Depends(get_search_service),
    llm_client: LLMClient = Depends(get_llm_client),
) -> MultiAskService:
    return MultiAskService(PaperRepository(db), search_service, llm_client)

@router.post("/ask-multiple", response_model=MultiAskAnswerOut)
def ask_across_papers(
    data: MultiAskRequest,
    user_id: str = Depends(get_current_user_id),
    service: MultiAskService = Depends(get_multi_ask_service),
) -> MultiAskAnswerOut:
    #Distinct path from /{paper_id}/ask, which stays single-paper
    return service.ask(data.paper_ids, owner_id=user_id, question=data.question)
