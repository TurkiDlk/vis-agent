"""Request tracing: Logfire spans for every agent run, tool call, and model call, also kept locally as JSON lines.

Pydantic AI's instrumentation already nests spans as a tree: the lead's run, each tool it calls, a specialist's run
inside that tool, and every model call. This module adds what that tree cannot show by itself: the position of each
model call in the budget that the lead and its specialists share (`vis.call_number`, the counter `request_limit`
checks), whether the call counted, the SDK's HTTP attempts and retries, and a file the `vis trace` report can read
without a Logfire account.
"""

import json
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import logfire
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.capabilities.abstract import CapabilityOrdering

MAX_ATTRIBUTE_CHARACTERS = 4000
# The OpenAI SDK logs each automatic retry at INFO; httpx2 logs every HTTP attempt with its status code.
# Neither logs headers at INFO, so the API key stays out. Pydantic AI does not count these attempts as requests.
HTTP_LOGGERS = ("openai", "httpx2")


@dataclass
class CallLedger(AbstractCapability[Any]):
    """Mark each model call with its place in the shared request budget. Runs innermost, inside the `chat` span."""

    def get_ordering(self) -> CapabilityOrdering:
        return CapabilityOrdering(position="innermost")

    async def wrap_model_request(self, ctx, *, request_context, handler):
        span = trace.get_current_span()
        limit = ctx.usage_limits.request_limit if ctx.usage_limits is not None else None
        # Pydantic AI counts a request only after the model answers, so this is the number it will receive.
        span.set_attributes({"vis.call_number": ctx.usage.requests + 1,
                             **({"vis.request_limit": limit} if limit is not None else {})})
        try:
            response = await handler(request_context)
        except BaseException:
            span.set_attribute("vis.counted", False)
            raise
        span.set_attribute("vis.counted", True)
        return response


class JsonLinesExporter(SpanExporter):
    """Append finished spans to one file per day. Long attribute values are cut; Logfire scrubbing runs first."""

    def __init__(self, directory: Path, max_characters: int = MAX_ATTRIBUTE_CHARACTERS):
        self.directory = directory
        self.max_characters = max_characters

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"spans-{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"
        with path.open("a", encoding="utf-8") as file:
            for span in spans:
                file.write(json.dumps(self.record(span), ensure_ascii=False, default=str) + "\n")
        return SpanExportResult.SUCCESS

    def cut(self, value):
        if isinstance(value, str) and len(value) > self.max_characters:
            return value[:self.max_characters] + f"… [{len(value) - self.max_characters} more characters]"
        return value

    def record(self, span: ReadableSpan) -> dict:
        errors = [event.attributes.get("exception.type", "") + ": " + event.attributes.get("exception.message", "")
                  for event in span.events if event.name == "exception"]
        return {
            "trace_id": f"{span.context.trace_id:032x}", "span_id": f"{span.context.span_id:016x}",
            "parent_id": f"{span.parent.span_id:016x}" if span.parent else None, "name": span.name,
            "start": span.start_time / 1e9, "end": span.end_time / 1e9 if span.end_time else None,
            "error": span.status.status_code.name == "ERROR" or bool(errors),
            "errors": errors or ([span.status.description] if span.status.description else []),
            "attributes": {key: self.cut(value) for key, value in (span.attributes or {}).items()
                           if key not in ("logfire.json_schema", "logfire.metrics", "model_request_parameters",
                                          "gen_ai.tool.definitions")},
        }


def configure_tracing(data_directory: Path, service_name: str = "vis-agent") -> None:
    """Send traces to Logfire when LOGFIRE_TOKEN is set, and always to VIS_TRACE_DIR unless it is "off".

    VIS_TRACE_CONTENT=0 records structure, timing, tokens, and errors without prompts, tool arguments, or results.
    Image bytes are never recorded."""
    directory = os.getenv("VIS_TRACE_DIR") or str(data_directory / "traces")
    processors = [] if directory.lower() == "off" else [SimpleSpanProcessor(JsonLinesExporter(Path(directory)))]
    logfire.configure(send_to_logfire="if-token-present", service_name=service_name, console=False,
                      additional_span_processors=processors)
    logfire.instrument_pydantic_ai(include_content=os.getenv("VIS_TRACE_CONTENT", "1") != "0",
                                   include_binary_content=False)
    # LOG_LEVEL still decides; at the default INFO each HTTP attempt and SDK retry joins the `chat` span it belongs to.
    handler = logfire.LogfireLoggingHandler(level=logging.INFO)
    for name in HTTP_LOGGERS:
        logger = logging.getLogger(name)
        if not any(isinstance(h, logfire.LogfireLoggingHandler) for h in logger.handlers):
            logger.addHandler(handler)
