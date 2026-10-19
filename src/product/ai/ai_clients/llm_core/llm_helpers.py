# boris/boriscore/ai_clients/client_oai.py
from __future__ import annotations

import json
import logging
from pathlib import Path

try:  # pragma: no cover
    import tiktoken  # type: ignore
    from tiktoken import Encoding
except Exception:  # pragma: no cover
    tiktoken = None  # we will fall back to a 4 chars ≈ 1 token heuristic
from typing import Union, List, Optional, Dict, Any, Sequence

from product.ai.ai_clients.providers.base import Provider
from product.ai.ai_clients.protocols.protocol_chat import (
    Msg,
    ChatRequest,
    msg_text,
    msg_from_loose,
)
from product.ai.ai_clients.llm_core.llm_base import LLMInterfaceBase
from product.ai.ai_clients.utils.utils import _env


# -------------------------------------------------------------------
# Default model → max context limits (tokens). Override in your app.
# You can update this safely without touching the patch itself.
DEFAULT_MODEL_CONTEXT: Dict[str, int] = {
    # OpenAI o-series / 4.x (adjust as needed for your estate)
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4.1": 1_000_000,
    "gpt-4.1-mini": 1_000_000,
    "o3": 200_000,
    "o4-mini": 200_000,
}


# Keep some output budget so the call doesn't fail after truncation
DEFAULT_OUTPUT_RESERVE = 1_024  # tokens to leave for completion


# Tooling guard knobs (can be tweaked per instance)
DEFAULT_TOOL_CALL_CAP = 20  # max provider tool calls executed per turn
DEFAULT_TOOL_MESSAGE_TOKEN_RATIO = 0.20  # tool output cap as % of model context (20%)
DEFAULT_TOOL_DISABLE_MARGIN_TOKENS = 3_500  # if remaining context < margin, disable tools

log_name_main = "llm_interface_helpers"


class LLMInterfaceHelpers(LLMInterfaceBase):
    """
    Token, budget, and protocol utilities layered on top of `LLMInterfaceBase`.

    What this layer does
    --------------------
    • Configures helper knobs (tool output cap ratio, output reserve, call cap).
    • Initializes per-turn tool loop state via `_ensure_runtime_caps()`.
    • Provides shared helpers used by the core API (token counting, truncation, and budgeting).

    What this layer does NOT do
    ---------------------------
    • It does NOT read/merge .env files.
    • It does NOT select providers/models or create SDK clients.
    • It does NOT call provider APIs.

    MRO & lifecycle
    ---------------
    `LLMInterfaceCore(LLMInterfaceHelpers, LLMInterfaceBase)` means:
    Core.__init__ → Helpers.__init__ → Base.__init__.
    The heavy lifting (env/adapters) is handled in Base.__init__. Helpers only sets
    helper-level configuration and runtime state.

    Parameters
    ----------
    logger : Optional[logging.Logger]
        Logger used by all layers (plumbed down to Base).
    base_path : Path
        Project root, used by Base to locate `.env`.
    max_tokens_per_message_ratio : Optional[float]
        Upper bound ratio for tool-result message tokens vs model context. Defaults
        to DEFAULT_TOOL_MESSAGE_TOKEN_RATIO. If None, the Base/Helpers default is kept.
    provider : Provider
        Optional initial provider hint; Base will validate/route.

    Attributes set by Base (available after super().__init__)
    --------------------------------------------------------
    logger, base_path, provider
    route_by_task, models_by_provider
    _adapters_cache, _provider_adapter, cfg
    base_encoder

    Attributes set/ensured by Helpers
    ---------------------------------
    tool_message_token_ratio : float
    output_reserve_tokens : int
    tool_disable_margin_tokens : int
    tool_call_cap : int
    azure_deployment_to_base : dict
    model_context_overrides : dict

    Notes
    -----
    - Changing helper knobs at runtime is supported; call `_ensure_runtime_caps()` to
      restore configured defaults when needed.
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        base_path: Path = Path("."),
        max_tokens_per_message_ratio: Optional[float] = DEFAULT_TOOL_MESSAGE_TOKEN_RATIO,
        provider: Provider = None,
        *args,
        **kwargs,
    ) -> None:
        logger.name = "[llmHelpers]"
        # Defer env/adapters to Base
        super().__init__(
            logger=logger,
            base_path=base_path,
            provider=provider,
            *args,
            **kwargs,
        )

        # Helper-level knobs (safe to set/override here)
        if max_tokens_per_message_ratio is not None:
            self.tool_message_token_ratio = float(max_tokens_per_message_ratio)
        elif not hasattr(self, "tool_message_token_ratio"):
            self.tool_message_token_ratio = DEFAULT_TOOL_MESSAGE_TOKEN_RATIO

        if not hasattr(self, "output_reserve_tokens"):
            self.output_reserve_tokens = DEFAULT_OUTPUT_RESERVE

        # Initialize/ensure runtime caps and per-turn tool state
        self._ensure_runtime_caps()

        # Optional: light debug trace
        self._log(
            f"[{log_name_main}.helpers.init] helpers ready (ratio={self.tool_message_token_ratio}, "
            f"reserve={self.output_reserve_tokens})",
            "debug",
        )

    def _ensure_runtime_caps(self) -> None:  #
        # Instance-level knobs with sensible defaults
        if not hasattr(self, "tool_disable_margin_tokens"):
            self.tool_disable_margin_tokens = DEFAULT_TOOL_DISABLE_MARGIN_TOKENS
        if not hasattr(self, "tool_call_cap"):
            self.tool_call_cap = DEFAULT_TOOL_CALL_CAP
        if not hasattr(self, "tool_message_token_ratio"):
            self.tool_message_token_ratio = DEFAULT_TOOL_MESSAGE_TOKEN_RATIO
        if not hasattr(self, "output_reserve_tokens"):
            self.output_reserve_tokens = DEFAULT_OUTPUT_RESERVE

        # Optional Azure deployment → base model mapping
        if not hasattr(self, "azure_deployment_to_base") or self.azure_deployment_to_base is None:
            mapping_env = _env("BORIS_AZURE_DEPLOY_MAP")
            try:
                self.azure_deployment_to_base = json.loads(mapping_env) if mapping_env else {}
            except Exception:
                self.azure_deployment_to_base = {}

        # Allow external override of model contexts
        if not hasattr(self, "model_context_overrides") or self.model_context_overrides is None:
            self.model_context_overrides = {}

    def _context_limit_for_model(self, model: str) -> int:  #
        """Best‑effort: user overrides → attempt API probe → fall back to map → default.

        We *don’t* rely on a specific documented field here because availability differs
        across providers and dates. You can override per instance via
        `self.model_context_overrides[<model or base>] = <int>`.
        """
        base = self._encoding_for_model()
        # 1) explicit override wins
        if base in self.model_context_overrides:
            return int(self.model_context_overrides[base])
        if model in self.model_context_overrides:
            return int(self.model_context_overrides[model])

        # 2) try an API probe (OpenAI) when available – ignore failures quietly
        try:  # pragma: no cover
            # return self._provider_adapter._get_token_context_for_model(model=base)
            pass
        except Exception:
            self._log(
                f"[{log_name_main}.context_limit] Failed to retrieve context window for {base}",
                "error",
            )
            pass

        # 3) fall back to static map (check both base and model names)
        if base in DEFAULT_MODEL_CONTEXT:
            return DEFAULT_MODEL_CONTEXT[base]
        if model in DEFAULT_MODEL_CONTEXT:
            return DEFAULT_MODEL_CONTEXT[model]

        # 4) last resort: a safe default (8k)
        return 128_000

    def _encoding_for_model(self, encoding_model: Optional[str] = "cl100k_base"):  #
        """Pick a tiktoken encoding for a base model; default to cl100k_base.

        We don’t attempt to perfectly mirror per‑model chat packing; this is a
        robust *upper‑bound estimator* suitable for pre‑flight truncation.
        """
        if tiktoken is None:
            return None
        try:
            return tiktoken.get_encoding(encoding_model)  # type: ignore[attr-defined]
        except Exception:
            return tiktoken.get_encoding("cl100k_base")

    def _count_tokens_text(self, text: str, encoding: Optional[Encoding] = None) -> int:  #
        if not text:
            return 0
        # Prefer provided encoding; else try base encoder; else fallback heuristic (~4 chars/token)
        enc = encoding or getattr(self, "base_encoder", None)
        if enc is None:
            # ceil(len/4) but simple integer division is fine as an estimate
            return max(1, (len(text) + 3) // 4)
        return len(enc.encode(text))

    def _count_tokens(self, obj: Any, encoding: Optional[Encoding] = None) -> int:  #
        """
        Count tokens in one message or text. Supports:
        - Msg (normalized)
        - dict with 'content'
        - str
        Falls back to JSON-dump for unknown structures.
        """
        # ChatML-ish overhead
        overhead = 3
        try:
            if isinstance(obj, Msg):
                txt = obj.as_text()
                return overhead + self._count_tokens_text(txt, encoding)
            if isinstance(obj, str):
                return overhead + self._count_tokens_text(obj, encoding)
            if isinstance(obj, dict):
                content = obj.get("content", "")
                if isinstance(content, str):
                    return overhead + self._count_tokens_text(content, encoding)
                return overhead + self._count_tokens_text(
                    json.dumps(content, ensure_ascii=False), encoding
                )
            # Fallback
            return overhead + self._count_tokens_text(str(obj), encoding)
        except Exception:
            return overhead + self._count_tokens_text(str(obj), encoding)

    def _count_tokens_messages(self, messages: Sequence[Any], encoding_model: str = None) -> int:  #
        enc = self._encoding_for_model(encoding_model=encoding_model)
        total = 0
        for m in messages:
            total += self._count_tokens(m, enc)
        return total + 3  # closing slack

    def _truncate_text_to_tokens(
        self,
        text: str,
        max_tokens: int,
        encoding_model: Optional[str] = None,
    ) -> str:
        """Truncate a string to at most `max_tokens` using the model's tokenizer.
        Fallback: ~4 chars ≈ 1 token if tiktoken isn't available.
        """
        if not isinstance(text, str):
            text = str(text)
        enc = self._encoding_for_model(encoding_model=encoding_model)
        if enc is None:
            approx_chars = max_tokens * 4
            if len(text) <= approx_chars:
                return text
            return (
                text[:approx_chars]
                + f"""
… [truncated to ~{max_tokens} tokens]"""
            )
        tokens = enc.encode(text)
        if len(tokens) <= max_tokens:
            return text
        trimmed = enc.decode(tokens[:max_tokens])
        # Note: suffix may push a couple tokens over; acceptable for guardrail.
        return (
            trimmed
            + f"""
… [truncated to {max_tokens} tokens]"""
        )

    def _tool_message_token_cap_for_model(self, model: str) -> int:  #
        ctx = self._context_limit_for_model(model)
        ratio = getattr(self, "tool_message_token_ratio", DEFAULT_TOOL_MESSAGE_TOKEN_RATIO)
        try:
            cap = max(1, int(ctx * float(ratio)))
        except Exception:
            cap = max(1, int(ctx * 0.2))
        return cap

    def _truncate_messages_to_budget(  #
        self,
        messages: List[Msg],
        model: str,
        *,
        max_context: int,
        max_output: int,
    ) -> List[Msg]:
        if not messages:
            return messages

        budget = max(1_024, max_context - max_output)

        pruned: List[Msg] = []
        for m in messages:
            if m.role == "tool":
                cap = self._tool_message_token_cap_for_model(model)
                truncated = self._truncate_text_to_tokens(m.as_text(), cap)
                pruned.append(
                    Msg(
                        role="tool",
                        content=truncated,
                        meta=(dict(m.meta) if m.meta else None),
                    )
                )
            else:
                pruned.append(m)

        total = self._count_tokens_messages(pruned)
        if total <= budget:
            return pruned

        keep: List[Msg] = []
        sys_first = pruned[0]
        keep.append(sys_first)

        tail = list(reversed(pruned[1:]))
        for m in tail:
            tmp = keep + [m]
            if self._count_tokens_messages(tmp) <= budget:
                keep.append(m)
            else:
                continue

        final_msgs = [keep[0]] + list(reversed(keep[1:]))
        return final_msgs

    def _disable_tools_if_low_budget_norm(self, req: ChatRequest) -> bool:  #
        model = req.model
        max_context = self._context_limit_for_model(model)
        margin = getattr(self, "tool_disable_margin_tokens", DEFAULT_TOOL_DISABLE_MARGIN_TOKENS)
        total = self._count_tokens_messages(req.messages)
        if total >= max_context - margin:
            # drop tools and add assistant notice
            req.tools = None
            req.messages.append(
                msg_text(
                    "assistant",
                    "Tooling disabled due to low remaining context. Please answer directly without calling tools.",
                )
            )
            self._log(
                f"Disabled tools: tokens {total} within {margin} of context {max_context}.",
                "warn",
            )
            return True
        return False

    def _ensure_context_budget_norm(self, req: ChatRequest) -> None:  #
        model = req.model
        max_context = self._context_limit_for_model(model)
        max_output = int(req.params.get("max_tokens") or self.output_reserve_tokens)
        msgs = req.messages or []
        total = self._count_tokens_messages(msgs)
        budget = max_context - max_output
        if total > budget:
            self._log(
                f"Context {total} > budget {budget} (ctx={max_context}, out={max_output}). Truncating…",
                "warning",
            )
            req.messages = self._truncate_messages_to_budget(
                msgs, model, max_context=max_context, max_output=max_output
            )

    def _looks_like_context_error(self, exc: Exception) -> bool:  #
        msg = str(exc).lower()
        return "maximum context length" in msg or "max context" in msg or "context length" in msg

    def _clamp_for_model(self, text: str, model_name: Optional[str]) -> str:  #
        if isinstance(text, str) and model_name:
            cap = self._tool_message_token_cap_for_model(model_name)
            text = self._truncate_text_to_tokens(text, cap)
        return text

    def _normalize_messages(
        self,
        system_prompt: str,
        chat_messages: Union[str, dict, List[dict], Any],
    ) -> List[Msg]:
        messages: List[Msg] = [msg_text("system", system_prompt)]

        def _append_one(m: Union[dict, Any]) -> None:
            if isinstance(m, Msg):
                messages.append(m)
                return
            if isinstance(m, dict):
                messages.append(msg_from_loose(m))
                return
            role = getattr(m, "role", None)
            content = getattr(m, "content", None)
            if role and isinstance(content, (str, list, dict)):
                messages.append(Msg(role=role, content=content))
                return
            if isinstance(m, str):
                messages.append(msg_text("user", m))
                return
            raise ValueError(f"Unsupported message type: {type(m)}")

        if isinstance(chat_messages, list):
            for m in chat_messages:
                _append_one(m)
        else:
            _append_one(chat_messages)

        return messages
