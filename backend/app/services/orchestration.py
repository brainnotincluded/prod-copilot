"""Orchestration service — manages scenario execution with explicit
state machine, correlation IDs, step timing, and structured logging.

Extracts all business logic from the route handlers so controllers
stay thin.
"""

from __future__ import annotations

import enum
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiEndpoint, SwaggerSource
from app.schemas.models import OrchestrationStep, ResultResponse
from app.services.mlops_client import MLOpsClient
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step state machine
# ---------------------------------------------------------------------------

class StepState(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    SKIPPED = "skipped"

    # Allowed transitions: from_state -> {to_states}
    _TRANSITIONS: dict[str, set[str]] = {  # type: ignore[assignment]
        "pending": {"running", "skipped"},
        "running": {"completed", "error"},
    }

    @classmethod
    def validate_transition(cls, from_state: StepState, to_state: StepState) -> None:
        allowed = cls._TRANSITIONS.get(from_state.value, set())
        if to_state.value not in allowed:
            raise ValueError(
                f"Invalid state transition: {from_state.value} -> {to_state.value}"
            )


# ---------------------------------------------------------------------------
# Per-step context
# ---------------------------------------------------------------------------

@dataclass
class StepContext:
    step_number: int
    action: str
    description: str
    state: StepState = StepState.PENDING
    started_at: float | None = None
    finished_at: float | None = None
    duration_ms: float | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    def transition(self, new_state: StepState) -> None:
        StepState.validate_transition(self.state, new_state)
        self.state = new_state
        now = time.monotonic()
        if new_state == StepState.RUNNING:
            self.started_at = now
        elif new_state in (StepState.COMPLETED, StepState.ERROR):
            self.finished_at = now
            if self.started_at is not None:
                self.duration_ms = round((now - self.started_at) * 1000, 2)

    def to_schema(self, correlation_id: str) -> OrchestrationStep:
        return OrchestrationStep(
            step=self.step_number,
            action=self.action,
            description=self.description,
            status=self.state.value,
            result=self.result,
            correlation_id=correlation_id,
            duration_ms=self.duration_ms,
        )


# ---------------------------------------------------------------------------
# Per-request orchestration context
# ---------------------------------------------------------------------------

@dataclass
class OrchestrationContext:
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query: str = ""
    swagger_source_ids: list[int] | None = None
    steps: list[StepContext] = field(default_factory=list)
    started_at: float = field(default_factory=time.monotonic)


# ---------------------------------------------------------------------------
# Orchestration service
# ---------------------------------------------------------------------------

class OrchestrationService:
    """Manages the full orchestration scenario:
    1. Fetch available endpoints from DB (with RAG pre-filtering if too many)
    2. Forward to MLOps orchestrator
    3. Track each step with timing and state transitions
    """

    # When total endpoints exceed this threshold, use RAG to pre-filter
    RAG_THRESHOLD = 50
    RAG_TOP_K = 30

    def __init__(
        self,
        db: AsyncSession,
        mlops_client: MLOpsClient | None = None,
    ) -> None:
        self._db = db
        self._mlops = mlops_client or MLOpsClient()

    # ------------------------------------------------------------------
    # Synchronous execution (POST /api/query)
    # ------------------------------------------------------------------

    async def execute(
        self,
        query: str,
        swagger_source_ids: list[int] | None = None,
    ) -> ResultResponse:
        ctx = OrchestrationContext(
            query=query,
            swagger_source_ids=swagger_source_ids,
        )
        self._log(ctx, "orchestration.start", query=query)

        # Step 1: fetch endpoints
        endpoints_payload, base_url = await self._run_step(
            ctx,
            step_num=1,
            action="fetch_endpoints",
            description="Loading available API endpoints",
            coro_fn=lambda: self._fetch_endpoints(ctx),
        )

        if not endpoints_payload:
            self._log(ctx, "orchestration.no_endpoints")
            return ResultResponse(
                type="text",
                data={"content": "No relevant API endpoints found for your query. Please upload a Swagger spec with the right API."},
                metadata={"status": "completed", "correlation_id": ctx.correlation_id},
            )

        # Step 2: call orchestrator
        try:
            raw_result = await self._run_step(
                ctx,
                step_num=2,
                action="orchestrate",
                description=f"Orchestrating query across {len(endpoints_payload)} endpoints",
                coro_fn=lambda: self._mlops.orchestrate(
                    query=query,
                    endpoints=endpoints_payload,
                    base_url=base_url,
                ),
            )
        except Exception as exc:
            self._log(ctx, "orchestration.error", error=str(exc))
            return ResultResponse(
                type="text",
                data={"content": f"Orchestration error: {exc}"},
                metadata={"status": "error", "correlation_id": ctx.correlation_id},
            )

        result_data = raw_result.get("data", {})
        result_type = raw_result.get("type", "text")

        if not result_data or result_data == {}:
            result_type = "text"
            result_data = {"content": "The query completed but returned no data."}

        total_ms = round((time.monotonic() - ctx.started_at) * 1000, 2)
        self._log(ctx, "orchestration.complete", total_ms=total_ms)

        return ResultResponse(
            type=result_type,
            data=result_data,
            metadata={
                **(raw_result.get("metadata") or {}),
                "correlation_id": ctx.correlation_id,
                "total_ms": total_ms,
            },
        )

    # ------------------------------------------------------------------
    # Streaming execution (WebSocket /api/ws/query)
    # ------------------------------------------------------------------

    async def execute_stream(
        self,
        query: str,
        swagger_source_ids: list[int] | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        ctx = OrchestrationContext(
            query=query,
            swagger_source_ids=swagger_source_ids,
        )
        self._log(ctx, "orchestration.stream.start", query=query)

        # Step 1: fetch endpoints
        endpoints_payload, base_url = await self._run_step(
            ctx,
            step_num=1,
            action="search",
            description="Loading available API endpoints",
            coro_fn=lambda: self._fetch_endpoints(ctx),
        )

        # Emit search step
        step1 = ctx.steps[-1]
        if endpoints_payload:
            names = [f"{ep['method']} {ep['path']}" for ep in endpoints_payload[:3]]
            names_str = ", ".join(names)
            if len(endpoints_payload) > 3:
                names_str += f" and {len(endpoints_payload) - 3} more"
            step1.description = f"{len(endpoints_payload)} endpoints available: {names_str}"
        else:
            step1.description = "No endpoints available."

        yield {"type": "step", "data": step1.to_schema(ctx.correlation_id).model_dump()}

        # Short-circuit: no endpoints
        if not endpoints_payload:
            result = ResultResponse(
                type="text",
                data={"content": "No API endpoints available. Please upload a Swagger spec with a base URL configured."},
                metadata={"status": "completed", "correlation_id": ctx.correlation_id},
            )
            yield {"type": "result", "data": result.model_dump()}
            return

        # Step 2+: stream from MLOps
        step_counter = 2
        step_action_map: dict[int, str] = {}
        step_description_map: dict[int, str] = {}

        try:
            async for chunk in self._mlops.orchestrate_stream(
                query=query,
                endpoints=endpoints_payload,
                base_url=base_url,
                history=history,
            ):
                event_type = chunk.pop("event_type", "")

                if event_type in ("step_start", "step_complete", "step_error"):
                    step_num = chunk.get("step", step_counter)

                    if event_type == "step_start":
                        status = "running"
                        action_name = chunk.get("action", "processing")
                        description = chunk.get("description", "")
                        step_action_map[step_num] = action_name
                        step_description_map[step_num] = description
                    elif event_type == "step_complete":
                        status = "completed"
                        action_name = chunk.get("action") or step_action_map.get(step_num, "processing")
                        description = chunk.get("description") or step_description_map.get(step_num, "")
                    else:
                        status = "error"
                        action_name = chunk.get("action") or step_action_map.get(step_num, "processing")
                        description = chunk.get("description") or step_description_map.get(step_num, "")

                    step_schema = OrchestrationStep(
                        step=step_counter,
                        action=action_name,
                        description=description,
                        status=status,
                        result=chunk.get("result"),
                        correlation_id=ctx.correlation_id,
                    )
                    yield {"type": "step", "data": step_schema.model_dump()}

                    if event_type in ("step_complete", "step_error"):
                        step_counter += 1

                elif event_type == "result":
                    result_data = chunk.get("data", {})
                    result_type = chunk.get("type", "text")

                    if not result_data or result_data == {}:
                        result_type = "text"
                        result_data = {"content": "The query completed but returned no data."}

                    result = ResultResponse(
                        type=result_type,
                        data=result_data,
                        metadata={
                            **(chunk.get("metadata") or {}),
                            "correlation_id": ctx.correlation_id,
                        },
                    )
                    yield {"type": "result", "data": result.model_dump()}

        except Exception as exc:
            self._log(ctx, "orchestration.stream.error", error=str(exc))
            yield {"type": "error", "data": {"message": f"Orchestration stream failed: {exc}"}}

    # ------------------------------------------------------------------
    # Internal: fetch endpoints (shared by sync + stream)
    # ------------------------------------------------------------------

    async def _fetch_endpoints(
        self,
        ctx: OrchestrationContext,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Query DB for all relevant endpoints and their base URLs.

        If the total number of endpoints exceeds RAG_THRESHOLD, uses
        semantic search to pre-filter to RAG_TOP_K most relevant ones.
        This prevents overloading the LLM context window with 500+ endpoints.

        Returns (endpoints_payload, first_base_url).
        """
        stmt = sa_select(ApiEndpoint).join(
            SwaggerSource, ApiEndpoint.swagger_source_id == SwaggerSource.id
        ).where(SwaggerSource.base_url.isnot(None))

        if ctx.swagger_source_ids:
            stmt = stmt.where(ApiEndpoint.swagger_source_id.in_(ctx.swagger_source_ids))

        result = await self._db.execute(stmt.order_by(ApiEndpoint.id))
        all_endpoints = list(result.scalars().all())

        # RAG pre-filtering: if too many endpoints, narrow down with semantic search
        if len(all_endpoints) > self.RAG_THRESHOLD and ctx.query:
            self._log(
                ctx, "rag.prefilter",
                total=len(all_endpoints), threshold=self.RAG_THRESHOLD,
            )
            rag = RAGService(self._db, mlops_client=self._mlops)
            rag_results = await rag.search(
                query=ctx.query,
                limit=self.RAG_TOP_K,
                swagger_source_ids=ctx.swagger_source_ids,
            )
            if rag_results:
                rag_ids = {ep.id for ep in rag_results}
                endpoints = [ep for ep in all_endpoints if ep.id in rag_ids]
                self._log(ctx, "rag.prefilter.done", filtered=len(endpoints))
            else:
                # RAG failed (e.g. no embeddings) — fallback to all
                endpoints = all_endpoints
        else:
            endpoints = all_endpoints

        # Build source cache
        source_cache: dict[int, SwaggerSource | None] = {}
        base_url: str | None = None
        for ep in endpoints:
            sid = ep.swagger_source_id
            if sid not in source_cache:
                source_cache[sid] = await self._db.get(SwaggerSource, sid)
            src = source_cache[sid]
            if src and src.base_url and not base_url:
                base_url = src.base_url

        payload = [
            {
                "id": ep.id,
                "method": ep.method,
                "path": ep.path,
                "summary": ep.summary,
                "description": ep.description,
                "parameters": ep.parameters,
                "request_body": ep.request_body,
                "response_schema": ep.response_schema,
                "base_url": (source_cache.get(ep.swagger_source_id) or SwaggerSource()).base_url,
            }
            for ep in endpoints
        ]

        return payload, base_url

    # ------------------------------------------------------------------
    # Internal: generic step runner
    # ------------------------------------------------------------------

    async def _run_step(
        self,
        ctx: OrchestrationContext,
        step_num: int,
        action: str,
        description: str,
        coro_fn,
    ):
        step = StepContext(step_number=step_num, action=action, description=description)
        ctx.steps.append(step)

        step.transition(StepState.RUNNING)
        self._log(ctx, "step.start", step=step_num, action=action)

        try:
            result = await coro_fn()
            step.transition(StepState.COMPLETED)
            step.result = {"status": "ok"}
            self._log(
                ctx, "step.complete",
                step=step_num, action=action, duration_ms=step.duration_ms,
            )
            return result
        except Exception as exc:
            step.transition(StepState.ERROR)
            step.error = str(exc)
            self._log(
                ctx, "step.error",
                step=step_num, action=action, error=str(exc),
                duration_ms=step.duration_ms,
            )
            raise

    # ------------------------------------------------------------------
    # Structured logging
    # ------------------------------------------------------------------

    @staticmethod
    def _log(ctx: OrchestrationContext, event: str, **kwargs: Any) -> None:
        logger.info(
            "[%s] %s %s",
            ctx.correlation_id[:8],
            event,
            " ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else "",
            extra={
                "correlation_id": ctx.correlation_id,
                "event": event,
                **kwargs,
            },
        )
