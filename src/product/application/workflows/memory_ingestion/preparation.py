"""Deterministic preparation for the memory-ingestion workflow."""

from product.agentic.tools import RegisteredTool
from product.application.references import ReferenceContext
from product.application.tools.memory_search import (
    MemorySearchToolInputDTO,
    MemorySearchToolResultDTO,
)
from product.application.workflows.base import WorkflowContext
from product.application.workflows.memory_ingestion.models import (
    IngestionOwnerIdentityDTO,
    IngestionPreparedContextDTO,
    IngestMemoryRequestDTO,
)


class IngestionContextPreparer:
    """Register the active owner and retrieve bounded model-safe graph context."""

    def __init__(
        self,
        *,
        owner: IngestionOwnerIdentityDTO,
        reference_context: ReferenceContext,
        search_tool: RegisteredTool[MemorySearchToolInputDTO, MemorySearchToolResultDTO],
    ) -> None:
        self.owner = owner
        self.reference_context = reference_context
        self.search_tool = search_tool

    def invoke_with_context(
        self,
        request: IngestMemoryRequestDTO,
        context: WorkflowContext,
    ) -> IngestionPreparedContextDTO:
        """Register dynamic owner context, then perform one bounded semantic retrieval.

        Dependencies:
            `ReferenceContext` owns the safe owner/backend mapping. The injected
            memory-search tool owns owner-scoped retrieval and registration of
            returned model-facing references.
        """
        invocation_context = context.invocation_context
        if invocation_context is None:
            raise ValueError("Ingestion preparation requires parent invocation context.")
        search_query = "\n".join(
            f"{message.role}: {message.as_text()}"
            for message in invocation_context.inherited_history()
            if message.as_text()
        )
        if not search_query:
            raise ValueError("Memory ingestion requires inherited conversational content.")

        owner_context = self.reference_context.register_owner(
            self.owner.backend_id,
            name=self.owner.name,
            surname=self.owner.surname,
        )
        result = self.search_tool.invoke(
            semantic_query=search_query,
            neighborhood_depth=1,
            limit=10,
        )
        if not isinstance(result, MemorySearchToolResultDTO):
            raise TypeError("Ingestion context search returned an unexpected result contract.")
        return IngestionPreparedContextDTO(
            request=request,
            owner=owner_context,
            known_references=self.reference_context.entries(),
            retrieved_memory=result,
        )
