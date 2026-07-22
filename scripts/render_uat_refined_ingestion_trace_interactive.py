from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from uat_refined_trace_common import (
    DEFAULT_ENV_FILE,
    build_trace_service,
    load_graph_context_pack,
    source_from_file,
)

from my_digital_brain.agentic import AgenticHistoryService
from my_digital_brain.chat.models import ClarificationPacket
from my_digital_brain.clarification import ClarificationService

DEFAULT_OUTPUT = Path("docs/uat/refined-ingestion-trace.txt")
logger = logging.getLogger("uat_ingestion_trace")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    source = source_from_file(input_path, timezone_name=args.timezone)
    base_raw_text = source.raw_text or source.content_ref or ""
    graph_context_pack = load_graph_context_pack(
        Path(args.graph_context) if args.graph_context else None,
        source_id=source.source_id,
    )
    service, provider = build_trace_service(
        graph_context_pack=graph_context_pack,
        env_file=Path(args.env_file) if args.env_file else None,
        override_env=args.env_override,
    )
    route: dict[str, Any] = {
        "route": "local_uat_refined_ingestion_interactive",
        "selected_path": (
            "reasoning -> entity planning -> entity candidates -> "
            "relationship planning -> relationship candidates"
        ),
        "reason": (
            "This script treats the input text as a memory-ingestion source, "
            "asks terminal clarification questions when the dry run blocks, "
            "and avoids backend API, graph database, vector database, and "
            "persisted memory dependencies."
        ),
        "env_file": args.env_file,
        "env_override": args.env_override,
        "clarification_interactions": [],
    }
    trace_events: list[dict[str, Any]] = []
    try:
        source, result = _answer_clarifications_from_terminal(
            service,
            source,
            base_raw_text=base_raw_text,
            result=None,
            route=route,
            structured_calls=provider.structured_calls,
            tool_calls=provider.tool_calls,
            trace_events=trace_events,
        )
    except Exception as exc:
        logger.exception("Interactive ingestion UAT trace failed.")
        _write_chronological_failure_report(
            Path(args.output),
            title="My Digital Brain - Interactive Ingestion UAT Trace",
            source_text=base_raw_text,
            route=route,
            error=exc,
            structured_calls=provider.structured_calls,
            tool_calls=provider.tool_calls,
            trace_events=trace_events,
        )
        print(f"Wrote failed interactive ingestion UAT trace to {args.output}")
        return 1
    _write_chronological_report(
        Path(args.output),
        title="My Digital Brain - Interactive Ingestion UAT Trace",
        source_text=base_raw_text,
        route=route,
        result=result,
        structured_calls=provider.structured_calls,
        tool_calls=provider.tool_calls,
        trace_events=trace_events,
    )
    print(f"Wrote interactive ingestion UAT trace to {args.output}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a graph/database-free UAT trace for the reasoning-first ingestion flow "
            "from a local text file, asking terminal clarifications when needed."
        ),
    )
    parser.add_argument("--input", required=True, help="Local .txt file used as the user message.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output .txt report path.")
    parser.add_argument(
        "--graph-context",
        default=None,
        help="Optional GraphContextPack JSON fixture. Defaults to an empty local pack.",
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help="Env file loaded before provider setup. Defaults to src/my_digital_brain/.env.",
    )
    parser.add_argument(
        "--env-override",
        action="store_true",
        help="Override already-set process environment variables with --env-file values.",
    )
    parser.add_argument("--timezone", default="Europe/Rome")
    return parser.parse_args()


def _answer_clarifications_from_terminal(
    service: Any,
    source: Any,
    *,
    base_raw_text: str,
    result: Any,
    route: dict[str, Any],
    structured_calls: list[Any],
    tool_calls: list[Any],
    trace_events: list[dict[str, Any]],
) -> tuple[Any, Any]:
    interactions = route["clarification_interactions"]
    if result is None:
        result = service.process_source(source)
    attempt = 0
    while True:
        pending_packet = _pending_clarification_packet(result)
        if pending_packet is None:
            route["clarification_stop_reason"] = "no_pending_clarification"
            return source, result
        attempt += 1

        question = pending_packet.questions[0]
        print("")
        print("Clarification needed before continuing the local UAT trace.")
        print(f"Stage: {pending_packet.origin_state_id}")
        print(f"Question: {question.question}")
        if question.options:
            print("Options: " + ", ".join(option.label for option in question.options))
        if pending_packet.target_refs:
            print(f"Target refs: {', '.join(pending_packet.target_refs)}")
        event = {
            "type": "clarification",
            "after_call_count": len(structured_calls),
            "attempt": attempt,
            "stage": pending_packet.origin_state_id,
            "question": question.question,
            "reason": pending_packet.reason,
            "target_refs": list(pending_packet.target_refs),
            "options": [option.label for option in question.options],
        }
        try:
            answer = input("Answer (leave empty to stop): ").strip()
        except EOFError:
            event["stop_reason"] = "stdin_eof"
            trace_events.append(event)
            route["clarification_stop_reason"] = "stdin_eof"
            return source, None
        if not answer:
            event["stop_reason"] = "empty_answer"
            trace_events.append(event)
            route["clarification_stop_reason"] = "empty_answer"
            return source, None
        event["answer"] = answer
        trace_events.append(event)
        interactions.append({**event, "answer": answer})
        clarification_service = ClarificationService()
        _, answer_history = clarification_service.answer_text(pending_packet, answer)
        source = _source_with_clarification_history(
            source,
            base_raw_text=base_raw_text,
            packet=pending_packet,
            answer_history=answer_history,
        )
        result = service.resume_pending(source, result, answer)


def _pending_clarification_packet(result: Any) -> ClarificationPacket | None:
    """Extract a pending packet when a channel-aware service exposes one."""
    interaction = getattr(result, "pending_interaction", None)
    packet = getattr(interaction, "clarification_packet", None)
    if isinstance(packet, dict):
        return ClarificationPacket.model_validate(packet)
    continuation = getattr(result, "continuation", None)
    for event in getattr(result, "tool_events", []):
        payload = getattr(getattr(event, "result", None), "data", None) or {}
        packet = payload.get("clarification_packet")
        if packet:
            return ClarificationPacket.model_validate(packet)
    if continuation is not None:
        for event in continuation.tool_events:
            payload = event.result.data or {}
            packet = payload.get("clarification_packet")
            if packet:
                return ClarificationPacket.model_validate(packet)
    return None


def _source_with_clarification_history(
    source: Any,
    *,
    base_raw_text: str,
    packet: ClarificationPacket,
    answer_history: list[dict[str, str]],
) -> Any:
    history = AgenticHistoryService().promote_messages_to_master_history(
        list((source.metadata or {}).get("model_facing_history") or []),
        [*packet.history_delta, *answer_history],
    )
    metadata = {
        **dict(source.metadata or {}),
        "model_facing_history": history,
    }
    return source.model_copy(
        update={
            "raw_text": base_raw_text,
            "metadata": metadata,
        },
        deep=True,
    )


def _write_chronological_report(
    output: Path,
    *,
    title: str,
    source_text: str,
    route: dict[str, Any],
    result: Any,
    structured_calls: list[Any],
    tool_calls: list[Any],
    trace_events: list[dict[str, Any]],
) -> None:
    lines = _base_report_lines(title)
    _append_text_block(lines, "User Request", source_text)
    _append_json_block(lines, "Routing", route)
    _append_execution_trace(lines, structured_calls, tool_calls, trace_events)
    _append_json_block(lines, "Final Ingestion Result", _result_summary(result))
    _write_lines(output, lines)


def _write_chronological_failure_report(
    output: Path,
    *,
    title: str,
    source_text: str,
    route: dict[str, Any],
    error: Exception,
    structured_calls: list[Any],
    tool_calls: list[Any],
    trace_events: list[dict[str, Any]],
) -> None:
    lines = _base_report_lines(title)
    _append_text_block(lines, "User Request", source_text)
    _append_json_block(lines, "Routing", route)
    _append_execution_trace(lines, structured_calls, tool_calls, trace_events)
    _append_json_block(
        lines,
        "Execution Error",
        {
            "error_type": error.__class__.__name__,
            "message": str(error),
        },
    )
    _write_lines(output, lines)


def _append_execution_trace(
    lines: list[str],
    structured_calls: list[Any],
    tool_calls: list[Any],
    trace_events: list[dict[str, Any]],
) -> None:
    lines.extend(["Execution Trace", "===============", ""])
    previous_index = 0
    pass_index = 1
    _append_pass_header(lines, pass_index, "initial input")
    for event in sorted(trace_events, key=lambda item: int(item.get("after_call_count", 0))):
        after_call_count = max(0, min(int(event.get("after_call_count", 0)), len(structured_calls)))
        _append_structured_calls(
            lines, structured_calls[previous_index:after_call_count], previous_index
        )
        previous_index = after_call_count
        _append_clarification_event(lines, event)
        if event.get("answer"):
            pass_index += 1
            _append_pass_header(
                lines,
                pass_index,
                "clarification answer added to model-facing history",
            )
    _append_structured_calls(lines, structured_calls[previous_index:], previous_index)
    if not structured_calls:
        lines.append("No structured provider calls were captured.")
        lines.append("")
    if tool_calls:
        lines.extend(["Tool Calls", "----------", ""])
        for index, call in enumerate(tool_calls, start=1):
            lines.append(f"Tool Call {index}: {call.name}")
            _append_json_block(
                lines,
                "Tool Snapshot",
                {
                    "arguments": call.arguments,
                    "status": call.status,
                    "output": call.output,
                    "error": call.error,
                },
            )


def _append_pass_header(lines: list[str], pass_index: int, reason: str) -> None:
    title = f"Pipeline Pass {pass_index}: {reason}"
    lines.extend([title, "-" * len(title), ""])


def _append_clarification_event(lines: list[str], event: dict[str, Any]) -> None:
    title = f"Clarification Round {event.get('attempt', '?')}"
    lines.extend([title, "-" * len(title), ""])
    _append_json_block(
        lines,
        "Interaction",
        {key: value for key, value in event.items() if key not in {"type", "after_call_count"}},
    )


def _append_structured_calls(
    lines: list[str],
    structured_calls: list[Any],
    start_index: int,
) -> None:
    for offset, call in enumerate(structured_calls, start=1):
        call_index = start_index + offset
        title = f"LLM Session Call {call_index}: {call.schema}"
        lines.extend([title, "-" * len(title), ""])
        lines.append(f"Purpose: {call.purpose or 'unknown'}")
        lines.append(f"Model: {call.model or 'default route'}")
        lines.append(f"Session ID: {call.session_id or 'session-local'}")
        lines.append(f"Continuation: {call.continuation}")
        lines.append(f"Tools: {', '.join(call.tools) if call.tools else '(none)'}")
        lines.append("")
        _append_text_block(lines, "System Prompt", call.system_prompt)
        _append_json_block(lines, "Messages", call.messages)
        if call.error is not None:
            _append_json_block(lines, "Error / Diagnostics", call.error)
        _append_json_block(lines, "Output", call.output)


def _result_summary(result: Any) -> dict[str, Any]:
    if result is None:
        return {
            "status": "stopped_before_completion",
            "reason": "The terminal clarification interaction was not answered.",
        }
    return {
        "status": str(result.status),
        "ingestion_stage": result.metadata.get("ingestion_stage"),
        "pending_interaction": (
            result.pending_interaction.model_dump(mode="json", exclude_none=True)
            if result.pending_interaction is not None
            else None
        ),
        "entity_candidates": len(result.entity_candidates),
        "supplemental_entity_candidates": len(result.supplemental_entity_candidates),
        "relationship_candidates": len(result.relationship_candidates),
        "validation_errors": [
            issue.model_dump(mode="json", exclude_none=True) for issue in result.validation_errors
        ],
        "missing_entities": (
            [
                item.model_dump(mode="json", exclude_none=True)
                for item in result.relationship_plan.missing_entities
            ]
            if result.relationship_plan is not None
            else []
        ),
        "resolved_entity_map": (
            result.resolved_entity_map.model_dump(mode="json", exclude_none=True)
            if result.resolved_entity_map is not None
            else None
        ),
        "final_candidate_graph": (
            result.candidate_graph.model_dump(mode="json", exclude_none=True)
            if result.candidate_graph is not None
            else None
        ),
    }


def _base_report_lines(title: str) -> list[str]:
    return [
        title,
        "=" * len(title),
        "",
        f"Generated at: {datetime.now(UTC).replace(microsecond=0).isoformat()}",
        "Graph/database integrations: disabled",
        "Provider-generated sections are non-deterministic.",
        "Report order: chronological execution trace first, final result last.",
        "",
    ]


def _append_text_block(lines: list[str], title: str, text: str) -> None:
    lines.extend([title, "~" * len(title), ""])
    lines.append(text.strip() or "(empty)")
    lines.append("")


def _append_json_block(lines: list[str], title: str, payload: Any) -> None:
    lines.extend([title, "~" * len(title), ""])
    lines.append(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    lines.append("")


def _write_lines(output: Path, lines: list[str]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
