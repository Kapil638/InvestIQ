"""Shared CrewAI agent execution limits for InvestIQ research agents."""

AGENT_EXECUTION_CONTROLS: dict[str, int | bool] = {
    "max_iter": 2,
    "max_execution_time": 75,
    "respect_context_window": True,
    "cache": True,
}
