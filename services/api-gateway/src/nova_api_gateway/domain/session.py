"""Session validation -- Phase 4 decision **D-3**.

Doc 13 specifies an Ed25519 device keypair (local-first) or OIDC + PKCE
(enterprise), both behind a `nova-auth` interface. **`nova-auth` does not
exist**; full OIDC is a Phase 7 deliverable. Building an identity provider
now would be scope creep far beyond 4A.

The approved Phase-4-scoped mechanism, grounded in **ADR-025**
(single-trusted-user-per-instance): a single long-lived local token,
generated at first run, presented once, and thereafter carried in an
httpOnly cookie. No multi-user concept, no RBAC, no external IdP.

This is a disclosed, bounded departure from doc 13's eventual design -- not
a redesign of it, and not a security regression: no web client existed
before, so there is no prior posture being weakened.

`SessionValidator` is the seam that keeps it that way. Phase 7 replaces the
implementation without touching a single route handler.
"""

from __future__ import annotations

import hmac
from typing import Protocol


class SessionValidator(Protocol):
    """The one thing route handlers may ask about authentication."""

    def is_valid(self, presented: str | None) -> bool: ...

    @property
    def configured(self) -> bool:
        """False when no credential is provisioned, so callers can fail closed."""
        ...


class LocalTokenSessionValidator:
    """Constant-time comparison against the instance's single local token.

    An unconfigured (empty) token makes every check fail rather than pass.
    A gateway with no credential provisioned must refuse requests, not serve
    them unauthenticated -- the failure mode has to be closed, because the
    alternative silently exposes every fronted engine.
    """

    def __init__(self, token: str) -> None:
        self._token = token

    @property
    def configured(self) -> bool:
        return bool(self._token)

    def is_valid(self, presented: str | None) -> bool:
        if not self.configured or not presented:
            return False
        # compare_digest to keep the comparison constant-time; the token is a
        # long-lived shared secret, so a timing oracle here would be real.
        return hmac.compare_digest(self._token, presented)


def extract_presented_token(
    cookie_value: str | None, authorization_header: str | None
) -> str | None:
    """Read the token from the cookie, or from a `Bearer` header.

    The cookie is how the browser authenticates (httpOnly, per doc 04 §5).
    The header exists for non-browser callers -- tests, curl, the Phase 5
    desktop shell -- which cannot hold cookies as naturally.
    """
    if cookie_value:
        return cookie_value
    if authorization_header:
        scheme, _, credential = authorization_header.partition(" ")
        if scheme.lower() == "bearer" and credential:
            return credential
    return None
