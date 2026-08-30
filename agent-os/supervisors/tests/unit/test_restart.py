"""`domain/restart.py` -- doc 12 §9's three restart strategies."""

from __future__ import annotations

from uuid import uuid4

import pytest
from nova_agent_os_supervisors.domain.models import RestartStrategy, SupervisedInstance
from nova_agent_os_supervisors.domain.restart import plan_restart


def _instance(order: int, status: str = "running") -> SupervisedInstance:
    return SupervisedInstance(
        id=uuid4(),
        category="coding",
        restart_strategy=RestartStrategy.ONE_FOR_ONE,
        started_order=order,
        status=status,
    )


def test_one_for_one_restarts_only_the_failed_instance() -> None:
    a, b, c = _instance(0), _instance(1), _instance(2)
    failed = b.model_copy(update={"status": "failed"})
    siblings = [a, failed, c]

    result = plan_restart(
        strategy=RestartStrategy.ONE_FOR_ONE, failed_instance_id=failed.id, siblings=siblings
    )

    assert result == [failed.id]


def test_one_for_all_restarts_every_sibling_in_started_order() -> None:
    a, b, c = _instance(2), _instance(0), _instance(1)
    failed = a.model_copy(update={"status": "failed"})
    siblings = [failed, b, c]

    result = plan_restart(
        strategy=RestartStrategy.ONE_FOR_ALL, failed_instance_id=failed.id, siblings=siblings
    )

    assert result == [b.id, c.id, failed.id]


def test_one_for_all_excludes_already_completed_siblings() -> None:
    a, b, c = _instance(0), _instance(1, status="completed"), _instance(2)
    failed = a.model_copy(update={"status": "failed"})
    siblings = [failed, b, c]

    result = plan_restart(
        strategy=RestartStrategy.ONE_FOR_ALL, failed_instance_id=failed.id, siblings=siblings
    )

    assert result == [failed.id, c.id]


def test_rest_for_one_restarts_the_failed_instance_and_everything_after_it() -> None:
    a, b, c, d = _instance(0), _instance(1), _instance(2), _instance(3)
    failed = b.model_copy(update={"status": "failed"})
    siblings = [a, failed, c, d]

    result = plan_restart(
        strategy=RestartStrategy.REST_FOR_ONE, failed_instance_id=failed.id, siblings=siblings
    )

    assert result == [failed.id, c.id, d.id]


def test_rest_for_one_never_restarts_instances_started_before_the_failure() -> None:
    a, b = _instance(0), _instance(1)
    failed = b.model_copy(update={"status": "failed"})
    siblings = [a, failed]

    result = plan_restart(
        strategy=RestartStrategy.REST_FOR_ONE, failed_instance_id=failed.id, siblings=siblings
    )

    assert a.id not in result


def test_raises_when_failed_instance_is_not_among_siblings() -> None:
    a = _instance(0)

    with pytest.raises(ValueError, match="not among siblings"):
        plan_restart(strategy=RestartStrategy.ONE_FOR_ONE, failed_instance_id=uuid4(), siblings=[a])
