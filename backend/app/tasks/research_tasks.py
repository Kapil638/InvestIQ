"""CrewAI task definitions for reasoning agents (Analysis, Risk, Recommendation)."""

from app.agents.financial_analyst_agent import build_financial_analyst_agent
from app.agents.financial_expert_agent import build_financial_expert_agent
from app.agents.risk_analyst_agent import build_risk_analyst_agent
from app.core.config import Settings

_STRUCTURED_JSON_FOOTER = """
You MUST output in this exact structure:

```json
{json_schema}
```

Then provide a concise narrative (2-4 paragraphs). Do not invent metrics outside the supplied context.
"""


def build_analysis_task(agent, settings: Settings):
    from crewai import Task

    schema = (
        '{"growth":0-100,"profitability":0-100,"valuation":0-100,'
        '"financial_health":0-100,"management":0-100,"sector_strength":0-100,'
        '"macro":0-100,"overall":0-100}'
    )
    return Task(
        description=(
            "Analyze {ticker} using ONLY the ResearchContext below.\n\n"
            "{research_context}\n\n"
            "{guardrail_feedback}\n\n"
            "If PRIOR_REPORTS or INSTITUTIONAL_MEMORY are present, explicitly note what changed "
            "vs prior thesis (rating, risks, valuation view) — do not copy old conclusions blindly. "
            "If PORTFOLIO_CONTEXT is present, factor existing ownership and concentration into "
            "the thesis framing (already owned vs new idea). "
            "Score growth, profitability, valuation, financial health, management, "
            "sector strength, and macro exposure (0-100 each). "
            "Use only supplied facts; state 'Not available' for missing data."
            + _STRUCTURED_JSON_FOOTER.format(json_schema=schema)
        ),
        expected_output=(
            "JSON score block plus investment thesis narrative for {ticker}."
        ),
        agent=agent,
    )


def build_risk_task(agent, settings: Settings):
    from crewai import Task

    schema = (
        '{"overall_risk":0-100,"financial":0-100,"governance":0-100,'
        '"macro":0-100,"business":0-100,"valuation":0-100,"regulatory":0-100,'
        '"risks":["risk1","risk2"]}'
    )
    return Task(
        description=(
            "Assess risks for {ticker} using ONLY the ResearchContext and Analysis below.\n\n"
            "RESEARCH CONTEXT:\n{research_context}\n\n"
            "ANALYSIS:\n{analysis}\n\n"
            "ANALYSIS SCORES:\n{analysis_scores}\n\n"
            "Do not regenerate financial analysis. Quantify risks (0-100, higher = riskier). "
            "If PRIOR_REPORTS lists earlier risks, highlight which are new, resolved, or worsening."
            + _STRUCTURED_JSON_FOOTER.format(json_schema=schema)
        ),
        expected_output="JSON risk scores plus risk narrative and bullet risks for {ticker}.",
        agent=agent,
    )


def build_recommendation_task(agent, settings: Settings):
    from crewai import Task

    return Task(
        description=(
            "Provide a final recommendation for {ticker} using ONLY:\n"
            "- ResearchContext\n- Analysis scores\n- Risk scores\n- Guardrails status\n\n"
            "RESEARCH CONTEXT:\n{research_context}\n\n"
            "ANALYSIS NARRATIVE:\n{analysis}\n\n"
            "ANALYSIS SCORES:\n{analysis_scores}\n\n"
            "RISK NARRATIVE:\n{risk_narrative}\n\n"
            "RISK SCORES:\n{risk_scores}\n\n"
            "GUARDRAILS:\n{guardrails_status}\n\n"
            "Do NOT invent or recalculate financial metrics. "
            "If PRIOR_REPORTS or INSTITUTIONAL_MEMORY are present, state whether the rating "
            "should upgrade, downgrade, or stay consistent vs the prior view and why. "
            "If PORTFOLIO_CONTEXT shows ALREADY OWNED, give add/hold/trim/exit guidance with "
            "allocation sizing that respects current weight; if NOT CURRENTLY HELD, suggest "
            "a starter allocation vs existing concentration. "
            "Output Rating (Buy/Hold/Avoid/Watchlist), reasoning, key risks, "
            "target price range if supported, horizon, allocation suggestion, expected upside. "
            "Do not output a confidence percentage – committee scoring is deterministic."
        ),
        expected_output=(
            "Final recommendation for {ticker} with rating, reasoning, risks, "
            "target price range, horizon, allocation, and expected upside."
        ),
        agent=agent,
    )


def build_reasoning_agent_pairs(settings: Settings, llm):
    """Build only reasoning agents used in the pipeline (no data-collection agents)."""
    analyst_agent = build_financial_analyst_agent(llm, settings)
    risk_agent = build_risk_analyst_agent(llm, settings)
    expert_agent = build_financial_expert_agent(llm, settings)

    return {
        "analysis": (analyst_agent, build_analysis_task(analyst_agent, settings)),
        "risk": (risk_agent, build_risk_task(risk_agent, settings)),
        "recommendation": (expert_agent, build_recommendation_task(expert_agent, settings)),
    }


# Backwards-compatible alias for tests importing the old name
def build_agent_task_pairs(settings: Settings, llm):
    return build_reasoning_agent_pairs(settings, llm)
