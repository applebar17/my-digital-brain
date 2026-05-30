from __future__ import annotations


class GraphError(Exception):
    """Base exception for graph domain failures."""


class GraphValidationError(GraphError):
    """Raised when graph input violates the domain contract."""


class GraphNotFoundError(GraphError):
    """Raised when a requested graph record does not exist."""


class GraphConflictError(GraphError):
    """Raised when a graph write conflicts with an explicit uniqueness rule."""
