from nova_world_model_engine.domain import state_management
from nova_world_model_engine.domain.models import ObjectState


def test_unknown_to_active_on_first_observation() -> None:
    assert (
        state_management.next_state_on_first_observation(ObjectState.UNKNOWN) is ObjectState.ACTIVE
    )


def test_first_observation_no_op_from_non_unknown() -> None:
    assert state_management.next_state_on_first_observation(ObjectState.ACTIVE) is None


def test_idle_to_active_on_new_observation() -> None:
    assert state_management.next_state_on_new_observation(ObjectState.IDLE) is ObjectState.ACTIVE


def test_new_observation_no_op_when_already_active() -> None:
    assert state_management.next_state_on_new_observation(ObjectState.ACTIVE) is None


def test_active_to_idle_on_timeout() -> None:
    assert state_management.next_state_on_idle_timeout(ObjectState.ACTIVE) is ObjectState.IDLE


def test_idle_timeout_no_op_from_non_active() -> None:
    assert state_management.next_state_on_idle_timeout(ObjectState.IDLE) is None


def test_active_to_executing_on_execution_start() -> None:
    assert (
        state_management.next_state_on_execution_start(ObjectState.ACTIVE) is ObjectState.EXECUTING
    )


def test_executing_outcomes() -> None:
    assert (
        state_management.next_state_on_execution_result(ObjectState.EXECUTING, outcome="success")
        is ObjectState.COMPLETED
    )
    assert (
        state_management.next_state_on_execution_result(ObjectState.EXECUTING, outcome="error")
        is ObjectState.FAILED
    )
    assert (
        state_management.next_state_on_execution_result(ObjectState.EXECUTING, outcome="blocked")
        is ObjectState.WAITING
    )


def test_execution_result_no_op_from_non_executing() -> None:
    assert (
        state_management.next_state_on_execution_result(ObjectState.ACTIVE, outcome="success")
        is None
    )


def test_active_to_learning_on_exploration_start() -> None:
    assert (
        state_management.next_state_on_exploration_start(ObjectState.ACTIVE) is ObjectState.LEARNING
    )


def test_completed_and_failed_are_terminal() -> None:
    assert state_management.is_valid_transition(ObjectState.COMPLETED, ObjectState.ACTIVE) is False
    assert state_management.is_valid_transition(ObjectState.FAILED, ObjectState.ACTIVE) is False


def test_waiting_and_learning_have_no_outgoing_edge() -> None:
    """§6's diagram draws no edge out of Waiting or Learning -- documented gap,
    not an oversight (see state_management.py's module docstring)."""
    assert state_management.is_valid_transition(ObjectState.WAITING, ObjectState.EXECUTING) is False
    assert state_management.is_valid_transition(ObjectState.LEARNING, ObjectState.ACTIVE) is False
