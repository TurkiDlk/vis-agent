"""Read the local trace files: one lead run's timeline, and where its model requests went."""

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REQUEST_ID = re.compile(r"rq_[0-9a-f]{32}")
HTTP_SUCCESS = re.compile(r'"HTTP/[\d.]+ 2\d\d ')
TOOL_CALL_NAME = re.compile(r'"type":\s*"tool_call".*?"name":\s*"([^"]+)"')
PREVIEW_CHARACTERS = 160


def load_spans(directory: Path) -> list[dict]:
    spans = []
    for path in sorted(directory.glob("spans-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                spans.append(json.loads(line))
    return spans


def lead_runs(spans: list[dict]) -> dict[str, list[dict]]:
    """Group spans by trace, keeping traces whose root is an agent run, oldest first."""
    traces: dict[str, list[dict]] = {}
    for span in spans:
        traces.setdefault(span["trace_id"], []).append(span)
    runs = {trace_id: sorted(group, key=lambda s: s["start"]) for trace_id, group in traces.items()
            if any(s["parent_id"] is None and s["name"].startswith("invoke_agent") for s in group)}
    return dict(sorted(runs.items(), key=lambda item: item[1][0]["start"]))


def find_runs(spans: list[dict], *, trace_id: str | None = None, request_id: str | None = None,
              conversation_id: str | None = None) -> dict[str, list[dict]]:
    runs = lead_runs(spans)
    if trace_id:
        return {key: group for key, group in runs.items() if key.startswith(trace_id)}
    if request_id:
        return {key: group for key, group in runs.items() if request_id in request_ids(group)}
    if conversation_id:
        return {key: group for key, group in runs.items()
                if any(s["attributes"].get("gen_ai.conversation.id") == conversation_id for s in group)}
    return runs


def request_ids(spans: list[dict]) -> list[str]:
    found: dict[str, None] = {}
    for span in spans:
        attributes = span["attributes"]
        for key in ("gen_ai.tool.call.arguments", "gen_ai.tool.call.result"):
            for match in REQUEST_ID.findall(str(attributes.get(key, ""))):
                found.setdefault(match)
    return list(found)


def _preview(value, limit: int = PREVIEW_CHARACTERS) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _lead_tool(span: dict, by_id: dict[str, dict], lead: str) -> str | None:
    """The lead's tool call that a nested span ran under, if any."""
    parent = by_id.get(span["parent_id"])
    while parent is not None:
        if parent["name"].startswith("execute_tool") and parent["attributes"].get("gen_ai.agent.name") == lead:
            return parent["attributes"].get("gen_ai.tool.name") or parent["name"].removeprefix("execute_tool ")
        parent = by_id.get(parent["parent_id"])
    return None


def summarize(spans: list[dict]) -> dict:
    """Per-run accounting from recorded spans only; nothing is inferred beyond what the spans say."""
    by_id = {s["span_id"]: s for s in spans}
    root = next(s for s in spans if s["parent_id"] is None and s["name"].startswith("invoke_agent"))
    lead = root["attributes"].get("gen_ai.agent.name") or root["name"].removeprefix("invoke_agent ")
    calls = []
    for span in spans:
        attributes = span["attributes"]
        if attributes.get("gen_ai.operation.name") != "chat":
            continue
        calls.append({
            "call_number": attributes.get("vis.call_number"), "request_limit": attributes.get("vis.request_limit"),
            "counted": attributes.get("vis.counted", not span["error"]), "agent": attributes.get("gen_ai.agent.name"),
            "model": attributes.get("gen_ai.response.model") or attributes.get("gen_ai.request.model"),
            "via": _lead_tool(span, by_id, lead), "seconds": round(span["end"] - span["start"], 3),
            "input_tokens": attributes.get("gen_ai.usage.input_tokens"),
            "output_tokens": attributes.get("gen_ai.usage.output_tokens"),
            "requested_tools": TOOL_CALL_NAME.findall(str(attributes.get("gen_ai.output.messages", ""))),
            "errors": span["errors"], "span_id": span["span_id"],
        })
    tools = [s for s in spans if s["attributes"].get("gen_ai.operation.name") == "execute_tool"]
    logs = [s for s in spans if s["attributes"].get("logfire.span_type") == "log"]
    http = [str(s["attributes"].get("logfire.msg", "")) for s in logs
            if str(s["attributes"].get("logfire.msg", "")).startswith("HTTP Request:")]
    counted = [c for c in calls if c["counted"]]
    errors = [error for s in spans for error in s["errors"]]
    return {
        "trace_id": root["trace_id"], "lead": lead,
        "conversation_id": root["attributes"].get("gen_ai.conversation.id"),
        "started": datetime.fromtimestamp(root["start"], timezone.utc).isoformat(timespec="seconds"),
        "seconds": round((root["end"] or root["start"]) - root["start"], 3),
        "status": "error" if root["error"] else "ok", "errors": root["errors"],
        "request_limit_reached": any("request_limit" in e for e in errors),
        "tool_calls_limit_reached": any("tool_calls_limit" in e for e in errors),
        "request_ids": request_ids(spans),
        "model_calls": len(calls), "counted_calls": len(counted),
        "request_limit": next((c["request_limit"] for c in calls if c["agent"] == lead and c["request_limit"]), None),
        "counted_by_agent": dict(Counter(c["agent"] for c in counted)),
        "counted_by_lead_tool": dict(Counter(c["via"] or f"{lead} (own turns)" for c in counted)),
        "failed_calls": [c for c in calls if not c["counted"] or c["errors"]],
        "tool_calls": dict(Counter(f'{s["attributes"].get("gen_ai.agent.name")}:{s["attributes"].get("gen_ai.tool.name")}'
                                   for s in tools)),
        "tool_retries": [{"agent": s["attributes"].get("gen_ai.agent.name"), "tool": s["attributes"].get("gen_ai.tool.name"),
                          "error": _preview("; ".join(s["errors"]))} for s in tools if s["errors"]],
        "http_attempts": len(http), "http_failures": [m for m in http if not HTTP_SUCCESS.search(m)],
        "sdk_retries": sum(1 for s in logs if str(s["attributes"].get("logfire.msg", "")).startswith("Retrying request")),
        "final_result": root["attributes"].get("final_result"),
        "calls": calls,
    }


def _describe(span: dict) -> str:
    attributes = span["attributes"]
    operation = attributes.get("gen_ai.operation.name")
    status = "✗ " + _preview("; ".join(span["errors"]), 200) if span["error"] else "ok"
    if operation == "chat":
        number, limit = attributes.get("vis.call_number"), attributes.get("vis.request_limit")
        counted = "" if attributes.get("vis.counted", True) else " (not counted)"
        tokens = f'in {attributes.get("gen_ai.usage.input_tokens", "?")} out {attributes.get("gen_ai.usage.output_tokens", "?")}'
        wanted = TOOL_CALL_NAME.findall(str(attributes.get("gen_ai.output.messages", "")))
        then = f" → calls {', '.join(wanted)}" if wanted else ""
        return f'[call {number}/{limit}{counted}] {span["name"]} ({attributes.get("gen_ai.agent.name")}) {tokens}{then} {status}'
    if operation == "execute_tool":
        arguments = attributes.get("gen_ai.tool.call.arguments")
        result = attributes.get("gen_ai.tool.call.result")
        detail = (f" args {_preview(arguments, 120)}" if arguments else "") + (f" → {_preview(result)}" if result else "")
        return f'{span["name"]}{detail} {status}'
    if attributes.get("logfire.span_type") == "log":
        return f'log: {_preview(attributes.get("logfire.msg", span["name"]), 200)}'
    if operation == "invoke_agent":
        final = attributes.get("final_result")
        return f'{span["name"]} {status}' + (f" → {_preview(final)}" if final else "")
    return f'{span["name"]} {status}'


def timeline(spans: list[dict]) -> list[str]:
    children: dict[str | None, list[dict]] = {}
    for span in spans:
        children.setdefault(span["parent_id"], []).append(span)
    known = {s["span_id"] for s in spans}
    roots = [s for s in spans if s["parent_id"] not in known]
    origin = min(s["start"] for s in spans)
    lines: list[str] = []

    def walk(span: dict, depth: int) -> None:
        seconds = (span["end"] or span["start"]) - span["start"]
        lines.append(f'{span["start"] - origin:+8.2f}s {seconds:7.2f}s  {"  " * depth}{_describe(span)}')
        for child in sorted(children.get(span["span_id"], []), key=lambda s: s["start"]):
            walk(child, depth + 1)

    for root in sorted(roots, key=lambda s: s["start"]):
        walk(root, 0)
    return lines


def report(spans: list[dict]) -> str:
    summary = summarize(spans)
    lines = [
        f'Trace {summary["trace_id"]}  conversation {summary["conversation_id"]}  started {summary["started"]}  '
        f'{summary["seconds"]} s  {summary["status"]}',
        f'Visualization requests: {", ".join(summary["request_ids"]) or "none"}',
    ]
    if summary["errors"]:
        lines.append(f'Error: {_preview("; ".join(summary["errors"]), 300)}')
    lines += ["", "Timeline (offset, duration)", *timeline(spans), "",
              f'Model calls counted toward request_limit: {summary["counted_calls"]} of {summary["request_limit"]}'
              f'{"  — LIMIT REACHED" if summary["request_limit_reached"] else ""}']
    for agent, count in sorted(summary["counted_by_agent"].items(), key=lambda item: -item[1]):
        lines.append(f"  {agent:<16} {count}")
    lines.append("By the lead's tool call that spent them:")
    for tool, count in sorted(summary["counted_by_lead_tool"].items(), key=lambda item: -item[1]):
        lines.append(f"  {tool:<28} {count}")
    lines.append(f'Model calls that failed or did not count: {len(summary["failed_calls"])}')
    for call in summary["failed_calls"]:
        lines.append(f'  call {call["call_number"]} {call["agent"]}: {_preview("; ".join(call["errors"]), 200)}')
    lines.append(f'Tool calls{" — TOOL LIMIT REACHED" if summary["tool_calls_limit_reached"] else ""}: '
                 + ", ".join(f"{name} ×{count}" for name, count in summary["tool_calls"].items()))
    lines.append(f'Tool calls returned as retries/failures: {len(summary["tool_retries"])}')
    for retry in summary["tool_retries"]:
        lines.append(f'  {retry["agent"]}:{retry["tool"]}: {retry["error"]}')
    lines.append(f'HTTP attempts: {summary["http_attempts"]}, SDK retries: {summary["sdk_retries"]}, '
                 f'non-2xx: {len(summary["http_failures"])}')
    for failure in summary["http_failures"]:
        lines.append(f"  {_preview(failure, 200)}")
    if summary["final_result"]:
        lines.append(f'Final result: {_preview(summary["final_result"], 400)}')
    return "\n".join(lines)
