"""Shared mock agent outputs for pipeline tests."""

ANALYSIS_CREW_OUTPUT = """
```json
{
  "growth": 82,
  "profitability": 75,
  "valuation": 68,
  "financial_health": 79,
  "management": 81,
  "sector_strength": 73,
  "macro": 69,
  "overall": 76
}
```

AAPL shows strong revenue growth and improving margins across segments,
supported by services expansion and disciplined capital allocation.
Valuation remains reasonable while debt is manageable and cash flow is healthy.
Key risks include competition and regulatory pressure.
"""

RISK_CREW_OUTPUT = """
```json
{
  "overall_risk": 61,
  "financial": 58,
  "governance": 18,
  "macro": 37,
  "business": 42,
  "valuation": 77,
  "regulatory": 20,
  "risks": ["Competition", "Regulatory pressure"]
}
```

Competition and regulatory headwinds remain the primary risks for AAPL.
"""

RECOMMENDATION_CREW_OUTPUT = (
    "Rating: Buy\nConfidence Score: 80\nReasoning: Strong fundamentals\n"
    "Key Risks:\n- Competition\nTarget Price Range: $200-$220"
)

SHORT_ANALYSIS_OUTPUT = "short"

COLLECT_RETURN = lambda fin, news: (fin, news, False, False)
