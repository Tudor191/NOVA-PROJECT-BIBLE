"""Session exchange -- decision **D-3**.

The instance's single long-lived local token is presented once here and
exchanged for an httpOnly cookie (doc 04 §5's `useSession()` row). The token
itself never reaches JavaScript.

This is the whole of Phase 4's auth surface. There is no registration, no
refresh rotation, no password, and no external identity provider. Phase 7's
`nova-auth` replaces it behind `SessionValidator` without touching routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from nova_api_gateway.domain.envelope import (
    Envelope,
    SessionIssueRequest,
    SessionState,
    failure,
    new_correlation_id,
    success,
)
from nova_api_gateway.domain.session import extract_presented_token

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/session", response_model=Envelope)
async def issue_session(body: SessionIssueRequest, request: Request) -> Response:
    validator = request.app.state.session_validator
    settings = request.app.state.settings
    correlation_id = new_correlation_id()

    if not validator.configured:
        # Fail closed and say so. An unconfigured gateway must not look like
        # a rejected password -- the operator needs to know the difference.
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=failure(
                "session_not_configured",
                "No local session token is provisioned for this instance.",
                correlation_id,
            ).model_dump(mode="json"),
        )

    if not validator.is_valid(body.token):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=failure(
                "invalid_token", "The presented session token is not valid.", correlation_id
            ).model_dump(mode="json"),
        )

    response = JSONResponse(
        content=success(
            SessionState(authenticated=True).model_dump(mode="json"), correlation_id
        ).model_dump(mode="json")
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=body.token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="strict",
        max_age=settings.session_cookie_max_age_seconds,
        path="/",
    )
    return response


@router.get("/session", response_model=Envelope)
async def read_session(request: Request) -> Response:
    """Whether the caller currently holds a valid session.

    The web client uses this on boot to decide between the shell and the
    first-run token prompt, without having to provoke a 401 on a real
    endpoint first.
    """
    settings = request.app.state.settings
    validator = request.app.state.session_validator
    presented = extract_presented_token(
        request.cookies.get(settings.session_cookie_name),
        request.headers.get("authorization"),
    )
    authenticated = validator.is_valid(presented)
    return JSONResponse(
        content=success(
            SessionState(authenticated=authenticated).model_dump(mode="json"),
            new_correlation_id(),
        ).model_dump(mode="json")
    )


@router.delete("/session", response_model=Envelope)
async def end_session(request: Request) -> Response:
    settings = request.app.state.settings
    response = JSONResponse(
        content=success(
            SessionState(authenticated=False).model_dump(mode="json"),
            new_correlation_id(),
        ).model_dump(mode="json")
    )
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    return response
