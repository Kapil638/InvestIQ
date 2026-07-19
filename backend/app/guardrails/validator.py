"""
Guardrails – validate pipeline output before Agent 4 executes.

See guardrails/engine.py for the full Phase 4 implementation.
"""

from app.guardrails.engine import GuardrailEngine, validate_before_recommendation

__all__ = ["GuardrailEngine", "validate_before_recommendation"]
