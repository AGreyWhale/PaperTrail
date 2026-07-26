import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security import AuthenticateRequestOptions
from fastapi import HTTPException, Request, status

from app.core.config import get_settings

settings = get_settings()

_clerk_client = Clerk(bearer_auth=settings.clerk_secret_key)

def get_current_user_id(request: Request) -> str:
    httpx_request = httpx.Request(
        method=request.method,
        url=str(request.url),
        headers=request.headers.raw,
    )

    request_state = _clerk_client.authenticate_request(
        httpx_request,
        AuthenticateRequestOptions(
            authorized_parties=settings.clerk_authorized_parties_list,
        ),
    )

    if not request_state.is_signed_in:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = request_state.payload.get("sub") if request_state.payload else None
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    return user_id