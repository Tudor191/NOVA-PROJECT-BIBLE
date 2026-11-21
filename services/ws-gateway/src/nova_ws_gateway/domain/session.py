"""Session validation for the realtime surface -- decision **D-3**.

Deliberately a copy of `api-gateway`'s validator rather than an import.
The ADR-004 independence contract forbids one service importing another's
top-level package, and `uv run lint-imports` enforces it, so the two
external surfaces of a single instance cannot share this code directly.

**Known follow-up, recorded rather than hidden:** two copies of a security
primitive can drift. The architecture-consistent home for it is
`nova-service-kit`, which exists precisely for shared service concerns with
no engine-specific knowledge (ADR-034) -- a token comparison qualifies.
That extraction is not done here because it would widen 4A into a shared
Phase 3 package mid-milestone; it is flagged for 4B.

Both copies must keep the same two properties: an unconfigured validator
refuses everything, and comparison is constant-time.
"""

from __future__ import annotations

import hmac


class LocalTokenSessionValidator:
    def __init__(self, token: str) -> None:
        self._token = token

    @property
    def configured(self) -> bool:
        return bool(self._token)

    def is_valid(self, presented: str | None) -> bool:
        if not self.configured or not presented:
            return False
        return hmac.compare_digest(self._token, presented)


def extract_presented_token(
    cookie_value: str | None, authorization_header: str | None
) -> str | None:
    """Cookie first (the browser path), then a `Bearer` header.

    A WebSocket handshake carries cookies like any other HTTP request, so the
    browser needs no special handling and the token never has to be placed in
    a query string -- which would leak it into access logs and referrers.
    """
    if cookie_value:
        return cookie_value
    if authorization_header:
        scheme, _, credential = authorization_header.partition(" ")
        if scheme.lower() == "bearer" and credential:
            return credential
    return None
