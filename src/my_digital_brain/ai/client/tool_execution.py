"""Tool-call execution helpers for GenAI chat completions."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from pydantic import BaseModel

from my_digital_brain.ai.logging import log_event
from my_digital_brain.ai.models import ToolError, ToolResult, ToolSpec
from my_digital_brain.ai.tools import build_tool_mapping
from my_digital_brain.ai.tracing import traceable
from my_digital_brain.debug import record_tool_execution


NON_ERROR_TOOL_STATUSES = {"ok", "accepted", "interrupted"}


class ToolCallInterruption(Exception):
    """Raised when a tool needs user input before its tool output can be emitted."""

    def __init__(
        self,
        *,
        tool_call_id: str,
        tool_name: str,
        result: ToolResult,
        messages: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(f"Tool '{tool_name}' interrupted for user input.")
        self.tool_call_id = tool_call_id
        self.tool_name = tool_name
        self.result = result
        self.messages = messages or []


class GenAIToolExecutionMixin:
    def _tool_budget_exceeded(
        self,
        start_time: float,
        tool_calls_executed: int,
        new_calls: int,
        *,
        tool_call_limit: int | None = None,
    ) -> bool:
        resolved_limit = self.tool_call_limit if tool_call_limit is None else tool_call_limit
        if (
            resolved_limit
            and tool_calls_executed + new_calls > resolved_limit
        ):
            return True
        if self.tool_call_timeout_seconds:
            elapsed = time.monotonic() - start_time
            if elapsed > self.tool_call_timeout_seconds:
                return True
        return False

    def _call_without_tools(self, params: dict[str, Any]):
        params_no_tools = dict(params)
        params_no_tools.pop("tools", None)
        params_no_tools.pop("tool_choice", None)
        params_no_tools.pop("parallel_tool_calls", None)
        response_format = params_no_tools.get("response_format")
        if isinstance(response_format, type) and issubclass(response_format, BaseModel):
            return self._call_structured_response_with_retries(params_no_tools)
        return self._call_with_retries(params_no_tools)

    @traceable(
        name="Tool Call",
        run_type="tool"
    )
    def _execute_tool_call(
        self,
        tool_call: Any,
        *,
        tools_mapping: dict[str, Callable[..., Any]],
        tools_by_name: dict[str, ToolSpec] | None = None,
        include_tool_meta: bool = False,
        messages_snapshot: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        fn_name = tool_call.function.name
        raw_args = tool_call.function.arguments or "{}"
        meta = {
            "tool": fn_name,
            "raw_args": raw_args,
        }
        record_tool_execution(
            tool_name=fn_name,
            arguments=raw_args,
            status="started",
        )

        start = time.monotonic()
        log_event(
            self.logger,
            "tool.call.start",
            component="tool",
            step="execute_tool_call",
            tool_name=fn_name,
            status="started",
        )

        if tools_by_name is not None and fn_name not in tools_by_name:
            error = ToolError(
                message=f"Tool '{fn_name}' is not allowed for this toolbox.",
                code="tool_not_allowed",
                hint=self._allowed_tools_hint(tools_by_name),
                retryable=False,
                details={"allowed_tools": sorted(tools_by_name.keys())},
            )
            result = ToolResult(status="error", error=error, meta=meta)
            log_event(
                self.logger,
                "tool.call.error",
                "warning",
                component="tool",
                step="execute_tool_call",
                tool_name=fn_name,
                status="error",
                duration_ms=int((time.monotonic() - start) * 1000),
                error_code=error.code,
            )
            record_tool_execution(
                tool_name=fn_name,
                arguments=raw_args,
                output=result,
                status=str(result.status),
                metadata={"error_code": error.code},
            )
            return self._tool_message(
                tool_call.id,
                result,
                include_tool_meta=include_tool_meta,
            )

        if fn_name not in tools_mapping:
            error = ToolError(
                message=f"Tool '{fn_name}' not found.",
                code="tool_not_found",
                hint=self._build_tool_hint(fn_name, tools_by_name),
                retryable=False,
                details={"available_tools": sorted(tools_mapping.keys())},
            )
            result = ToolResult(status="error", error=error, meta=meta)
            log_event(
                self.logger,
                "tool.call.error",
                "warning",
                component="tool",
                step="execute_tool_call",
                tool_name=fn_name,
                status="error",
                duration_ms=int((time.monotonic() - start) * 1000),
                error_code=error.code,
            )
            record_tool_execution(
                tool_name=fn_name,
                arguments=raw_args,
                output=result,
                status=str(result.status),
                metadata={"error_code": error.code},
            )
            return self._tool_message(
                tool_call.id,
                result,
                include_tool_meta=include_tool_meta,
            )

        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError as exc:
            error = ToolError(
                message="Failed to parse tool arguments as JSON.",
                code="invalid_json",
                type=exc.__class__.__name__,
                hint=self._build_tool_hint(fn_name, tools_by_name),
                retryable=False,
                details={"raw": raw_args},
            )
            result = ToolResult(status="error", error=error, meta=meta)
            log_event(
                self.logger,
                "tool.call.error",
                "warning",
                component="tool",
                step="execute_tool_call",
                tool_name=fn_name,
                status="error",
                duration_ms=int((time.monotonic() - start) * 1000),
                error_type=exc.__class__.__name__,
                error_code=error.code,
            )
            record_tool_execution(
                tool_name=fn_name,
                arguments=raw_args,
                output=result,
                status=str(result.status),
                metadata={"error_code": error.code, "error_type": exc.__class__.__name__},
            )
            return self._tool_message(
                tool_call.id,
                result,
                include_tool_meta=include_tool_meta,
            )

        tool_fn = tools_mapping[fn_name]
        context = getattr(tool_fn, "_agentic_execution_context", None)
        previous_tool_call_id = getattr(context, "current_tool_call_id", None)
        previous_tool_name = getattr(context, "current_tool_name", None)
        previous_tool_arguments = getattr(context, "current_tool_arguments", None)
        previous_provider_messages = getattr(context, "provider_messages", None)
        if context is not None:
            context.current_tool_call_id = tool_call.id
            context.current_tool_name = fn_name
            context.current_tool_arguments = dict(args)
            context.provider_messages = list(messages_snapshot or [])
        try:
            output = tool_fn(**args)
            result = self._normalize_tool_output(output)
        except Exception as exc:  # pragma: no cover
            error = ToolError(
                message=f"Tool '{fn_name}' raised: {exc}",
                code="tool_exception",
                type=exc.__class__.__name__,
                hint="Verify required parameters and try again.",
                retryable=False,
            )
            result = ToolResult(status="error", error=error)
        finally:
            if context is not None:
                context.current_tool_call_id = previous_tool_call_id
                context.current_tool_name = previous_tool_name
                context.current_tool_arguments = previous_tool_arguments or {}
                context.provider_messages = previous_provider_messages or []

        duration_ms = int((time.monotonic() - start) * 1000)
        meta["duration_ms"] = duration_ms
        if result.meta:
            meta.update(result.meta)
        result.meta = meta
        is_expected_status = result.status in NON_ERROR_TOOL_STATUSES
        log_event(
            self.logger,
            "tool.call.end" if is_expected_status else "tool.call.error",
            "info" if is_expected_status else "warning",
            component="tool",
            step="execute_tool_call",
            tool_name=fn_name,
            status=result.status,
            duration_ms=duration_ms,
            error_type=result.error.type if result.error else None,
            error_code=result.error.code if result.error else None,
            arg_keys=sorted(args.keys()),
        )
        record_tool_execution(
            tool_name=fn_name,
            arguments=args,
            output=result,
            status=str(result.status),
            metadata={"duration_ms": duration_ms, "arg_keys": sorted(args.keys())},
        )
        if result.status == "interrupted":
            self._attach_interruption_ids(result, tool_call_id=tool_call.id, tool_name=fn_name)
            raise ToolCallInterruption(
                tool_call_id=tool_call.id,
                tool_name=fn_name,
                result=result,
            )
        return self._tool_message(
            tool_call.id,
            result,
            include_tool_meta=include_tool_meta,
        )

    def _attach_interruption_ids(
        self,
        result: ToolResult,
        *,
        tool_call_id: str,
        tool_name: str,
    ) -> None:
        if not isinstance(result.data, dict):
            result.data = {"value": result.data}
        result.data.setdefault("tool_call_id", tool_call_id)
        result.data.setdefault("tool_name", tool_name)
        packet = result.data.get("clarification_packet")
        if isinstance(packet, dict):
            packet.setdefault("tool_call_id", tool_call_id)
            packet.setdefault("tool_name", tool_name)

    def _normalize_tool_output(self, output: Any) -> ToolResult:
        if isinstance(output, ToolResult):
            return output
        if isinstance(output, BaseModel):
            return ToolResult(status="ok", data=output.model_dump(exclude_none=True))
        if isinstance(output, (dict, list)):
            return ToolResult(status="ok", data=output)
        if output is None:
            return ToolResult(status="ok", output="ok")
        return ToolResult(status="ok", output=str(output))

    def _build_tool_hint(
        self,
        tool_name: str,
        tools_by_name: dict[str, ToolSpec] | None,
    ) -> str | None:
        if not tools_by_name:
            return None
        spec = tools_by_name.get(tool_name)
        if not spec:
            return None
        params = spec.get("function", {}).get("parameters", {})
        required = params.get("required") or []
        properties = params.get("properties") or {}
        return (
            "Expected params: "
            + ", ".join(required)
            + ". Available fields: "
            + ", ".join(properties.keys())
        )

    def _allowed_tools_hint(self, tools_by_name: dict[str, ToolSpec]) -> str | None:
        if not tools_by_name:
            return None
        return "Allowed tools: " + ", ".join(sorted(tools_by_name.keys()))

    def _tool_message(
        self,
        tool_call_id: str,
        result: ToolResult,
        *,
        include_tool_meta: bool = False,
    ) -> dict[str, Any]:
        if include_tool_meta:
            payload = result.model_dump_json(exclude_none=True)
        else:
            payload = result.model_copy(update={"meta": None}).model_dump_json(
                exclude_none=True
            )
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": payload,
        }

    def _append_tool_budget_exceeded_messages(
        self,
        params: dict[str, Any],
        tool_calls: list[Any],
        *,
        tool_calls_executed: int,
        start_time: float,
        tool_call_limit: int,
    ) -> int:
        elapsed = max(0.0, time.monotonic() - start_time)
        appended = 0
        for tool_call in tool_calls:
            function = getattr(tool_call, "function", None)
            fn_name = getattr(function, "name", "unknown_tool")
            tool_call_id = getattr(tool_call, "id", None) or (
                f"tool_budget_exceeded_{tool_calls_executed + appended + 1}"
            )
            error = ToolError(
                message="Tool execution skipped because the tool budget was exceeded.",
                code="tool_budget_exceeded",
                hint="Proceed with the available context without additional tool calls.",
                retryable=False,
                details={
                    "tool": fn_name,
                    "executed_calls": tool_calls_executed,
                    "tool_call_limit": tool_call_limit,
                    "tool_call_timeout_seconds": self.tool_call_timeout_seconds,
                    "elapsed_seconds": round(elapsed, 3),
                },
            )
            result = ToolResult(
                status="error",
                error=error,
                meta={"tool": fn_name, "reason": "tool_budget_exceeded"},
            )
            params["messages"].append(
                self._tool_message(
                    tool_call_id,
                    result,
                    include_tool_meta=False,
                )
            )
            appended += 1
        return appended

    def _resolve_tool_call_limit(self, max_tool_calls: int | None) -> int:
        if max_tool_calls is None:
            return self.tool_call_limit
        try:
            return max(0, int(max_tool_calls))
        except (TypeError, ValueError):
            return self.tool_call_limit

    def _get_tool_mapping(self) -> dict[str, Callable[..., Any]]:
        if self._tool_mapping is not None:
            return self._tool_mapping
        try:
            self._tool_mapping = build_tool_mapping(
                embed_fn=self.embed,
                genai_client=self,
            )
            return self._tool_mapping
        except Exception as exc:  # pragma: no cover
            self.logger.exception("Failed to initialize tool mapping.")

            def _tool_init_failed(**_kwargs: Any) -> ToolResult:
                return ToolResult(
                    status="error",
                    error=ToolError(
                        message="Tooling backend is unavailable.",
                        code="tool_init_failed",
                        type=exc.__class__.__name__,
                        hint="Verify configured tool settings and try again.",
                        retryable=False,
                        details={"error": str(exc)},
                    ),
                )

            fallback = {
                tool_name: _tool_init_failed
                for tool_name in self.chat_toolbox.tools_by_name.keys()
            }
            self._tool_mapping = fallback
            return self._tool_mapping

    def _message_to_dict(self, message: Any) -> dict[str, Any]:
        if isinstance(message, dict):
            return message
        if hasattr(message, "model_dump"):
            try:
                payload = message.model_dump(exclude_none=True)
            except Exception:
                payload = None
            if isinstance(payload, dict):
                return payload
        return {
            "role": getattr(message, "role", "assistant"),
            "content": getattr(message, "content", None),
            "tool_calls": self._tool_calls_to_dict(
                getattr(message, "tool_calls", None)
            ),
        }

    def _tool_calls_to_dict(self, tool_calls: Any) -> Any:
        if not isinstance(tool_calls, list):
            return tool_calls
        serialized: list[dict[str, Any]] = []
        for call in tool_calls:
            if isinstance(call, dict):
                serialized.append(call)
                continue
            function = getattr(call, "function", None)
            serialized.append(
                {
                    "id": getattr(call, "id", None),
                    "type": getattr(call, "type", "function"),
                    "function": {
                        "name": getattr(function, "name", None),
                        "arguments": getattr(function, "arguments", None),
                    },
                }
            )
        return serialized
