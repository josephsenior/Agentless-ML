import pytest

from agentless_ml.attempt_budget import AttemptBudget, BudgetExceeded
from agentless_ml.budget_runner import BudgetRunner
from agentless_ml.validation import PublicTestCommand


def test_threshold_and_inflight_overshoot_stop_next_work():
    budget = AttemptBudget(tokens=20)
    budget.start()
    budget.charge(10, 5)
    with pytest.raises(BudgetExceeded, match='token_limit'):
        budget.charge(4, 3)
    assert budget.snapshot()['token_overshoot'] == 2
    with pytest.raises(BudgetExceeded):
        budget.check()


def test_baseline_time_is_excluded_but_validation_is_counted():
    now = [0.0]
    budget = AttemptBudget(seconds=10, clock=lambda: now[0])
    budget.start()
    with budget.exclude_baseline():
        now[0] = 100
    assert budget.remaining == 10
    now[0] = 110
    with pytest.raises(BudgetExceeded, match='time_limit'):
        budget.check()


def test_missing_usage_stops_future_requests():
    budget = AttemptBudget()
    with pytest.raises(BudgetExceeded, match='usage_unavailable'):
        budget.charge(None, 3)
    with pytest.raises(BudgetExceeded, match='usage_unavailable'):
        budget.check()


def test_runner_clamps_command_to_remaining_time():
    now = [0.0]
    budget = AttemptBudget(seconds=10, clock=lambda: now[0])
    class Runner:
        def run(self, source, command, **kwargs):
            assert command.timeout_seconds == 7
            now[0] = 10
    budget.start()
    now[0] = 3
    with pytest.raises(BudgetExceeded, match='time_limit'):
        BudgetRunner(Runner(), budget).run('fixture', PublicTestCommand(('test',), timeout_seconds=30))
