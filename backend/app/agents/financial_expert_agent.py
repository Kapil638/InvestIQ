"""Agent 4 – Financial Expert."""


def build_financial_expert_agent(llm, settings):
    from crewai import Agent

    from app.agents.execution import AGENT_EXECUTION_CONTROLS

    return Agent(
        role="Financial Expert",
        goal=(
            "Deliver a final investment recommendation for {ticker} with clear reasoning, "
            "confidence score, risks, target price range, horizon, and allocation guidance."
        ),
        backstory=(
            "You are a portfolio manager at a top-tier asset management firm. "
            "You translate analyst theses into actionable investment decisions. "
            "You always explain your reasoning and acknowledge uncertainty."
        ),
        llm=llm,
        verbose=settings.crew_verbose,
        allow_delegation=False,
        **AGENT_EXECUTION_CONTROLS,
    )
