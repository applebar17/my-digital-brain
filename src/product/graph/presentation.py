"""Pure display helpers for typed semantic graph nodes."""

from product.graph.models import NodeCreate


def node_display_name(node: NodeCreate) -> str:
    """Return the canonical readable title for one typed node."""
    for field_name in ("display_name", "title", "name"):
        value = getattr(node, field_name, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return node.node_type.value.replace("_", " ").title()
