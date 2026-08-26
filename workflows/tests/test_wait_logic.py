from agent_workflows.logic.wait import wait_seconds


def test_wait_seconds_zero() -> None:
    wait_seconds(0)
