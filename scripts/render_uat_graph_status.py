from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import textwrap
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_OUTPUT = Path("docs/uat/current-graph-status.txt")
DEFAULT_PROBES = ("mio fratello", "coinquilino")
SECRET_MARKERS = (
    "token",
    "secret",
    "password",
    "credential",
    "api_key",
    "apikey",
    "authorization",
)


class ApiClient:
    def __init__(self, base_url: str, *, timeout: float, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = token

    def get(self, path: str, **query: Any) -> Any:
        url = f"{self.base_url}{path}"
        clean_query = {key: value for key, value in query.items() if value not in (None, "")}
        if clean_query:
            url = f"{url}?{urlencode(clean_query, doseq=True)}"
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GET {url} failed with HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"GET {url} failed: {exc.reason}") from exc
        return json.loads(payload) if payload else None


def main() -> int:
    args = parse_args()
    client = ApiClient(args.api_base_url, timeout=args.timeout, token=args.token)
    lines = build_report(
        client,
        api_base_url=args.api_base_url,
        node_limit=args.node_limit,
        issue_limit=args.issue_limit,
        search_limit=args.search_limit,
        random_limit=args.random_limit,
        random_pool_limit=args.random_pool_limit,
        random_seed=args.random_seed,
        reference_memory=reference_text(args.reference_memory, args.reference_memory_file),
        reference_chat_history=reference_text(
            args.reference_chat_history,
            args.reference_chat_history_file,
        ),
        probes=args.probe or list(DEFAULT_PROBES),
        include_archived=args.include_archived,
        include_technical=args.include_technical,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote UAT graph status report to {output}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a human-readable UAT snapshot of the memory graph API.",
    )
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--token", default=None)
    parser.add_argument("--reference-memory", default=None)
    parser.add_argument("--reference-memory-file", default=None)
    parser.add_argument("--reference-chat-history", default=None)
    parser.add_argument("--reference-chat-history-file", default=None)
    parser.add_argument("--node-limit", type=int, default=25)
    parser.add_argument("--issue-limit", type=int, default=20)
    parser.add_argument("--search-limit", type=int, default=10)
    parser.add_argument("--random-limit", type=int, default=0)
    parser.add_argument("--random-pool-limit", type=int, default=200)
    parser.add_argument("--random-seed", default=None)
    parser.add_argument("--probe", action="append", default=None)
    parser.add_argument("--include-archived", action="store_true")
    parser.add_argument("--include-technical", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args()


def build_report(
    client: ApiClient,
    *,
    api_base_url: str,
    node_limit: int,
    issue_limit: int,
    search_limit: int,
    random_limit: int,
    random_pool_limit: int,
    random_seed: str | None,
    reference_memory: str | None,
    reference_chat_history: str | None,
    probes: list[str],
    include_archived: bool,
    include_technical: bool,
) -> list[str]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        "My Digital Brain - UAT Graph Status",
        "=" * 36,
        "",
        f"Generated at: {generated_at}",
        f"Include archived: {include_archived}",
        f"Technical references: {'included' if include_technical else 'hidden'}",
        "",
    ]
    if include_technical:
        lines.insert(4, f"API base URL: {api_base_url.rstrip('/')}")

    append_reference_context(
        lines,
        reference_memory=reference_memory,
        reference_chat_history=reference_chat_history,
    )

    analytics = fetch_optional(
        client,
        "/graph/analytics/summary",
        include_archived=include_archived,
        limit=max(node_limit, issue_limit),
    )
    append_analytics(lines, analytics, include_technical=include_technical)

    nodes = fetch_optional(
        client,
        "/graph/nodes/search",
        lifecycle_state=None if include_archived else "active",
        limit=node_limit,
    )
    append_node_sample(lines, nodes or [], include_technical=include_technical)

    append_random_graph_sample(
        lines,
        client,
        limit=random_limit,
        pool_limit=random_pool_limit,
        random_seed=random_seed,
        include_archived=include_archived,
        include_technical=include_technical,
    )

    contradictions = fetch_optional(
        client,
        "/graph/contradictions",
        status="detected",
        limit=issue_limit,
    )
    append_record_sample(
        lines,
        "Detected Contradictions",
        contradictions or [],
        include_technical=include_technical,
    )

    merges = fetch_optional(client, "/graph/merges", status="proposed", limit=issue_limit)
    append_record_sample(
        lines,
        "Proposed Merges",
        merges or [],
        include_technical=include_technical,
    )

    append_retrieval_probes(
        lines,
        client,
        probes=dedupe([probe for probe in probes if probe.strip()]),
        search_limit=search_limit,
        include_archived=include_archived,
        include_technical=include_technical,
    )
    append_review_notes(lines)
    return lines


def reference_text(inline: str | None, file_path: str | None) -> str | None:
    if inline:
        return inline.strip()
    if not file_path:
        return None
    return Path(file_path).read_text(encoding="utf-8").strip()


def fetch_optional(client: ApiClient, path: str, **query: Any) -> Any:
    try:
        return client.get(path, **query)
    except RuntimeError as exc:
        return {"_uat_error": str(exc)}


def append_reference_context(
    lines: list[str],
    *,
    reference_memory: str | None,
    reference_chat_history: str | None,
) -> None:
    lines.extend(["Reference Context", "-" * 17])
    lines.append("Reference memory/source:")
    lines.extend(indent_text(reference_memory or "[not provided]", indent="  "))
    lines.append("")
    lines.append("Reference chat history:")
    if reference_chat_history:
        lines.extend(indent_text(reference_chat_history, indent="  "))
    else:
        lines.append("  [not provided]")
        lines.append("  Placeholder: add relevant user/assistant turns with")
        lines.append("  --reference-chat-history-file when comparing storage behavior.")
    lines.append("")


def append_analytics(lines: list[str], analytics: Any, *, include_technical: bool) -> None:
    lines.extend(["Graph Analytics", "-" * 15])
    if append_error_if_needed(lines, analytics, include_technical=include_technical):
        return
    analytics = analytics or {}
    node_counts = dict(sorted(analytics.get("node_counts", {}).items()))
    relationship_counts = dict(sorted(analytics.get("relationship_counts", {}).items()))
    lines.append(f"Total nodes: {sum_ints(node_counts.values())}")
    lines.append(f"Total relationships: {sum_ints(relationship_counts.values())}")
    lines.append(f"Unresolved contradictions: {analytics.get('unresolved_contradictions', 0)}")
    lines.append("")
    append_count_block(lines, "Nodes by label", node_counts)
    append_count_block(lines, "Relationships by type", relationship_counts)
    append_item_block(
        lines,
        "Top connected nodes",
        analytics.get("top_connected_nodes", []),
        include_technical=include_technical,
    )
    append_item_block(
        lines,
        "Top emotion tags",
        analytics.get("top_emotion_tags", []),
        include_technical=include_technical,
    )


def append_node_sample(
    lines: list[str],
    nodes: list[dict[str, Any]],
    *,
    include_technical: bool,
) -> None:
    lines.extend(["Graph Node Sample", "-" * 17])
    if append_error_if_needed(lines, nodes, include_technical=include_technical):
        return
    if not nodes:
        lines.extend(["No nodes returned.", ""])
        return
    for index, node in enumerate(nodes, start=1):
        properties = sanitize_mapping(node.get("properties", {}))
        lines.append(f"{index}. {node_title(node)}")
        lines.append(f"   label: {node.get('label', 'unknown')}")
        if include_technical:
            lines.append(f"   id: {properties.get('id', 'unknown')}")
        append_properties(lines, properties, keys=display_property_keys(), indent="   ")
    lines.append("")


def append_random_graph_sample(
    lines: list[str],
    client: ApiClient,
    *,
    limit: int,
    pool_limit: int,
    random_seed: str | None,
    include_archived: bool,
    include_technical: bool,
) -> None:
    lines.extend(["Random Graph Sample", "-" * 19])
    if limit <= 0:
        lines.extend(["Disabled. Use --random-limit N to include this section.", ""])
        return
    pool = fetch_optional(
        client,
        "/graph/nodes/search",
        lifecycle_state=None if include_archived else "active",
        limit=pool_limit,
    )
    if append_error_if_needed(lines, pool, include_technical=include_technical):
        return
    if not pool:
        lines.extend(["No nodes returned for random sampling.", ""])
        return

    sampler = random.Random(random_seed)
    selected_nodes = sample_items(pool, limit, sampler)
    relationships = fetch_relationship_pool(client, selected_nodes, pool_limit=pool_limit)
    selected_relationships = sample_items(relationships, limit, sampler)
    title_cache = {
        str(node.get("properties", {}).get("id")): node_title(node)
        for node in selected_nodes
        if node.get("properties", {}).get("id")
    }

    lines.append(f"Requested limit: {limit}")
    lines.append(f"Node pool fetched: {len(pool)}")
    lines.append(f"Relationship pool fetched from selected nodes: {len(relationships)}")
    lines.append(f"Random seed: {random_seed or 'system entropy'}")
    lines.append("")
    lines.append("Random nodes:")
    for index, node in enumerate(selected_nodes, start=1):
        properties = sanitize_mapping(node.get("properties", {}))
        lines.append(f"  {index}. {node_title(node)}")
        lines.append(f"     label: {node.get('label', 'unknown')}")
        if include_technical:
            lines.append(f"     id: {properties.get('id', 'unknown')}")
        append_properties(lines, properties, keys=display_property_keys(), indent="     ")

    lines.append("")
    lines.append("Random edges:")
    if not selected_relationships:
        lines.append("  none")
    for index, relationship in enumerate(selected_relationships, start=1):
        append_relationship(
            lines,
            client,
            relationship,
            index=index,
            title_cache=title_cache,
            include_technical=include_technical,
        )
    lines.append("")


def append_record_sample(
    lines: list[str],
    title: str,
    records: list[dict[str, Any]],
    *,
    include_technical: bool,
) -> None:
    lines.extend([title, "-" * len(title)])
    if append_error_if_needed(lines, records, include_technical=include_technical):
        return
    if not records:
        lines.extend(["No records returned.", ""])
        return
    for index, record in enumerate(records, start=1):
        properties = sanitize_mapping(record.get("properties", {}))
        lines.append(f"{index}. {first_text(properties, 'title', 'description', 'reason')}")
        lines.append(f"   label: {record.get('label', 'unknown')}")
        if include_technical:
            lines.append(f"   id: {properties.get('id', 'unknown')}")
        append_properties(lines, properties, keys=record_property_keys(), indent="   ")
    lines.append("")


def append_retrieval_probes(
    lines: list[str],
    client: ApiClient,
    *,
    probes: list[str],
    search_limit: int,
    include_archived: bool,
    include_technical: bool,
) -> None:
    lines.extend(["Hybrid Retrieval Probes", "-" * 23])
    if not probes:
        lines.extend(["No probe queries configured.", ""])
        return
    for query in probes:
        result = fetch_optional(
            client,
            "/graph/search/hybrid",
            query=query,
            include_archived=include_archived,
            include_history=True,
            limit=search_limit,
        )
        lines.append(f"Query: {query}")
        if append_error_if_needed(
            lines,
            result,
            indent="  ",
            include_technical=include_technical,
        ):
            continue
        hits = result.get("hits", [])
        graph_view = result.get("graph_view", {})
        lines.append(f"  hits: {len(hits)}")
        lines.append(f"  rendered nodes: {len(graph_view.get('nodes', []))}")
        lines.append(f"  rendered edges: {len(graph_view.get('relationships', []))}")
        append_hits(lines, hits, include_technical=include_technical)
        append_graph_assembly(
            lines,
            result.get("trace", []),
            include_technical=include_technical,
        )
        append_rendered_graph(lines, graph_view, include_technical=include_technical)
        lines.append("")


def append_hits(
    lines: list[str],
    hits: list[dict[str, Any]],
    *,
    include_technical: bool,
) -> None:
    if not hits:
        lines.append("  retrieval hits: none")
        return
    lines.append("  retrieval hits:")
    for hit in hits:
        summary = (
            f"#{hit.get('rank')} score={format_score(hit.get('score'))} "
            f"source={hit.get('source')} label={hit.get('primary_target_label')}"
        )
        if include_technical:
            summary = (
                f"{summary} id="
                f"{hit.get('canonical_target_id') or hit.get('primary_target_id')}"
            )
        lines.append(f"    {summary}")
        if hit.get("title"):
            lines.append(f"      title: {clip(hit['title'], 180)}")
        description = hit.get("description") or hit.get("document_preview")
        if description:
            lines.append(f"      text: {clip(description, 240)}")
        if include_technical and hit.get("related_target_ids"):
            lines.append(f"      related: {format_list(hit['related_target_ids'])}")


def append_graph_assembly(
    lines: list[str],
    trace: list[dict[str, Any]],
    *,
    include_technical: bool,
) -> None:
    event = next((item for item in trace if item.get("stage") == "graph_assembly"), None)
    if not event:
        return
    data = event.get("data", {})
    lines.append("  graph assembly:")
    lines.append(
        "    "
        f"mode={data.get('focus_mode')} algorithm={data.get('focus_algorithm')} "
        f"reason={data.get('focus_reason')} threshold={format_score(data.get('focus_threshold'))}"
    )
    if include_technical:
        lines.append(f"    selected: {format_list(data.get('selected_target_ids', []))}")
        lines.append(f"    excluded: {format_list(data.get('excluded_target_ids', []))}")
    else:
        lines.append(f"    selected hits: {data.get('selected_hit_count', 'n/a')}")
        lines.append(f"    excluded hits: {data.get('excluded_hit_count', 'n/a')}")


def append_rendered_graph(
    lines: list[str],
    graph_view: dict[str, Any],
    *,
    include_technical: bool,
) -> None:
    nodes = graph_view.get("nodes", [])
    relationships = graph_view.get("relationships", [])
    title_by_id = {node.get("id"): node.get("title") or node.get("label") for node in nodes}
    if nodes:
        lines.append("  rendered nodes:")
        for node in nodes[:12]:
            title = clip(str(node.get("title") or ""), 120)
            if include_technical:
                lines.append(f"    {node.get('id')} [{node.get('label')}] {title}")
            else:
                lines.append(f"    [{node.get('label')}] {title}")
    if relationships:
        lines.append("  rendered edges:")
        for relationship in relationships[:12]:
            if include_technical:
                lines.append(
                    "    "
                    f"{relationship.get('id')} {relationship.get('type')} "
                    f"{relationship.get('from_id')} -> {relationship.get('to_id')}"
                )
            else:
                from_title = title_by_id.get(relationship.get("from_id"), "unknown")
                to_title = title_by_id.get(relationship.get("to_id"), "unknown")
                lines.append(f"    {relationship.get('type')}: {from_title} -> {to_title}")


def append_relationship(
    lines: list[str],
    client: ApiClient,
    relationship: dict[str, Any],
    *,
    index: int,
    title_cache: dict[str, str],
    include_technical: bool,
) -> None:
    properties = sanitize_mapping(relationship.get("properties", {}))
    if include_technical:
        relationship_id = properties.get("id", "unknown")
        lines.append(
            "  "
            f"{index}. {relationship_id} {relationship.get('type', 'unknown')} "
            f"{relationship.get('from_id', 'unknown')} -> "
            f"{relationship.get('to_id', 'unknown')}"
        )
    else:
        from_title = endpoint_title(client, relationship.get("from_id"), title_cache)
        to_title = endpoint_title(client, relationship.get("to_id"), title_cache)
        lines.append(
            f"  {index}. {relationship.get('type', 'unknown')}: "
            f"{from_title} -> {to_title}"
        )
    append_properties(lines, properties, keys=relationship_property_keys(), indent="     ")


def append_review_notes(lines: list[str]) -> None:
    lines.extend(
        [
            "UAT Review Notes",
            "-" * 16,
            "- Check whether important people, relationships, perceptions, and profile "
            "memories are visible.",
            "- Check whether aliases and duplicate entities need merge prompt tuning.",
            "- Check whether relationship_kind/detail fields capture family, roommate, "
            "friend, colleague, and similar intents.",
            "- Check whether emotional summaries and original user words are useful, "
            "grounded, and not over-inferred.",
            "- Check whether hybrid retrieval probes render graph nodes/edges that "
            "explain the query.",
            "",
        ]
    )


def fetch_relationship_pool(
    client: ApiClient,
    nodes: list[dict[str, Any]],
    *,
    pool_limit: int,
) -> list[dict[str, Any]]:
    relationships_by_key: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_id = node.get("properties", {}).get("id")
        if not node_id:
            continue
        result = fetch_optional(
            client,
            f"/graph/nodes/{quote(str(node_id), safe='')}/relationships",
            direction="both",
            limit=pool_limit,
        )
        if isinstance(result, dict) and "_uat_error" in result:
            continue
        for relationship in result or []:
            properties = relationship.get("properties", {})
            key = str(
                properties.get("id")
                or (
                    f"{relationship.get('type')}:{relationship.get('from_id')}:"
                    f"{relationship.get('to_id')}"
                )
            )
            relationships_by_key[key] = relationship
    return list(relationships_by_key.values())


def endpoint_title(client: ApiClient, node_id: Any, cache: dict[str, str]) -> str:
    if not node_id:
        return "unknown"
    key = str(node_id)
    if key in cache:
        return cache[key]
    result = fetch_optional(client, f"/graph/nodes/{quote(key, safe='')}")
    if isinstance(result, dict) and "_uat_error" not in result:
        cache[key] = node_title(result)
        return cache[key]
    return "unknown"


def append_count_block(lines: list[str], title: str, counts: dict[str, int]) -> None:
    lines.append(f"{title}:")
    if not counts:
        lines.append("  none")
    else:
        for key, count in counts.items():
            lines.append(f"  {key}: {count}")
    lines.append("")


def append_item_block(
    lines: list[str],
    title: str,
    items: list[dict[str, Any]],
    *,
    include_technical: bool,
) -> None:
    lines.append(f"{title}:")
    if not items:
        lines.append("  none")
    else:
        for item in items:
            if include_technical:
                label = f" ({item.get('label')})" if item.get("label") else ""
                lines.append(f"  {item.get('key')}{label}: {item.get('count')}")
            else:
                lines.append(f"  {item.get('label') or item.get('key')}: {item.get('count')}")
    lines.append("")


def append_properties(
    lines: list[str],
    properties: dict[str, Any],
    *,
    keys: list[str],
    indent: str,
) -> None:
    for key in keys:
        value = properties.get(key)
        if value in (None, "", [], {}):
            continue
        lines.append(f"{indent}{key}: {format_value(value)}")


def append_error_if_needed(
    lines: list[str],
    value: Any,
    *,
    include_technical: bool,
    indent: str = "",
) -> bool:
    if isinstance(value, dict) and "_uat_error" in value:
        message = (
            value["_uat_error"]
            if include_technical
            else "Endpoint unavailable or returned an API error. "
            "Re-run with --include-technical for endpoint details."
        )
        lines.extend(indent_text(message, indent=indent))
        lines.append("")
        return True
    return False


def display_property_keys() -> list[str]:
    return [
        "lifecycle_state",
        "privacy_level",
        "trust_level",
        "status",
        "relationship_kind",
        "relationship_detail",
        "known_since",
        "time_value",
        "time_precision",
        "city",
        "country",
        "emotional_summary",
        "original_user_words",
        "description",
    ]


def record_property_keys() -> list[str]:
    return [
        "status",
        "severity",
        "contradiction_type",
        "reason",
        "description",
        "created_at",
        "updated_at",
    ]


def relationship_property_keys() -> list[str]:
    return [
        "lifecycle_state",
        "trust_level",
        "relationship_kind",
        "relationship_detail",
        "description",
        "emotional_summary",
    ]


def sanitize_mapping(value: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        if any(marker in key.lower() for marker in SECRET_MARKERS):
            sanitized[key] = "[redacted]"
        else:
            sanitized[key] = item
    return sanitized


def first_text(properties: dict[str, Any], *keys: str, fallback: Any = "Record") -> str:
    for key in keys:
        value = properties.get(key)
        if isinstance(value, str) and value.strip():
            return clip(value.strip(), 180)
    return clip(str(fallback or "unknown"), 180)


def node_title(node: dict[str, Any]) -> str:
    properties = sanitize_mapping(node.get("properties", {}))
    return first_text(
        properties,
        "display_name",
        "name",
        "title",
        "text",
        "description",
        "value",
        fallback=properties.get("id", "unknown"),
    )


def sample_items(
    items: list[dict[str, Any]],
    limit: int,
    sampler: random.Random,
) -> list[dict[str, Any]]:
    if len(items) <= limit:
        return list(items)
    return sampler.sample(items, limit)


def format_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(clip(str(item), 80) for item in value[:10])
    if isinstance(value, dict):
        return json.dumps(sanitize_mapping(value), ensure_ascii=False, sort_keys=True)
    return clip(str(value), 240)


def format_score(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return "n/a"


def format_list(values: Any) -> str:
    if not values:
        return "none"
    return ", ".join(map(str, values[:12]))


def indent_text(value: str, *, indent: str) -> list[str]:
    return textwrap.wrap(
        " ".join(str(value).split()),
        width=100,
        initial_indent=indent,
        subsequent_indent=indent,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [indent]


def clip(value: str, max_chars: int) -> str:
    compact = " ".join(str(value).split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def sum_ints(values: Any) -> int:
    total = 0
    for value in values:
        try:
            total += int(value)
        except (TypeError, ValueError):
            continue
    return total


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


if __name__ == "__main__":
    raise SystemExit(main())
