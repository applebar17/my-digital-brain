from __future__ import annotations

import json
from typing import Any, Protocol

from my_digital_brain.ai.protocols import LLMProvider, ModelRouter
from my_digital_brain.ai.schemas import AIRequestContext, ChatMessage, ChatRequest
from my_digital_brain.ai.tracing import traceable
from my_digital_brain.chat.enums import (
    ChatDiagnosticLevel,
    ChatResponseStatus,
    PendingProcessKind,
)
from my_digital_brain.chat.clarification import build_clarification_packet
from my_digital_brain.chat.facade import (
    CancelPendingProcessRequest,
    ChatToolRequest,
    ChatToolResult,
    NoopBackendToolFacade,
)
from my_digital_brain.chat.models import (
    ChatAction,
    ChatDiagnostic,
    ChatEvidenceRef,
    PendingProcessRef,
)
from my_digital_brain.core.ids import new_uuid
from my_digital_brain.graph.exceptions import GraphNotFoundError
from my_digital_brain.graph.models import GraphContextPackage, NodeSearchResult
from my_digital_brain.ingestion.contracts import SourceRecordRef
from my_digital_brain.ingestion.enums import IngestionStatus, SourceChannel, SourceType
from my_digital_brain.ingestion.service import IngestionService
from my_digital_brain.rag.models import SemanticMemorySearchResult


class GraphContextAnswerGenerator(Protocol):
    def generate_answer(
        self,
        *,
        question: str,
        context_package: GraphContextPackage,
        conversation_id: str,
    ) -> str: ...


class DeterministicGraphContextAnswerGenerator:
    """Low-noise fallback answer builder when no LLM answer provider is configured."""

    def generate_answer(
        self,
        *,
        question: str,
        context_package: GraphContextPackage,
        conversation_id: str,
    ) -> str:
        target_title = context_package.target.get("title") or "this memory"
        lines = [f"I found {target_title} in your memory graph."]

        facts = [
            f"{fact['field']}: {fact['value']}"
            for fact in context_package.current_facts[:5]
            if fact.get("field") and fact.get("value") not in (None, "", [])
        ]
        if facts:
            lines.append("Key facts: " + "; ".join(facts) + ".")

        affective = self._first_affective_summary(context_package)
        if affective:
            lines.append(f"Affective context: {affective}")

        timeline = [
            item
            for item in context_package.timeline[:3]
            if item.get("title") or item.get("description")
        ]
        if timeline:
            timeline_bits = [
                f"{item.get('time') or 'unknown time'}: "
                f"{item.get('title') or item.get('description')}"
                for item in timeline
            ]
            lines.append("Timeline: " + "; ".join(timeline_bits) + ".")

        if context_package.notes:
            lines.append("Notes: " + " ".join(context_package.notes[:2]))

        return " ".join(lines)

    def _first_affective_summary(self, context_package: GraphContextPackage) -> str | None:
        for section in (
            [context_package.target],
            context_package.perceptions,
            context_package.relationship_contexts,
            context_package.relationships,
        ):
            for item in section:
                summary = item.get("emotional_summary")
                if summary:
                    return str(summary)
        return None


class LLMGraphContextAnswerGenerator:
    """Optional answer path using the provider-neutral LLM interface."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        router: ModelRouter | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = provider
        self.router = router
        self.model = model

    @traceable(name="LLM Graph Context Answer", run_type="llm")
    def generate_answer(
        self,
        *,
        question: str,
        context_package: GraphContextPackage,
        conversation_id: str,
    ) -> str:
        context = AIRequestContext(
            purpose="memory_question_answer",
            conversation_id=conversation_id,
        )
        route = self.router.route("memory_question_answer", context) if self.router else None
        result = self.provider.generate_chat(
            ChatRequest(
                model=self.model or (route.model if route else None),
                temperature=0.2,
                max_tokens=500,
                messages=[
                    ChatMessage(
                        role="system",
                        content=(
                            "Answer using only the provided memory graph context. "
                            "Keep the answer concise, natural, and grounded. "
                            "Do not expose raw UUIDs."
                        ),
                    ),
                    ChatMessage(
                        role="user",
                        content=json.dumps(
                            {
                                "question": question,
                                "context": context_package.model_dump(mode="json"),
                            },
                            ensure_ascii=True,
                        ),
                    ),
                ],
                context=context,
                metadata={"route": route.model_dump(mode="json")} if route else {},
            ),
        )
        return result.content


class MemoryBackendToolFacade(NoopBackendToolFacade):
    """Backend tool facade that connects chat tools to graph and ingestion services."""

    def __init__(
        self,
        *,
        graph_service: Any | None = None,
        ingestion_service: IngestionService | None = None,
        semantic_search_service: Any | None = None,
        vectorization_service: Any | None = None,
        answer_generator: GraphContextAnswerGenerator | None = None,
    ) -> None:
        self.graph_service = graph_service
        self.ingestion_service = ingestion_service
        self.semantic_search_service = semantic_search_service
        self.vectorization_service = vectorization_service or getattr(
            ingestion_service,
            "vectorization_service",
            None,
        )
        self.answer_generator = answer_generator or DeterministicGraphContextAnswerGenerator()

    @traceable(name="Memory Tool Start Ingestion", run_type="tool")
    def start_memory_ingestion(self, request: ChatToolRequest) -> ChatToolResult:
        if self.ingestion_service is None:
            return super().start_memory_ingestion(request)

        source = SourceRecordRef(
            source_id=new_uuid(),
            source_type=self._source_type_for_request(request),
            channel=self._source_channel_for_request(request),
            external_id=request.metadata.get("message_id"),
            content_ref=self._content_ref_for_request(request),
            raw_text=request.text or None,
            metadata={
                "conversation_id": request.conversation_id,
                "session_id": request.session_id,
                "owner_id": request.owner_id,
                "chat_channel": request.channel,
            },
        )
        result = self.ingestion_service.process_source(source)
        return self._chat_result_from_ingestion(
            result,
            source=source,
            operation="start_memory_ingestion",
        )

    @traceable(name="Memory Tool Resume Pending Process", run_type="tool")
    def resume_pending_process(self, request: ChatToolRequest) -> ChatToolResult:
        if self.ingestion_service is None:
            return super().resume_pending_process(request)
        pending_context = request.pending_process_context
        if pending_context is None:
            return ChatToolResult(
                status=ChatResponseStatus.FAILED,
                primary_text="There is no pending memory process to resume.",
                diagnostics=[
                    ChatDiagnostic(
                        level=ChatDiagnosticLevel.ERROR,
                        code="missing_pending_process",
                        message="Resume requires a pending process context.",
                    )
                ],
                metadata={"operation": "resume_pending_process"},
            )
        process_kind = str(pending_context.process_ref.kind)
        if process_kind == PendingProcessKind.MEMORY_QUERY.value:
            result = self.query_memory_context(
                request.model_copy(
                    update={"text": self._resumed_text(request, pending_context)},
                    deep=True,
                ),
            )
            return result.model_copy(
                update={
                    "metadata": {
                        **result.metadata,
                        "operation": "resume_pending_process",
                        "resumed_operation": "query_memory_context",
                        "pending_process_id": pending_context.process_ref.process_id,
                        "clear_pending_process": True,
                    }
                },
                deep=True,
            )
        if process_kind == PendingProcessKind.MEMORY_UPDATE.value:
            result = self.update_memory_graph(
                request.model_copy(
                    update={"text": self._resumed_text(request, pending_context)},
                    deep=True,
                ),
            )
            return result.model_copy(
                update={
                    "metadata": {
                        **result.metadata,
                        "operation": "resume_pending_process",
                        "resumed_operation": "update_memory_graph",
                        "pending_process_id": pending_context.process_ref.process_id,
                        "clear_pending_process": result.pending_process is None,
                    }
                },
                deep=True,
            )
        if process_kind != PendingProcessKind.MEMORY_INGESTION.value:
            return ChatToolResult(
                status=ChatResponseStatus.FAILED,
                primary_text="I cannot resume this pending process kind yet.",
                diagnostics=[
                    ChatDiagnostic(
                        level=ChatDiagnosticLevel.ERROR,
                        code="unsupported_pending_process_kind",
                        message=(
                            "Only memory_ingestion, memory_query, and memory_update "
                            "pending processes support resume in this implementation slice."
                        ),
                        details={"kind": process_kind},
                    )
                ],
                metadata={
                    "operation": "resume_pending_process",
                    "pending_process_id": pending_context.process_ref.process_id,
                },
            )

        current_answer = request.text.strip()
        resumed_text = self._resumed_text(request, pending_context)

        original_source_id = (
            pending_context.process_ref.metadata.get("source_id")
            or pending_context.context.get("source_id")
        )
        source = SourceRecordRef(
            source_id=new_uuid(),
            source_type=SourceType.TEXT,
            channel=self._source_channel_for_request(request),
            external_id=request.metadata.get("message_id"),
            content_ref=None,
            raw_text=resumed_text,
            metadata={
                "conversation_id": request.conversation_id,
                "session_id": request.session_id,
                "owner_id": request.owner_id,
                "chat_channel": request.channel,
                "current_user_message": current_answer,
                "clarification_answer_summary": current_answer,
                "resumed_from_pending_process_id": pending_context.process_ref.process_id,
                "original_source_id": original_source_id,
                "checkpoint_schema_version": pending_context.context.get(
                    "checkpoint_schema_version",
                    "v1",
                ),
                "resume_policy": "refresh_context_before_write",
                "conversation_history_refs": list(request.conversation_history_refs),
            },
            )
        result = self.ingestion_service.process_source(source)
        chat_result = self._chat_result_from_ingestion(
            result,
            source=source,
            operation="resume_pending_process",
        )
        metadata = {
            **chat_result.metadata,
            "pending_process_id": pending_context.process_ref.process_id,
            "resumed_from_pending_process_id": pending_context.process_ref.process_id,
            "resume_policy": "refresh_context_before_write",
        }
        if chat_result.pending_process is None:
            metadata["clear_pending_process"] = True
        return chat_result.model_copy(update={"metadata": metadata}, deep=True)

    def _resumed_text(
        self,
        request: ChatToolRequest,
        pending_context,
    ) -> str:
        original_text = str(
            pending_context.context.get("source_text")
            or pending_context.context.get("original_text")
            or pending_context.process_ref.metadata.get("source_text")
            or pending_context.process_ref.question
            or "",
        ).strip()
        current_answer = request.text.strip()
        return "\n\n".join(item for item in [original_text, current_answer] if item) or current_answer

    def _chat_result_from_ingestion(
        self,
        result,
        *,
        source: SourceRecordRef,
        operation: str,
    ) -> ChatToolResult:
        if result.status == IngestionStatus.NEEDS_CLARIFICATION and result.clarification:
            clarification_text = result.clarification.doubt
            clarification_summary = result.clarification.reason
            if result.clarification.options:
                clarification_summary = (
                    f"{clarification_summary} Possible interpretations: "
                    f"{result.clarification.options}"
                )
            packet = build_clarification_packet(
                frame_id=result.ingestion_id,
                origin_state_id="memory_ingestion",
                reason=result.clarification.reason,
                questions=[
                    {
                        "question": clarification_text,
                        "options": [],
                        "free_text_allowed": True,
                        "required": result.clarification.blocking,
                        "selection_mode": "single",
                    }
                ],
                compact_summary=clarification_summary,
                target_refs=result.clarification.target_refs,
            )
            return ChatToolResult(
                status=ChatResponseStatus.NEEDS_USER_INPUT,
                primary_text=clarification_text,
                pending_process=PendingProcessRef(
                    process_id=result.ingestion_id,
                    kind=PendingProcessKind.MEMORY_INGESTION,
                    question=clarification_text,
                    metadata={
                        "source_id": source.source_id,
                        "reason": result.clarification.reason,
                        "ingestion_id": result.ingestion_id,
                        "source_text": source.raw_text,
                        "resume_step": "source_reprocess",
                        "checkpoint_schema_version": "v1",
                        "clarification_packet": packet.model_dump(
                            mode="json",
                            exclude_none=True,
                        ),
                        "resume_strategy": "memory_ingestion",
                    },
                ),
                metadata={"operation": operation, "source_id": source.source_id},
                clarification_packet=packet,
            )
        if result.validation_errors:
            return ChatToolResult(
                status=ChatResponseStatus.FAILED,
                primary_text="I could not safely process this memory yet.",
                diagnostics=[
                    ChatDiagnostic(
                        level=ChatDiagnosticLevel.ERROR,
                        code=issue.code,
                        message=issue.message,
                        details=issue.details,
                    )
                    for issue in result.validation_errors
                ],
                metadata={"operation": operation, "source_id": source.source_id},
            )
        if result.status == IngestionStatus.WRITTEN:
            if not _ingestion_result_has_graph_writes(result):
                return ChatToolResult(
                    status=ChatResponseStatus.FAILED,
                    primary_text=(
                        "I could not verify that this memory was written to the graph."
                    ),
                    diagnostics=[
                        ChatDiagnostic(
                            level=ChatDiagnosticLevel.ERROR,
                            code="empty_graph_write_result",
                            message=(
                                "Ingestion returned written status without any recorded "
                                "graph mutations. Treating the result as failed to avoid "
                                "a false storage confirmation."
                            ),
                            details={
                                "ingestion_status": str(result.status),
                                "write_counts": _ingestion_write_counts(result),
                            },
                        )
                    ],
                    metadata={
                        "operation": operation,
                        "source_id": source.source_id,
                        "ingestion_id": result.ingestion_id,
                        "ingestion_status": str(result.status),
                    },
                )
            text = "I stored this memory."
        else:
            return ChatToolResult(
                status=ChatResponseStatus.FAILED,
                primary_text=(
                    "I could not store this memory yet. The ingestion pipeline stopped "
                    "before a graph write was completed."
                ),
                diagnostics=[
                    ChatDiagnostic(
                        level=ChatDiagnosticLevel.ERROR,
                        code="ingestion_not_written",
                        message=(
                            "Ingestion returned a non-written status. Check pipeline "
                            "configuration, write execution, or validation diagnostics."
                        ),
                        details={"ingestion_status": str(result.status)},
                    ),
                ],
                metadata={
                    "operation": operation,
                    "source_id": source.source_id,
                    "ingestion_id": result.ingestion_id,
                    "ingestion_status": str(result.status),
                },
            )
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text=text,
            metadata={
                "operation": operation,
                "source_id": source.source_id,
                "ingestion_id": result.ingestion_id,
                "ingestion_status": result.status,
                "clear_pending_process": operation == "resume_pending_process",
            },
        )

    @traceable(name="Memory Tool Query Context", run_type="tool")
    def query_memory_context(self, request: ChatToolRequest) -> ChatToolResult:
        if self.graph_service is None:
            return super().query_memory_context(request)

        retrieval_diagnostics: list[ChatDiagnostic] = []
        if self.semantic_search_service is not None:
            try:
                return self._query_memory_context_with_retrieval(request)
            except Exception as exc:
                retrieval_diagnostics.append(
                    ChatDiagnostic(
                        level=ChatDiagnosticLevel.ERROR,
                        code="hybrid_retrieval_failed",
                        message=(
                            "Hybrid semantic retrieval failed, so the query fell back to "
                            "exact graph-property search."
                        ),
                        details={
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                    )
                )

        return self._query_memory_context_with_property_seed(
            request,
            diagnostics=retrieval_diagnostics,
        )

    def _query_memory_context_with_retrieval(
        self,
        request: ChatToolRequest,
    ) -> ChatToolResult:
        search_result: SemanticMemorySearchResult = self.semantic_search_service.search_hybrid(
            request.text,
            label=self._str_metadata(request, "label"),
            include_archived=self._bool_metadata(request, "include_archived", default=False),
            include_history=True,
            limit=self._int_metadata(request, "limit", default=10),
            target_ids=self._target_ids_metadata(request),
        )
        if not search_result.hits:
            return ChatToolResult(
                status=ChatResponseStatus.OK,
                primary_text=(
                    "I could not find a matching memory in the graph yet. "
                    "Try naming a person, place, event, or topic more explicitly."
                ),
                diagnostics=[
                    ChatDiagnostic(
                        level=ChatDiagnosticLevel.INFO,
                        code="no_matching_graph_seed",
                        message="Hybrid graph retrieval returned no hydrated hits.",
                    )
                ],
                metadata={
                    "operation": "query_memory_context",
                    "retrieval_mode": search_result.mode,
                    "semantic_search": search_result.model_dump(
                        mode="json",
                        exclude_none=True,
                    ),
                },
            )

        hit = search_result.hits[0]
        target_id = hit.display_target_id or hit.canonical_target_id or hit.primary_target_id
        context_package = self._context_package_from_retrieval(
            search_result,
            target_id=target_id,
            request=request,
        )
        primary_text = self.answer_generator.generate_answer(
            question=request.text,
            context_package=context_package,
            conversation_id=request.conversation_id,
        )
        return ChatToolResult(
            status=ChatResponseStatus.OK,
            primary_text=primary_text,
            actions=[
                ChatAction(
                    action_type="open_graph_node",
                    label="Open memory",
                    parameters={"node_id": target_id},
                )
            ],
            evidence=self._evidence_from_context(context_package),
            metadata={
                "operation": "query_memory_context",
                "retrieval_mode": search_result.mode,
                "seed_id": target_id,
                "target": context_package.target,
                "alias_map": context_package.alias_map,
                "context_package": context_package.model_dump(mode="json"),
                "semantic_search": search_result.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
            },
        )

    def _context_package_from_retrieval(
        self,
        search_result: SemanticMemorySearchResult,
        *,
        target_id: str,
        request: ChatToolRequest,
    ) -> GraphContextPackage:
        for context_package in search_result.context_packages:
            if self._context_package_targets_id(context_package, target_id):
                return context_package
        return self.graph_service.get_context_package(
            target_id,
            include_history=True,
            timeline_limit=self._int_metadata(request, "timeline_limit", default=20),
            relationship_limit=self._int_metadata(request, "relationship_limit", default=50),
        )

    def _context_package_targets_id(
        self,
        context_package: GraphContextPackage,
        target_id: str,
    ) -> bool:
        if context_package.target.get("id") == target_id:
            return True
        alias = context_package.target.get("alias")
        if isinstance(alias, str) and context_package.alias_map.get(alias) == target_id:
            return True
        return target_id in set(context_package.alias_map.values())

    def _query_memory_context_with_property_seed(
        self,
        request: ChatToolRequest,
        *,
        diagnostics: list[ChatDiagnostic] | None = None,
    ) -> ChatToolResult:
        seed = self._resolve_seed_node(request)
        if seed is None:
            return ChatToolResult(
                status=ChatResponseStatus.OK,
                primary_text=(
                    "I could not find a matching memory in the graph yet. "
                    "Try naming a person, place, event, or topic more explicitly."
                ),
                diagnostics=[
                    ChatDiagnostic(
                        level=ChatDiagnosticLevel.INFO,
                        code="no_matching_graph_seed",
                        message="No graph seed matched the memory question.",
                    )
                ]
                + list(diagnostics or []),
                metadata={
                    "operation": "query_memory_context",
                    "retrieval_mode": "property",
                },
            )

        seed_id = str(seed.properties["id"])
        context_package = self.graph_service.get_context_package(
            seed_id,
            include_history=True,
            timeline_limit=self._int_metadata(request, "timeline_limit", default=20),
            relationship_limit=self._int_metadata(request, "relationship_limit", default=50),
        )
        primary_text = self.answer_generator.generate_answer(
            question=request.text,
            context_package=context_package,
            conversation_id=request.conversation_id,
        )
        return ChatToolResult(
            status=ChatResponseStatus.OK,
            primary_text=primary_text,
            actions=[
                ChatAction(
                    action_type="open_graph_node",
                    label="Open memory",
                    parameters={"node_id": seed_id},
                )
            ],
            evidence=self._evidence_from_context(context_package),
            diagnostics=list(diagnostics or []),
            metadata={
                "operation": "query_memory_context",
                "retrieval_mode": "property",
                "seed_id": seed_id,
                "target": context_package.target,
                "alias_map": context_package.alias_map,
                "context_package": context_package.model_dump(mode="json"),
            },
        )

    @traceable(name="Memory Tool Update Graph", run_type="tool")
    def update_memory_graph(self, request: ChatToolRequest) -> ChatToolResult:
        if self.graph_service is None:
            return super().update_memory_graph(request)
        return ChatToolResult(
            status=ChatResponseStatus.FAILED,
            primary_text=(
                "Memory graph updates require the agentic graph update state. "
                "This deterministic facade cannot infer and execute multi-step graph updates."
            ),
            diagnostics=[
                ChatDiagnostic(
                    level=ChatDiagnosticLevel.ERROR,
                    code="graph_update_requires_agentic_state",
                    message=(
                        "Use the update_memory_graph agentic tool so graph_update can "
                        "retrieve context and call deterministic write tools."
                    ),
                )
            ],
            metadata={
                "operation": "update_memory_graph",
                "source_text": request.text,
                "guidelines": request.metadata.get("guidelines"),
                "desired_work": request.metadata.get("desired_work"),
            },
        )

    def _resolve_seed_node(self, request: ChatToolRequest) -> NodeSearchResult | None:
        seed_id = request.metadata.get("seed_id") or request.metadata.get("node_id")
        if seed_id:
            try:
                return self.graph_service.get_node(str(seed_id))
            except GraphNotFoundError:
                return None

        results = self.graph_service.search_nodes(query=request.text, limit=5)
        if not results:
            return None
        return results[0]

    def _evidence_from_context(
        self,
        context_package: GraphContextPackage,
    ) -> list[ChatEvidenceRef]:
        evidence: list[ChatEvidenceRef] = []
        for item in context_package.evidence[:5]:
            evidence.append(
                ChatEvidenceRef(
                    title=item.get("title"),
                    summary=(
                        item.get("description")
                        or item.get("original_user_words")
                        or item.get("source_kind")
                    ),
                    source_id=self._first_source_id(item),
                    metadata={"alias": item.get("alias"), "label": item.get("label")},
                ),
            )
        return evidence

    def _first_source_id(self, item: dict[str, Any]) -> str | None:
        source_ids = item.get("source_ids")
        if isinstance(source_ids, list) and source_ids:
            return str(source_ids[0])
        return None

    def _node_title(self, node: NodeSearchResult) -> str:
        properties = node.properties
        return str(
            properties.get("display_name")
            or properties.get("name")
            or properties.get("title")
            or properties.get("id")
            or node.label
        )

    def _int_metadata(self, request: ChatToolRequest, key: str, *, default: int) -> int:
        value = request.metadata.get(key, default)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(1, min(parsed, 200))

    def _bool_metadata(self, request: ChatToolRequest, key: str, *, default: bool) -> bool:
        value = request.metadata.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return default

    def _str_metadata(self, request: ChatToolRequest, key: str) -> str | None:
        value = request.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
        return None

    def _target_ids_metadata(self, request: ChatToolRequest) -> list[str]:
        values: list[str] = []
        raw_target_ids = request.metadata.get("target_ids")
        if isinstance(raw_target_ids, list):
            values.extend(str(value) for value in raw_target_ids if str(value).strip())
        elif isinstance(raw_target_ids, str) and raw_target_ids.strip():
            values.extend(
                item.strip()
                for item in raw_target_ids.split(",")
                if item.strip()
            )
        for key in ("seed_id", "node_id", "target_id"):
            value = request.metadata.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
        seen: set[str] = set()
        deduped: list[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                deduped.append(value)
        return deduped

    def _source_type_for_request(self, request: ChatToolRequest) -> SourceType:
        if request.metadata.get("media_only"):
            return SourceType.AUDIO
        return SourceType.TEXT

    def _source_channel_for_request(self, request: ChatToolRequest) -> SourceChannel:
        if request.channel == "telegram":
            return SourceChannel.TELEGRAM
        return SourceChannel.API

    def _content_ref_for_request(self, request: ChatToolRequest) -> str | None:
        media_refs = request.metadata.get("media_refs")
        if not isinstance(media_refs, list) or not media_refs:
            return None
        first = media_refs[0]
        if not isinstance(first, dict):
            return None
        storage_ref = first.get("storage_ref")
        return str(storage_ref) if storage_ref else None


_WRITE_COUNT_KEYS = (
    "created_nodes",
    "updated_nodes",
    "created_claims",
    "created_perceptions",
    "created_relationship_contexts",
    "created_memory_logs",
    "metadata_patches",
    "relationships",
)


def _ingestion_result_has_graph_writes(result) -> bool:
    return sum(_ingestion_write_counts(result).values()) > 0


def _ingestion_write_counts(result) -> dict[str, int]:
    counts: dict[str, int] = {}
    metadata = getattr(result, "metadata", {}) or {}
    for key in _WRITE_COUNT_KEYS:
        value = metadata.get(key, 0)
        try:
            counts[key] = max(0, int(value))
        except (TypeError, ValueError):
            counts[key] = 0
    return counts
