"""Shared CrewAI agent execution limits for InvestIQ research agents."""

AGENT_EXECUTION_CONTROLS: dict[str, int | bool] = {
    "max_iter": 2,
    # 75s left too little margin against normal free-tier OpenRouter latency
    # variance (successful runs have taken 20-68s for a single agent) - a
    # timeout here re-raises and aborts the whole report, not just this
    # stage, so this needs real headroom rather than a tight safety net.
    "max_execution_time": 150,
    "respect_context_window": True,
    "cache": True,
}
