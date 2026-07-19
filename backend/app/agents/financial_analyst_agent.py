"""Agent 3 – Financial Analyst."""


def build_financial_analyst_agent(llm, settings):
    from crewai import Agent

    from app.agents.execution import AGENT_EXECUTION_CONTROLS

    return Agent(
        role="Financial Analyst",
        goal=(
            "Produce a detailed investment thesis for {ticker} by analyzing "
            "structured financial data and qualitative news research."
        ),
        backstory=(
            "You are a senior equity research analyst with deep expertise in "
            "fundamental analysis, valuation, and risk assessment. "
            "You synthesize quantitative data with qualitative context to build "
            "a rigorous, evidence-based investment thesis."
        ),
        llm=llm,
        verbose=settings.crew_verbose,
        allow_delegation=False,
        **AGENT_EXECUTION_CONTROLS,
    )
