"""Execute and complete one provider-issued tool-call batch."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from typing import Any

from pydantic import BaseModel

from product.ai.ai_clients.protocols.protocol_chat import Msg, ToolCalled
from product.ai.ai_clients.protocols.protocol_tools import (
    ToolCallBatchItemDTO,
    ToolCallBatchPauseDTO,
    ToolCallContextDTO,
    ToolCallResultDTO,
    ToolErrorDTO,
    ToolInteractionRequestDTO,
    ToolOutputDTO,
)
from product.ai.tracing import get_trace_parent_headers, tracing_context


class ToolCallBatchRuntime:
    """Map each provider call to one result, including failures and pauses.

    Provider routing, transcript sequencing, budget checks, and the next
    provider request remain responsibilities of `LLMInterfaceCore`.
    """

    def __init__(
        self,
        *,
        log: Callable[[str, str], None],
        clamp_for_model: Callable[[str, str | None], str],
    ) -> None:
        self._log = log
        self._clamp_for_model = clamp_for_model

    def execute_batch(
        self,
        tool_calls: Sequence[ToolCalled],
        tools_mapping: Mapping[str, Callable[..., Any]],
        *,
        tools_enabled: bool,
        state: dict[str, Any],
    ) -> list[ToolCallBatchItemDTO[BaseModel]] | ToolCallBatchPauseDTO[BaseModel]:
        """Execute a provider turn's calls and preserve provider order.

        Mapped functions run concurrently when the provider returned multiple
        executable calls. Every ordinary failure becomes that call's error
        output. External-input requests pause the complete batch instead.
        """
        completed_results: dict[str, ToolOutputDTO | ToolInteractionRequestDTO] = {}
        executable_calls: list[tuple[ToolCalled, Callable[..., Any], dict[str, Any]]] = []

        for tool_call in tool_calls:
            call_id = tool_call.id
            tool_name = tool_call.function.name
            if state["tool_calls_processed"] >= state["tool_call_cap"]:
                completed_results[call_id] = self._tool_error_output(
                    code="tool_call_cap_reached",
                    message=(
                        f"The configured tool-call limit ({state['tool_call_cap']}) was reached; "
                        f"'{tool_name}' was not executed. Continue with the available results and answer."
                    ),
                )
                continue

            state["tool_calls_processed"] += 1
            if not tools_enabled:
                completed_results[call_id] = self._tool_error_output(
                    code="toolbox_unavailable",
                    message=f"Tool '{tool_name}' was not executed because no toolbox is available.",
                )
                continue

            try:
                raw_arguments = tool_call.function.arguments
                arguments = (
                    json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
                )
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be a JSON object.")
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                completed_results[call_id] = self._tool_error_output(
                    code="invalid_tool_arguments",
                    message=f"Tool '{tool_name}' received invalid arguments: {error}",
                    hint="Return the tool arguments as a valid JSON object and continue.",
                )
                continue

            handler = tools_mapping.get(tool_name)
            if not callable(handler):
                completed_results[call_id] = self._tool_error_output(
                    code="tool_handler_unavailable",
                    message=f"No backend handler is registered for tool '{tool_name}'.",
                )
                continue
            executable_calls.append((tool_call, handler, arguments))

        self._execute_mapped_calls(executable_calls, completed_results)

        batch_items: list[ToolCallBatchItemDTO[BaseModel]] = []
        for tool_call in tool_calls:
            call_id = tool_call.id
            tool_name = tool_call.function.name
            result = completed_results.get(call_id)
            if not isinstance(result, (ToolOutputDTO, ToolInteractionRequestDTO)):
                result = self._tool_error_output(
                    code="tool_result_missing",
                    message=(
                        f"Tool '{tool_name}' did not produce a result because an internal "
                        "batch-processing step failed. Continue with this error and the other results."
                    ),
                    hint="Use this error result and continue the interaction.",
                )

            if isinstance(result, ToolInteractionRequestDTO):
                batch_items.append(
                    ToolCallBatchItemDTO[BaseModel](
                        provider_call_id=call_id,
                        tool_name=tool_name,
                        interaction_request=result,
                    )
                )
                continue

            if result.status == "error":
                self._log(
                    f"[llm_interface_core.tools_handle] "
                    f"{result.error.message if result.error else 'Tool returned an error status.'}",
                    "warning",
                )
            normalized, _serialized = self._serialize_tool_output(tool_name, result)
            batch_items.append(
                ToolCallBatchItemDTO[BaseModel](
                    provider_call_id=call_id,
                    tool_name=tool_name,
                    tool_output=normalized,
                )
            )

        if any(item.interaction_request is not None for item in batch_items):
            return ToolCallBatchPauseDTO[BaseModel](
                calls=batch_items,
                tool_calls_processed=state["tool_calls_processed"],
                tool_call_cap=state["tool_call_cap"],
                seen_call_ids=list(state["seen_call_ids"]),
            )
        return batch_items

    def complete_paused_batch(
        self,
        paused_batch: ToolCallBatchPauseDTO[BaseModel],
        tool_results: Sequence[ToolCallResultDTO],
    ) -> list[ToolCallBatchItemDTO[BaseModel]] | ToolCallBatchPauseDTO[BaseModel]:
        """Match external outputs by provider call ID and retain unanswered calls."""
        pending_ids = {
            call.provider_call_id
            for call in paused_batch.calls
            if call.interaction_request is not None
        }
        results_by_id: dict[str, ToolCallResultDTO] = {}
        for result in tool_results:
            call_id = result.provider_call_id
            if call_id not in pending_ids:
                self._log(
                    f"[llm_interface_core.resume_tool_batch] Ignoring output for unknown call ID {call_id}.",
                    "warning",
                )
                continue
            if call_id in results_by_id:
                self._log(
                    f"[llm_interface_core.resume_tool_batch] Ignoring duplicate output for call ID {call_id}.",
                    "warning",
                )
                continue
            results_by_id[call_id] = result

        resumed_calls: list[ToolCallBatchItemDTO[BaseModel]] = []
        for call in paused_batch.calls:
            result = results_by_id.get(call.provider_call_id)
            if call.interaction_request is not None and result is not None:
                resumed_calls.append(
                    ToolCallBatchItemDTO[BaseModel](
                        provider_call_id=call.provider_call_id,
                        tool_name=call.tool_name,
                        tool_output=result.tool_output,
                    )
                )
            else:
                resumed_calls.append(call)

        if any(call.interaction_request is not None for call in resumed_calls):
            return ToolCallBatchPauseDTO[BaseModel](
                calls=resumed_calls,
                tool_calls_processed=paused_batch.tool_calls_processed,
                tool_call_cap=paused_batch.tool_call_cap,
                seen_call_ids=list(paused_batch.seen_call_ids),
            )
        return resumed_calls

    def build_tool_messages(
        self,
        calls: Sequence[ToolCallBatchItemDTO[BaseModel]],
        model_name: str | None,
    ) -> list[Msg]:
        """Build the complete ordered provider message batch before appending it."""
        return [
            self._tool_result_message(
                call.provider_call_id,
                call.tool_name,
                call.tool_output,
                model_name,
            )
            for call in calls
        ]

    def _execute_mapped_calls(
        self,
        executable_calls: list[tuple[ToolCalled, Callable[..., Any], dict[str, Any]]],
        completed_results: dict[str, ToolOutputDTO | ToolInteractionRequestDTO],
    ) -> None:
        """Run mapped calls and fill one success/error result slot per call ID."""
        if len(executable_calls) == 1:
            tool_call, handler, arguments = executable_calls[0]
            completed_results[tool_call.id] = self._execute_mapped_tool(
                ToolCallContextDTO(
                    provider_call_id=tool_call.id,
                    tool_name=tool_call.function.name,
                ),
                handler,
                arguments,
            )
            return
        if not executable_calls:
            return

        try:
            with ThreadPoolExecutor(max_workers=len(executable_calls)) as executor:
                future_to_call = {}
                for tool_call, handler, arguments in executable_calls:
                    context = copy_context()
                    future = executor.submit(
                        context.run,
                        self._execute_mapped_tool,
                        ToolCallContextDTO(
                            provider_call_id=tool_call.id,
                            tool_name=tool_call.function.name,
                        ),
                        handler,
                        arguments,
                    )
                    future_to_call[future] = tool_call

                for future in as_completed(future_to_call):
                    tool_call = future_to_call[future]
                    try:
                        completed_results[tool_call.id] = future.result()
                    except Exception as error:
                        completed_results[tool_call.id] = self._tool_error_output(
                            code="tool_execution_failed",
                            message=(
                                f"Tool '{tool_call.function.name}' failed with "
                                f"{type(error).__name__}: {error}. Continue with the other results."
                            ),
                            hint="Use this error to correct the call or choose another action.",
                        )
        except Exception as error:
            for tool_call, _handler, _arguments in executable_calls:
                completed_results.setdefault(
                    tool_call.id,
                    self._tool_error_output(
                        code="tool_execution_failed",
                        message=(
                            f"Tool '{tool_call.function.name}' could not run because the parallel "
                            f"tool executor failed with {type(error).__name__}: {error}."
                        ),
                        hint="Continue with the error result and retry another approach if needed.",
                    ),
                )

    def _execute_mapped_tool(
        self,
        call_context: ToolCallContextDTO,
        handler: Callable[..., Any],
        arguments: dict[str, Any],
    ) -> ToolOutputDTO | ToolInteractionRequestDTO:
        """Run one mapped handler with provider identity when the handler accepts it."""
        tool_name = call_context.tool_name
        try:
            with tracing_context(parent=get_trace_parent_headers()):
                contextual_invoke = getattr(handler, "invoke_for_tool_call", None)
                result = (
                    contextual_invoke(call_context, **arguments)
                    if callable(contextual_invoke)
                    else handler(**arguments)
                )
            if isinstance(result, ToolInteractionRequestDTO):
                return result
            output = self._normalize_tool_output(result)
            callable_name = getattr(getattr(handler, "func", handler), "__name__", tool_name)
            self._log(f"[llm_interface_core.tools_handle] Tool {callable_name} executed.", "debug")
            return output
        except Exception as error:
            return self._tool_error_output(
                code="tool_execution_failed",
                message=(
                    f"Tool '{tool_name}' failed with {type(error).__name__}: {error}. "
                    "Review the error, adjust the input or approach, and continue."
                ),
                hint="Use this error to correct the tool call or choose another action.",
            )

    def _tool_result_message(
        self,
        provider_call_id: str,
        tool_name: str,
        tool_output: ToolOutputDTO | None,
        model_name: str | None,
    ) -> Msg:
        """Build one correlated tool message, falling back to a compact error."""
        if tool_output is None:
            tool_output = self._tool_error_output(
                code="tool_output_missing",
                message=(
                    f"Tool '{tool_name}' completed without an output. "
                    "Continue with this error and the other batch results."
                ),
            )
        try:
            _normalized, serialized = self._serialize_tool_output(tool_name, tool_output)
            content = self._clamp_for_model(serialized, model_name)
        except Exception as error:
            fallback = self._tool_error_output(
                code="tool_output_preparation_failed",
                message=f"Tool '{tool_name}' output preparation failed: {type(error).__name__}.",
            )
            try:
                _normalized, content = self._serialize_tool_output(tool_name, fallback)
            except Exception:
                content = (
                    '{"status":"error","error":{"code":"tool_output_preparation_failed",'
                    '"message":"Tool output preparation failed; continue with other batch results."}}'
                )
        return Msg(role="tool", content=content, meta={"tool_call_id": provider_call_id})

    @staticmethod
    def _serialize_tool_output(
        tool_name: str, tool_output: ToolOutputDTO
    ) -> tuple[ToolOutputDTO, str]:
        """Serialize a tool result or replace it with a serializable error DTO."""
        try:
            return tool_output, tool_output.model_dump_json(exclude_none=True)
        except Exception as error:
            fallback = ToolCallBatchRuntime._tool_error_output(
                code="tool_output_serialization_failed",
                message=(
                    f"Tool '{tool_name}' returned a result that could not be serialized: "
                    f"{type(error).__name__}: {error}"
                ),
                hint="Return JSON-compatible tool result data and continue.",
            )
            return fallback, fallback.model_dump_json(exclude_none=True)

    @staticmethod
    def _tool_error_output(
        *, code: str, message: str, hint: str | None = None
    ) -> ToolOutputDTO:
        """Create the one normalized error shape sent for a failed tool call."""
        return ToolOutputDTO(
            status="error",
            error=ToolErrorDTO(code=code, message=message, hint=hint),
        )

    @staticmethod
    def _normalize_tool_output(result: Any) -> ToolOutputDTO:
        """Normalize a handler result without a serialize/parse round trip."""
        if isinstance(result, ToolOutputDTO):
            return result
        if isinstance(result, BaseModel):
            result = result.model_dump(mode="json")
        if not isinstance(result, dict):
            result = {"result": result}
        return ToolOutputDTO(status="ok", data=result)
