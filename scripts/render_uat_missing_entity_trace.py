from __future__ import annotations

import argparse
import logging
from pathlib import Path

from uat_refined_trace_common import (
    DEFAULT_ENV_FILE,
    build_trace_service,
    load_entity_candidates,
    load_graph_context_pack,
    source_from_file,
    write_failure_report,
    write_report,
)


DEFAULT_OUTPUT = Path("docs/uat/missing-entity-trace.txt")
logger = logging.getLogger("uat_refined_trace")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    source = source_from_file(input_path, timezone_name=args.timezone)
    entity_candidates = load_entity_candidates(Path(args.entities), source=source)
    graph_context_pack = load_graph_context_pack(
        Path(args.graph_context) if args.graph_context else None,
        source_id=source.source_id,
    )
    service, provider = build_trace_service(
        graph_context_pack=graph_context_pack,
        env_file=Path(args.env_file) if args.env_file else None,
        override_env=args.env_override,
    )
    route = {
        "route": "local_uat_missing_entity_relationship_trace",
        "selected_path": "predefined entities -> relationship planning -> missing entity loop -> relationship candidates",
        "reason": (
            "This script starts from fixture entity candidates so the "
            "relationship planner can be inspected in a controlled missing-endpoint "
            "scenario without backend API, graph database, vector database, or "
            "persisted memory dependencies."
        ),
        "env_file": args.env_file,
        "env_override": args.env_override,
    }
    try:
        result = service.process_source_with_entity_candidates(
            source,
            entity_candidates,
            graph_context_pack=graph_context_pack,
        )
    except Exception as exc:
        logger.exception("Missing-entity UAT trace failed.")
        write_failure_report(
            Path(args.output),
            title="My Digital Brain - Missing Entity UAT Trace",
            source=source,
            route=route,
            error=exc,
            structured_calls=provider.structured_calls,
            initial_entities=entity_candidates,
        )
        print(f"Wrote failed missing-entity UAT trace to {args.output}")
        return 1
    write_report(
        Path(args.output),
        title="My Digital Brain - Missing Entity UAT Trace",
        source=source,
        route=route,
        result=result,
        structured_calls=provider.structured_calls,
        initial_entities=entity_candidates,
    )
    print(f"Wrote missing-entity UAT trace to {args.output}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a graph/database-free UAT trace for the refined relationship "
            "planner from predefined entity candidates."
        ),
    )
    parser.add_argument("--input", required=True, help="Local .txt fictitious ingestion request.")
    parser.add_argument(
        "--entities",
        required=True,
        help="JSON fixture containing CandidateEntity objects or {'candidates': [...]}.",
    )
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


if __name__ == "__main__":
    raise SystemExit(main())
