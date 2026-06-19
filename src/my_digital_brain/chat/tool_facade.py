"""Removed legacy chat facade compatibility module.

Production chat is agentic-only and uses AgenticFrame continuations with direct
service dependencies. This module intentionally exposes no facade API.
"""

raise ImportError(
    "my_digital_brain.chat.tool_facade was removed from active runtime. "
    "Use ChatRuntime with AgenticRuntime and direct services."
)
