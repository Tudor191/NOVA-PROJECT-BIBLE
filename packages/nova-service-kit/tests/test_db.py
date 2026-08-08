from nova_service_kit.db import create_engine, create_session_factory


def test_create_engine_enables_pool_pre_ping() -> None:
    engine = create_engine("postgresql+asyncpg://user:pass@localhost/db")

    assert engine.pool._pre_ping is True


def test_create_session_factory_disables_expire_on_commit() -> None:
    engine = create_engine("postgresql+asyncpg://user:pass@localhost/db")
    session_factory = create_session_factory(engine)

    session = session_factory()
    try:
        assert session.sync_session.expire_on_commit is False
    finally:
        session.sync_session.close()
