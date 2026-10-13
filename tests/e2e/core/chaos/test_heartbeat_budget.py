"""Heartbeat coverage follows the RPC response budget, not a fast-turn cutoff."""
from types import SimpleNamespace

import pytest

from tests.e2e.core.chaos.test_tui_gateway_turn_liveness import (
    HEARTBEAT_INTERVAL_S,
    HEARTBEAT_MAX_S,
    MIN_HEARTBEATS,
    Scenario,
    _assert_heartbeat,
)


def test_short_turn_with_responsive_rpcs_does_not_require_five_samples():
    # The CI failure answered four RPCs during a 2.1s turn; its first RPC
    # used 1.55s, well within the 3s responsiveness contract.
    heartbeat = SimpleNamespace(
        latencies=[HEARTBEAT_MAX_S / 2] + [0.02] * (MIN_HEARTBEATS - 2),
        failures=[], interval=HEARTBEAT_INTERVAL_S,
    )
    _assert_heartbeat(Scenario("short_drop", "drop"), heartbeat, {}, HEARTBEAT_MAX_S * 0.7)


@pytest.mark.parametrize("latencies,failures,message", [
    ([HEARTBEAT_MAX_S], [], "dispatcher blocked"),
    ([0.01], [], "only"),
    ([], ["RPC timed out"], "heartbeat RPC failed"),
])
def test_heartbeat_budget_still_rejects_blocking_failures_and_missing_coverage(latencies, failures, message):
    heartbeat = SimpleNamespace(latencies=latencies, failures=failures, interval=HEARTBEAT_INTERVAL_S)
    turn_s = 2 * MIN_HEARTBEATS * (HEARTBEAT_MAX_S + HEARTBEAT_INTERVAL_S)
    with pytest.raises(AssertionError, match=message):
        _assert_heartbeat(Scenario("wedged", "hang"), heartbeat, {}, turn_s)
