"""Verify CrewAI agents use shared execution safety limits."""

from unittest.mock import MagicMock, patch

import pytest

from app.agents.execution import AGENT_EXECUTION_CONTROLS
from app.agents.financial_analyst_agent import build_financial_analyst_agent
from app.agents.financial_expert_agent import build_financial_expert_agent
from app.agents.risk_analyst_agent import build_risk_analyst_agent
from app.core.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        yfinance_enabled=True,
        tavily_api_key="tavily-key",
        openrouter_api_key="openrouter-key",
        llm_provider="openrouter",
        crew_verbose=False,
    )


@pytest.mark.parametrize(
    "builder",
    [
        build_financial_analyst_agent,
        build_risk_analyst_agent,
        build_financial_expert_agent,
    ],
)
def test_all_agents_apply_execution_controls(builder, settings: Settings) -> None:
    llm = MagicMock()
    with patch("crewai.Agent") as agent_cls:
        builder(llm, settings)
        kwargs = agent_cls.call_args.kwargs
        assert kwargs["max_iter"] == 2
        assert kwargs["max_execution_time"] == 75
        assert kwargs["respect_context_window"] is True
        assert kwargs["cache"] is True
        assert "max_rpm" not in kwargs


def test_execution_controls_match_shared_constant() -> None:
    assert AGENT_EXECUTION_CONTROLS == {
        "max_iter": 2,
        "max_execution_time": 75,
        "respect_context_window": True,
        "cache": True,
    }
