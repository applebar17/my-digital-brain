"""Memory-ingestion prompt template exports.

The canonical active prompt constants live in ``prompts.active``. This module
keeps the previous memory-specific import path stable.
"""

from my_digital_brain.prompts.active import (
    MEMORY_CREATION_SYSTEM_TEMPLATE,
    MEMORY_EDGE_PLANNING_SYSTEM_TEMPLATE,
    MEMORY_INGESTION_SYSTEM_TEMPLATE,
    MEMORY_LOG_PLANNING_SYSTEM_TEMPLATE,
    MEMORY_NODE_PLANNING_SYSTEM_TEMPLATE,
    MEMORY_PROMPT_TEMPLATES,
)

__all__ = [
    "MEMORY_CREATION_SYSTEM_TEMPLATE",
    "MEMORY_EDGE_PLANNING_SYSTEM_TEMPLATE",
    "MEMORY_INGESTION_SYSTEM_TEMPLATE",
    "MEMORY_LOG_PLANNING_SYSTEM_TEMPLATE",
    "MEMORY_NODE_PLANNING_SYSTEM_TEMPLATE",
    "MEMORY_PROMPT_TEMPLATES",
]
