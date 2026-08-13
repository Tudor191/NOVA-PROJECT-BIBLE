"""`SessionRegistry`'s `user_id -> connected session_id` lookup (Phase 2D-D
docs/design/phase-2d/06-personal-companion.md Sec10.2, Fork D)."""

from __future__ import annotations

from uuid import uuid4

from nova_communication_engine.session_registry import SessionRegistry

from tests.fakes.channel_adapter import FakeChannelAdapter


def test_no_registration_has_no_connected_session_for_any_user() -> None:
    registry = SessionRegistry()
    assert registry.get_connected_session_id(uuid4()) is None


def test_registering_with_a_user_id_makes_the_session_discoverable_by_user() -> None:
    registry = SessionRegistry()
    user_id = uuid4()
    session_id = uuid4()

    registry.register(session_id, FakeChannelAdapter(), user_id=user_id)

    assert registry.get_connected_session_id(user_id) == session_id


def test_registering_without_a_user_id_stays_undiscoverable_by_user() -> None:
    """Existing call sites that never needed this (this module's own prior
    tests) keep working unchanged -- `user_id` is opt-in, not required."""
    registry = SessionRegistry()
    session_id = uuid4()

    registry.register(session_id, FakeChannelAdapter())

    assert registry.get_adapter(session_id) is not None
    assert registry.get_connected_session_id(uuid4()) is None


def test_unregistering_clears_the_user_lookup() -> None:
    registry = SessionRegistry()
    user_id = uuid4()
    session_id = uuid4()
    registry.register(session_id, FakeChannelAdapter(), user_id=user_id)

    registry.unregister(session_id)

    assert registry.get_connected_session_id(user_id) is None


def test_a_new_session_for_the_same_user_replaces_the_old_lookup() -> None:
    """ADR-025's single-concurrent-session-per-instance assumption -- a
    reconnect under a new session_id is expected to supersede the old one."""
    registry = SessionRegistry()
    user_id = uuid4()
    old_session_id = uuid4()
    new_session_id = uuid4()
    registry.register(old_session_id, FakeChannelAdapter(), user_id=user_id)

    registry.register(new_session_id, FakeChannelAdapter(), user_id=user_id)

    assert registry.get_connected_session_id(user_id) == new_session_id


def test_unregistering_a_superseded_session_id_does_not_clear_the_new_lookup() -> None:
    """If the old session's own disconnect handler fires after the
    reconnect already happened, it must not clobber the newer, still-live
    mapping -- the guard compares against the *current* value, not just
    presence."""
    registry = SessionRegistry()
    user_id = uuid4()
    old_session_id = uuid4()
    new_session_id = uuid4()
    registry.register(old_session_id, FakeChannelAdapter(), user_id=user_id)
    registry.register(new_session_id, FakeChannelAdapter(), user_id=user_id)

    registry.unregister(old_session_id)

    assert registry.get_connected_session_id(user_id) == new_session_id
