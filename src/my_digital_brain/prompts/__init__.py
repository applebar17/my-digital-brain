"""Centralized prompt registry and template loading."""

from my_digital_brain.prompts.models import PromptTemplate
from my_digital_brain.prompts.registry import PromptNotFoundError, PromptRegistry
from my_digital_brain.prompts.memory_ingestion import (
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
    "PromptNotFoundError",
    "PromptRegistry",
    "PromptTemplate",
]
