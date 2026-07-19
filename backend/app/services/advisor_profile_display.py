"""Profile display helpers for advisor responses."""

from __future__ import annotations

from app.schemas.advisor import InvestorProfile, ProfileFieldDisplay
from app.services.advisor_intent_service import AdvisorIntentType, ClassifiedIntent

_FIELD_LABELS: list[tuple[str, str]] = [
    ("capital", "Capital"),
    ("time_horizon", "Time horizon"),
    ("risk_appetite", "Risk appetite"),
    ("market_cap_preference", "Market cap preference"),
    ("dividend_growth_preference", "Dividend / growth preference"),
    ("investment_style", "Investment style"),
]


def build_profile_fields(classified: ClassifiedIntent) -> list[ProfileFieldDisplay]:
    if classified.intent == AdvisorIntentType.MARKET_RECOMMENDATION:
        return [
            ProfileFieldDisplay(
                label="Mode",
                value="Market recommendation",
                source="assumed",
            )
        ]

    if classified.intent == AdvisorIntentType.COMPANY_RESEARCH:
        sym = classified.company_symbol or "—"
        return [
            ProfileFieldDisplay(label="Mode", value="Company research", source="user"),
            ProfileFieldDisplay(label="Symbol", value=sym, source="user"),
        ]

    fields: list[ProfileFieldDisplay] = [
        ProfileFieldDisplay(
            label="Mode",
            value=_intent_label(classified.intent),
            source="assumed",
        )
    ]

    profile = classified.profile
    for key, label in _FIELD_LABELS:
        value = getattr(profile, key, None)
        if value:
            source = "user" if key in classified.user_provided_fields else "assumed"
            fields.append(ProfileFieldDisplay(label=label, value=value, source=source))
        else:
            fields.append(ProfileFieldDisplay(label=label, value=None, source="missing"))

    if profile.preferences:
        fields.append(
            ProfileFieldDisplay(
                label="Preferences",
                value=", ".join(profile.preferences),
                source="user" if "preferences" in classified.user_provided_fields else "assumed",
            )
        )
    if profile.themes:
        names = ", ".join(t.name for t in profile.themes)
        fields.append(
            ProfileFieldDisplay(
                label="Themes",
                value=names,
                source="user" if "themes" in classified.user_provided_fields else "assumed",
            )
        )

    return fields


def _intent_label(intent: AdvisorIntentType) -> str:
    labels = {
        AdvisorIntentType.MARKET_RECOMMENDATION: "Market recommendation",
        AdvisorIntentType.THEME_DISCOVERY: "Theme discovery",
        AdvisorIntentType.PERSONALIZED_PORTFOLIO: "Personalized portfolio",
        AdvisorIntentType.COMPANY_RESEARCH: "Company research",
        AdvisorIntentType.FOLLOW_UP: "Follow-up",
        AdvisorIntentType.UNKNOWN: "General research",
    }
    return labels.get(intent, "General research")
