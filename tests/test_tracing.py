"""Traces number every model call in the shared budget and show where a run's requests went."""

import asyncio

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.capabilities import Instrumentation
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.instrumented import InstrumentationSettings
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import UsageLimits

from vis_agent import trace_report
from vis_agent.analyst.agent import create_analyst
from vis_agent.designer.agent import create_designer
from vis_agent.lead import create_lead
from vis_agent.profiler.agent import create_profiler
from vis_agent.reviewer.agent import create_reviewer
from vis_agent.tracing import CallLedger, JsonLinesExporter


@pytest.mark.parametrize("factory", [create_lead, create_designer, create_reviewer, create_analyst, create_profiler])
def test_every_team_agent_numbers_its_model_calls(factory):
    agent = factory(TestModel())
    assert any(isinstance(c, CallLedger) for c in agent.root_capability.capabilities)


def run_team(tmp_path, request_limit):
    """A lead whose tool runs a designer on the shared usage, as design_visualization does. The designer's first
    model call fails, the lead's first tool call is retried, and the lead never stops calling the tool."""
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(JsonLinesExporter(tmp_path)))
    traced = [Instrumentation(InstrumentationSettings(tracer_provider=provider)), CallLedger()]
    designer_calls = []

    def designer_model(messages, info):
        designer_calls.append(1)
        if len(designer_calls) == 1:
            raise ModelHTTPError(429, "test-model", body="rate limited")
        return ModelResponse(parts=[TextPart("spec")])

    designer = Agent(FunctionModel(designer_model), name="designer", capabilities=traced)
    lead = Agent(FunctionModel(lambda messages, info: ModelResponse(parts=[ToolCallPart(
        "design_visualization", {"request_id": "rq_" + "a" * 32})])), name="vis-lead", capabilities=traced)
    tool_calls = []

    @lead.tool
    async def design_visualization(ctx: RunContext, request_id: str) -> str:
        tool_calls.append(1)
        if len(tool_calls) == 1:
            raise ModelRetry("Required columns are not in the result table.")
        try:
            return (await designer.run("design", usage=ctx.usage, usage_limits=ctx.usage_limits)).output
        except ModelHTTPError as exc:
            return f"The designer could not finish: {exc}"

    with pytest.raises(UsageLimitExceeded):
        asyncio.run(lead.run("chart it", conversation_id="conv-1",
                             usage_limits=UsageLimits(request_limit=request_limit)))
    return trace_report.load_spans(tmp_path)


def test_report_accounts_for_a_run_that_reaches_the_request_limit(tmp_path):
    runs = trace_report.find_runs(run_team(tmp_path, request_limit=5), request_id="rq_" + "a" * 32)
    assert len(runs) == 1
    spans = next(iter(runs.values()))
    summary = trace_report.summarize(spans)

    assert summary["request_limit_reached"] and summary["status"] == "error"
    assert summary["conversation_id"] == "conv-1"
    assert summary["request_limit"] == 5
    # The shared counter runs across the lead and its nested designer; the failed 429 is not counted.
    assert [c["call_number"] for c in summary["calls"]] == [1, 2, 3, 3, 4, 5]
    assert [(c["agent"], c["counted"]) for c in summary["calls"]] == [
        ("vis-lead", True), ("vis-lead", True), ("designer", False), ("vis-lead", True),
        ("designer", True), ("vis-lead", True)]
    assert summary["counted_calls"] == 5
    assert summary["counted_by_agent"] == {"vis-lead": 4, "designer": 1}
    assert summary["counted_by_lead_tool"] == {"vis-lead (own turns)": 4, "design_visualization": 1}
    assert [c["agent"] for c in summary["failed_calls"]] == ["designer"]
    assert "429" in summary["failed_calls"][0]["errors"][0]
    # The fourth tool call's designer is refused by the shared limit before it reaches its model.
    assert summary["tool_calls"] == {"vis-lead:design_visualization": 4}
    assert [r["error"].split(":")[0] for r in summary["tool_retries"]] == [
        "pydantic_ai.exceptions.ToolRetryError", "pydantic_ai.exceptions.UsageLimitExceeded"]

    text = trace_report.report(spans)
    assert "LIMIT REACHED" in text and "[call 3/5 (not counted)]" in text
    assert "request_limit of 5" in text


def test_exporter_cuts_long_values(tmp_path):
    exporter = JsonLinesExporter(tmp_path, max_characters=10)
    assert exporter.cut("x" * 25) == "x" * 10 + "… [15 more characters]"
    assert exporter.cut("short") == "short"
