"""Pipeline stage tracing for research report generation."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Literal

from app.schemas.research import PipelineStageTrace

PipelineStage = Literal[
    "financial",
    "news",
    "analysis",
    "risk",
    "guardrails",
    "recommendation",
    "committee",
    "save_report",
]

_STAGE_STATUS = Literal["running", "completed", "failed", "skipped"]


class PipelineTracer:
    """Records start/end timestamps and durations for each pipeline stage."""

    def __init__(self) -> None:
        self._entries: list[PipelineStageTrace] = []
        self._starts: dict[PipelineStage, tuple[datetime, float]] = {}

    def start(self, stage: PipelineStage) -> None:
        now = datetime.now(UTC)
        self._starts[stage] = (now, perf_counter())
        self._entries.append(
            PipelineStageTrace(stage=stage, status="running", started_at=now)
        )

    def complete(
        self,
        stage: PipelineStage,
        *,
        cache_hit: bool = False,
        tokens: int | None = None,
        detail: str | None = None,
    ) -> None:
        self._finish(stage, "completed", cache_hit=cache_hit, tokens=tokens, detail=detail)

    def fail(self, stage: PipelineStage, *, error: str | None = None) -> None:
        self._finish(stage, "failed", error=error)

    def skip(self, stage: PipelineStage, *, reason: str | None = None) -> None:
        now = datetime.now(UTC)
        self._entries.append(
            PipelineStageTrace(
                stage=stage,
                status="skipped",
                started_at=now,
                completed_at=now,
                duration_ms=0,
                detail=reason,
            )
        )

    def _finish(
        self,
        stage: PipelineStage,
        status: _STAGE_STATUS,
        *,
        cache_hit: bool = False,
        tokens: int | None = None,
        error: str | None = None,
        detail: str | None = None,
    ) -> None:
        started_at, perf_start = self._starts.pop(stage, (None, None))
        completed_at = datetime.now(UTC)
        duration_ms: int | None = None
        if perf_start is not None:
            duration_ms = int((perf_counter() - perf_start) * 1000)

        for i in range(len(self._entries) - 1, -1, -1):
            entry = self._entries[i]
            if entry.stage == stage and entry.status == "running":
                self._entries[i] = entry.model_copy(
                    update={
                        "status": status,
                        "started_at": started_at or entry.started_at,
                        "completed_at": completed_at,
                        "duration_ms": duration_ms,
                        "cache_hit": cache_hit,
                        "tokens": tokens,
                        "error": error,
                        "detail": detail,
                    }
                )
                return

        self._entries.append(
            PipelineStageTrace(
                stage=stage,
                status=status,
                started_at=started_at or completed_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
            )
        )

    def to_list(self) -> list[PipelineStageTrace]:
        return list(self._entries)
