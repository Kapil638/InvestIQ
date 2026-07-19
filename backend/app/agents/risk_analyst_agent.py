"""Agent – Risk Analyst (structured risk assessment)."""


def build_risk_analyst_agent(llm, settings):
    from crewai import Agent

    from app.agents.execution import AGENT_EXECUTION_CONTROLS

    return Agent(
        role="Risk Analyst",
        goal=(
            "Assess investment risks for {ticker} using ONLY the supplied ResearchContext "
            "and Analysis output. Identify governance, financial, macro, business, "
            "regulatory, valuation, and earnings risks."
        ),
        backstory=(
            "You are a senior risk officer at an institutional asset manager. "
            "You never invent metrics or fetch external data. "
            "You quantify risks on a 0-100 scale (higher = riskier) and explain them clearly."
        ),
        llm=llm,
        verbose=settings.crew_verbose,
        allow_delegation=False,
        **AGENT_EXECUTION_CONTROLS,
    )
