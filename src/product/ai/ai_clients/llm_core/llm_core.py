# boris/boriscore/ai_clients/llm_core/llm_core.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from collections.abc import Mapping
from pydantic import BaseModel


from product.ai.ai_clients.providers.base import Provider
from product.ai.ai_clients.protocols.protocol_chat import (
    Msg,
    ChatRequest,
    ToolSpec,
    coerce_toolspecs,
    ToolCalled,
    ChatResponse,
)
from product.ai.ai_clients.llm_core.llm_helpers import LLMInterfaceHelpers
from product.ai.ai_clients.llm_core.llm_base import LLMInterfaceBase
from product.ai.ai_clients.llm_core.tool_call_batch import ToolCallBatchRuntime

from product.ai.ai_clients.protocols.protocol_tools import (
    ToolDefinitionDTO,
    ToolCallBatchPauseDTO,
    ToolCallResultDTO,
)
from product.ai.tracing import (
    traceable,
    set_trace_metadata,
    get_trace_parent_headers,
    tracing_context,
)

log_name_main = "llm_interface_core"


class LLMInterfaceCore(LLMInterfaceHelpers, LLMInterfaceBase):
    """
    Provider-agnostic public API surface built on Base + Helpers.

    What this layer does
    --------------------
    • Exposes `handle_params()` to build a normalized `ChatRequest`.
    • Exposes `call()` to route by task kind (chat/coding/reasoning/embedding), dispatch to
      the correct provider adapter, and (optionally) run a guarded tool-calling loop.
    • Exposes `handle_tool_calling()` to execute tools safely and bounce back to `call()`.

    What this layer does NOT do
    ---------------------------
    • It does NOT read/merge environment variables or create SDK clients (Base handles that).
    • It does NOT own token/accounting primitives (Helpers handles that).

    MRO & lifecycle
    ---------------
    Core.__init__ → Helpers.__init__ → Base.__init__.
    - Base: merges envs, resolves routing, builds adapter cache, bootstraps a default adapter,
      sets `base_encoder`.
    - Helpers: applies/initializes helper knobs and runtime caps.
    - Core: thin pass-through; no heavy work in __init__.

    Parameters
    ----------
    logger : Optional[logging.Logger]
        Logger for all layers.
    base_path : Path
        Root folder used by Base to locate `.env`.
    max_tokens_per_message_ratio : Optional[float]
        Tool-result token cap ratio; forwarded to Helpers.
    provider : Provider
        Optional initial provider; final resolution still follows routing rules.

    Primary methods
    ---------------
    handle_params(...) -> ChatRequest
        Normalize messages/tools/params and enforce budget pre-flight.
    call(req, tools_mapping, ...) -> ChatResponse | ToolCallBatchPauseDTO
        Route to the provider, run the tool loop, or return a whole batch awaiting external input.
    handle_tool_calling(req, tool_calls, tools_mapping, _state=...) -> ChatResponse | ToolCallBatchPauseDTO
        Complete a full provider batch or return it paused for external input, then resume the provider.

    Notes
    -----
    - On Azure, `model` is the deployment name.
    - Env priority: BORIS_* > legacy AZURE_* or OPENAI_* keys.
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        base_path: Path = Path("."),
        max_tokens_per_message_ratio: Optional[float] = None,
        provider: Provider = None,
        *args,
        **kwargs,
    ) -> None:

        logger.name = "[llmCore]"
        # Single pass through the MRO; Helpers will forward to Base.
        super().__init__(
            logger=logger,
            base_path=base_path,
            provider=provider,
            max_tokens_per_message_ratio=max_tokens_per_message_ratio,
            *args,
            **kwargs,
        )
        self._tool_call_batch_runtime = ToolCallBatchRuntime(
            log=self._log,
            clamp_for_model=self._clamp_for_model,
        )
        self._log(
            f"[{log_name_main}.core.init] core ready (base_path={self.base_path}, provider={self.provider})",
            "debug",
        )

    @traceable(name="llm_core.handle_params", run_type="prompt")
    def handle_params(
        self,
        system_prompt: str,
        chat_messages: Union[str, List[dict], dict],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
        top_p: Optional[float] = None,
        n: Optional[int] = None,
        stop: Optional[List[str]] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        response_format: Optional[Any] = None,
        tools: Optional[List[dict | ToolDefinitionDTO]] = None,
        user: Optional[str] = None,
        parallel_tool_calls: Optional[bool] = None,
        reasoning_effort: Optional[str] = None,
        # provider-specific passthroughs
        service_tier: Optional[str] = None,
        tool_choice: Optional[Union[str, dict]] = None,
        thinking: Optional[dict] = None,
        metadata: Optional[dict] = None,
        stream: Optional[bool] = None,
        *,
        model_kind: Optional[str] = None,
    ) -> ChatRequest:

        self._log(
            f"[{log_name_main}.handle_params] Handling params…",
            "debug",
        )
        self._ensure_runtime_caps()

        kind = (model_kind or "chat").lower()

        # Ensure correct adapter for this task kind (respects routing)
        self._ensure_adapter_for_kind(kind)

        # Resolve the concrete model under that provider
        resolved_model = self._resolve_model(explicit=model, model_kind=kind)
        self._log(
            f"[{log_name_main}.handle_params] Resolved Model: {resolved_model}.",
            "debug",
        )
        # Normalize messages
        messages = self._normalize_messages(system_prompt, chat_messages)

        # Normalize tools → ToolSpec[]
        norm_tools: Optional[List[ToolSpec]] = coerce_toolspecs(tools) if tools else None

        # Gather scalar params (trim Nones)
        params: Dict[str, Any] = {}
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if temperature is not None:
            params["temperature"] = temperature
        if top_p is not None:
            params["top_p"] = top_p
        if n is not None:
            params["n"] = n
        if stop is not None:
            params["stop"] = stop
        if presence_penalty is not None:
            params["presence_penalty"] = presence_penalty
        if frequency_penalty is not None:
            params["frequency_penalty"] = frequency_penalty
        if user is not None:
            params["user"] = user
        if reasoning_effort is not None:
            params["reasoning_effort"] = reasoning_effort
        if response_format is not None:
            params["response_format"] = response_format
        if service_tier is not None:
            params["service_tier"] = service_tier
        if tool_choice is not None:
            params["tool_choice"] = tool_choice
        if thinking is not None:
            params["thinking"] = thinking
        if metadata is not None:
            params["metadata"] = metadata
        if stream is not None:
            params["stream"] = stream
        params["model_kind"] = kind

        # Only include parallel tool calls if tools are present
        if norm_tools and parallel_tool_calls is not None:
            params["parallel_tool_calls"] = parallel_tool_calls
            self._log(
                f"[{log_name_main}.handle_params] With parallel_tool_calls {parallel_tool_calls}.",
                "debug",
            )
        # Reasoning models often ignore temperature; preserve your existing rule
        if (
            kind == "reasoning"
            and self._resolve_model_for_kind(kind="reasoning") == resolved_model
            and "temperature" in params
        ):
            del params["temperature"]

        # Assemble request
        req = ChatRequest(
            model=resolved_model,
            messages=messages,
            tools=norm_tools,
            params=params,
        )

        # Budget preflight
        self._ensure_context_budget_norm(req)
        if self._disable_tools_if_low_budget_norm(req):
            self._ensure_context_budget_norm(req)

        # Logging
        self._log(
            "[{}.handle_params] Req ready: model={} tools={} resp_format={} messages={} max_tokens={} temperature={}".format(
                log_name_main,
                req.model,
                "yes" if req.tools else "no",
                "yes" if "response_format" in req.params else "no",
                len(req.messages),
                req.params.get("max_tokens", "auto"),
                req.params.get("temperature", "default"),
            ),
            "debug",
        )

        return req

    @traceable(name="llm_core.call", run_type="chain")
    def call(
        self,
        req: ChatRequest,
        tools_mapping: Optional[Mapping[str, Callable[..., Any]]] = None,
        *,
        max_tool_calls: Optional[int] = None,
        _state: Optional[dict] = None,
    ) -> ChatResponse | ToolCallBatchPauseDTO[BaseModel]:
        """Call the routed adapter and resume this method after mapped tool outputs.

        Depends on provider/model routing and the adapter's `chat` method; tool
        turns delegate to `handle_tool_calling`. It returns a final provider
        response or a complete batch continuation when external input is needed.
        """
        kind = (req.params.get("model_kind") if req.params else None) or "chat"
        provider_for_turn = self._resolve_provider_for_kind(kind)
        model_for_turn = self._resolve_model_for_kind(kind)

        # Stamp provider/model if missing (telemetry/adapter expectations)
        if req.params is not None:
            if "provider" not in req.params:
                req.params["provider"] = provider_for_turn
            if model_for_turn and "model" not in req.params:
                req.params["model"] = model_for_turn

        self._log(
            f"[{log_name_main}.call] Turn routing: kind={kind} → provider={provider_for_turn} model={model_for_turn}",
            "debug",
        )

        set_trace_metadata(
            model_kind=kind,
            provider=provider_for_turn,
            model=model_for_turn,
            session_id=(req.params or {}).get("session_id") or (req.params or {}).get("user"),
            user_id=(req.params or {}).get("user"),
        )

        # Initialize runtime guards and budget
        self._ensure_runtime_caps()
        self._ensure_context_budget_norm(req)

        # Initialize _state once
        if _state is None:
            _state = dict(
                tool_calls_processed=0,
                tool_call_cap=(
                    max_tool_calls if max_tool_calls is not None else self.tool_call_cap
                ),
                seen_call_ids=set(),
            )

        # Provider call using the routed adapter
        adapter = self._get_adapter_for_provider(provider_for_turn)
        parent_headers = get_trace_parent_headers()
        with tracing_context(parent=parent_headers):
            resp: ChatResponse = adapter.chat(req)

        if not getattr(resp, "tool_calls", None):
            self._log(f"[{log_name_main}.call] No tools requested.", "debug")
            return resp

        self._log(
            f"[{log_name_main}.call] Model requested {len(resp.tool_calls)} tool call(s): {','.join([tool.function.name for tool in resp.tool_calls])}",
            "info",
        )
        return self.handle_tool_calling(req, resp.tool_calls, tools_mapping or {}, _state=_state)

    @traceable(name="llm_core.handle_tool_calling", run_type="tool")
    def handle_tool_calling(
        self,
        req: ChatRequest,
        tool_calls: List[ToolCalled],
        tools_mapping: Mapping[str, Callable[..., Any]],
        *,
        _state: dict,
    ) -> ChatResponse | ToolCallBatchPauseDTO[BaseModel]:
        """Execute one provider tool batch, then resume only when it is complete.

        Depends on `ToolCallBatchRuntime` for mapped execution, per-call error
        outputs, and call-ID correlation. This method owns the assistant tool
        turn, transcript append, budget check, and next provider call. A batch
        requesting external input returns to the state without a partial
        provider request.
        """
        self._log(f"[{log_name_main}.tools_handle] Tooling...", "debug")
        model_name = req.model

        unique_tool_calls: list[ToolCalled] = []
        seen_call_ids: set[str] = _state.setdefault("seen_call_ids", set())
        for tool_call in tool_calls:
            if tool_call.id in seen_call_ids:
                self._log(
                    f"[{log_name_main}.tools_handle] Skipping provider call ID already seen in this session: {tool_call.id}.",
                    "warning",
                )
                continue
            seen_call_ids.add(tool_call.id)
            unique_tool_calls.append(tool_call)

        if not unique_tool_calls:
            self._log(
                f"[{log_name_main}.tools_handle] No unseen tool calls; resuming provider with the existing transcript.",
                "info",
            )
            return self.call(
                req,
                tools_mapping,
                max_tool_calls=_state["tool_call_cap"],
                _state=_state,
            )

        # Echo assistant with tool_calls payload (provider-agnostic shape)
        tc_payload = [
            {
                "id": tc.id,
                "type": "function",
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            }
            for tc in unique_tool_calls
        ]
        req.messages.append(Msg(role="assistant", content=None, meta={"tool_calls": tc_payload}))

        batch_result = self._tool_call_batch_runtime.execute_batch(
            unique_tool_calls,
            tools_mapping,
            tools_enabled=bool(req.tools),
            state=_state,
        )
        if isinstance(batch_result, ToolCallBatchPauseDTO):
            return batch_result

        req.messages.extend(
            self._tool_call_batch_runtime.build_tool_messages(batch_result, model_name)
        )

        if _state["tool_calls_processed"] >= _state["tool_call_cap"]:
            req.tools = None
            req.params.pop("parallel_tool_calls", None)

        # Post-tools: enforce budget; disable tools if tight
        self._ensure_context_budget_norm(req)
        if self._disable_tools_if_low_budget_norm(req):
            req.tools = None
            req.params.pop("parallel_tool_calls", None)
            req.messages.append(
                Msg(
                    role="assistant",
                    content="Tooling disabled due to limited remaining context. Please answer the user directly.",
                )
            )
            self._ensure_context_budget_norm(req)

        self._log(
            f"[{log_name_main}.tools_handle] Re-calling provider after tool outputs (processed {_state['tool_calls_processed']}).",
            "debug",
        )
        return self.call(req, tools_mapping, max_tool_calls=_state["tool_call_cap"], _state=_state)

    @traceable(name="llm_core.resume_tool_batch", run_type="chain")
    def resume_tool_batch(
        self,
        req: ChatRequest,
        paused_batch: ToolCallBatchPauseDTO[BaseModel],
        tool_results: list[ToolCallResultDTO],
        tools_mapping: Mapping[str, Callable[..., Any]],
    ) -> ChatResponse | ToolCallBatchPauseDTO[BaseModel]:
        """Complete an interrupted provider batch and make one next call when whole.

        Depends on `ToolCallBatchRuntime.complete_paused_batch` to correlate
        external outputs and preserve unanswered calls. This method appends
        outputs only when the full batch is complete, then resumes the provider
        loop once.
        """
        batch_result = self._tool_call_batch_runtime.complete_paused_batch(
            paused_batch,
            tool_results,
        )
        if isinstance(batch_result, ToolCallBatchPauseDTO):
            return batch_result

        req.messages.extend(
            self._tool_call_batch_runtime.build_tool_messages(batch_result, req.model)
        )

        resumed_state = {
            "tool_calls_processed": paused_batch.tool_calls_processed,
            "tool_call_cap": paused_batch.tool_call_cap,
            "seen_call_ids": set(paused_batch.seen_call_ids),
        }
        if resumed_state["tool_calls_processed"] >= resumed_state["tool_call_cap"]:
            req.tools = None
            req.params.pop("parallel_tool_calls", None)
        return self.call(
            req,
            tools_mapping,
            max_tool_calls=resumed_state["tool_call_cap"],
            _state=resumed_state,
        )
