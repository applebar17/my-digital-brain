from __future__ import annotations

import argparse
import logging
from pathlib import Path

from uat_refined_trace_common import (
    DEFAULT_ENV_FILE,
    build_trace_service,
    load_graph_context_pack,
    source_from_file,
    write_failure_report,
    write_report,
)


DEFAULT_OUTPUT = Path("docs/uat/refined-ingestion-trace.txt")
logger = logging.getLogger("uat_refined_trace")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    source = source_from_file(input_path, timezone_name=args.timezone)
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
        "route": "local_uat_refined_ingestion",
        "selected_path": "reasoning -> entity planning -> entity candidates -> relationship planning -> relationship candidates",
        "reason": (
            "This script treats the input text as a memory-ingestion source "
            "and avoids backend API, graph database, vector database, and "
            "persisted memory dependencies."
        ),
        "env_file": args.env_file,
        "env_override": args.env_override,
    }
    try:
        result = service.process_source(source)
    except Exception as exc:
        logger.exception("Refined ingestion UAT trace failed.")
        write_failure_report(
            Path(args.output),
            title="My Digital Brain - Refined Ingestion UAT Trace",
            source=source,
            route=route,
            error=exc,
            structured_calls=provider.structured_calls,
        )
        print(f"Wrote failed refined ingestion UAT trace to {args.output}")
        return 1
    write_report(
        Path(args.output),
        title="My Digital Brain - Refined Ingestion UAT Trace",
        source=source,
        route=route,
        result=result,
        structured_calls=provider.structured_calls,
    )
    print(f"Wrote refined ingestion UAT trace to {args.output}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a graph/database-free UAT trace for the refined ingestion flow "
            "from a local text file."
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


if __name__ == "__main__":
    raise SystemExit(main())
