from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel

from my_digital_brain.ai.client.core import GenAIClient
from my_digital_brain.ai.client.settings import (
    GenAISettings,
    genai_settings_from_app_settings,
)
from my_digital_brain.ai.models import ToolResult
from my_digital_brain.ai.protocols import ToolCallingLLMProvider
from my_digital_brain.ai.providers import AzureOpenAIProvider, OpenAIProvider
from my_digital_brain.ai.router import (
    EMBEDDING_TASK,
    SPEECH_TO_TEXT_TASK,
    STRUCTURED_EXTRACTION_TASK,
    StaticModelRouter,
)
from my_digital_brain.ai.schemas import (
    ChatMessage,
    ChatRequest,
    EmbeddingRequest,
    StructuredGenerationRequest,
    TranscriptionRequest,
)
from my_digital_brain.ai.tools import ToolBox, build_tool_index
from my_digital_brain.config import Settings


class ExampleStructuredOutput(BaseModel):
    title: str


class StubGenAIClient:
    def __init__(self) -> None:
        self.chat_params: dict[str, Any] | None = None
        self.toolbox: ToolBox | None = None
        self.tools_mapping: dict[str, Any] | None = None
        self.max_tool_calls: int | None = None
        self.embed_call: dict[str, Any] | None = None
        self.transcribe_call: dict[str, Any] | None = None

    def call_openai(
        self,
        params: dict[str, Any],
        *,
        tools_mapping: dict[str, Any] | None = None,
        toolbox: ToolBox | None = None,
        max_tool_calls: int | None = None,
    ):
        self.chat_params = params
        self.tools_mapping = tools_mapping
        self.toolbox = toolbox
        self.max_tool_calls = max_tool_calls
        return SimpleNamespace(
            id="chat-request-1",
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="chat response"))
            ],
            usage=SimpleNamespace(
                prompt_tokens=4,
                completion_tokens=2,
                total_tokens=6,
            ),
        )

    def generate_structured(
        self,
        schema: type[BaseModel],
        system_prompt: str,
        input_message: str,
        **kwargs: Any,
    ) -> BaseModel:
        return schema.model_validate({"title": f"{system_prompt}:{input_message}"})

    def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> list[list[float]]:
        self.embed_call = {
            "texts": texts,
            "model": model,
            "dimensions": dimensions,
        }
        resolved_dimensions = dimensions or 2
        return [[float(index) for index in range(resolved_dimensions)] for _ in texts]

    def transcribe_audio(
        self,
        audio_path: Path,
        *,
        model: str | None = None,
        language: str | None = None,
        prompt: str | None = None,
    ) -> dict[str, Any]:
        self.transcribe_call = {
            "audio_path": audio_path,
            "model": model,
            "language": language,
            "prompt": prompt,
        }
        return {
            "id": "transcription-request-1",
            "text": "audio transcript",
            "language": language or "en",
            "duration": 3.5,
            "segments": [
                {"text": "audio", "start": 0.0, "end": 1.0},
                {"text": "transcript", "start": 1.0, "end": 3.5},
            ],
        }


class StubTranscriptions:
    def __init__(self) -> None:
        self.params: dict[str, Any] | None = None

    def create(self, **params: Any) -> dict[str, Any]:
        self.params = dict(params)
        self.params["file_name"] = params["file"].name
        self.params.pop("file")
        return {"text": "low-level transcript"}


def test_openai_provider_wraps_chat_structured_embeddings_and_transcription(
    tmp_path: Path,
) -> None:
    client = StubGenAIClient()
    provider = OpenAIProvider(
        client=client,
        settings=GenAISettings(openai_api_key="test"),
    )

    chat = provider.generate_chat(
        ChatRequest(
            messages=[ChatMessage(role="user", content="hello")],
            model="chat-model",
        )
    )
    structured = provider.generate_structured(
        StructuredGenerationRequest(
            schema=ExampleStructuredOutput,
            system_prompt="extract",
            input_message="memory",
            model="structured-model",
        )
    )
    embeddings = provider.embed(
        EmbeddingRequest(
            texts=["alpha", "beta"],
            model="embedding-model",
            dimensions=4,
        )
    )
    transcript = provider.transcribe(
        TranscriptionRequest(
            audio_path=tmp_path / "voice.ogg",
            model="transcribe-model",
            language="it",
            prompt="Memory note.",
        )
    )

    assert chat.content == "chat response"
    assert chat.usage.total_tokens == 6
    assert structured.parsed.title == "extract:memory"
    assert len(embeddings.embeddings[0]) == 4
    assert client.embed_call == {
        "texts": ["alpha", "beta"],
        "model": "embedding-model",
        "dimensions": 4,
    }
    assert transcript.text == "audio transcript"
    assert transcript.language == "it"
    assert len(transcript.segments) == 2
    assert client.transcribe_call["model"] == "transcribe-model"


def test_openai_provider_passes_toolbox_and_mapping_to_genai_client() -> None:
    client = StubGenAIClient()
    provider = OpenAIProvider(
        client=client,
        settings=GenAISettings(openai_api_key="test"),
    )
    tool = {
        "type": "function",
        "function": {
            "name": "example_tool",
            "description": "Example tool.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }
    toolbox = ToolBox(
        name="test",
        tools=[tool],
        tools_by_name=build_tool_index([tool]),
    )
    mapping = {"example_tool": lambda: ToolResult(status="ok", output="done")}

    chat = provider.generate_chat_with_tools(
        ChatRequest(
            messages=[ChatMessage(role="user", content="hello")],
            model="chat-model",
        ),
        toolbox=toolbox,
        tools_mapping=mapping,
        max_tool_calls=2,
    )

    assert isinstance(provider, ToolCallingLLMProvider)
    assert chat.content == "chat response"
    assert client.toolbox is toolbox
    assert client.tools_mapping is mapping
    assert client.max_tool_calls == 2


def test_azure_provider_marks_provider_and_deployment(tmp_path: Path) -> None:
    provider = AzureOpenAIProvider(
        client=StubGenAIClient(),
        settings=GenAISettings(
            is_azure=True,
            azure_openai_api_key="test",
            azure_openai_endpoint="https://example.openai.azure.com",
        ),
    )

    transcript = provider.transcribe(
        TranscriptionRequest(audio_path=tmp_path / "voice.ogg", model="whisper-deploy")
    )

    assert transcript.metadata.provider == "azure_openai"
    assert transcript.metadata.deployment == "whisper-deploy"
    assert isinstance(provider, ToolCallingLLMProvider)


def test_static_model_router_uses_default_and_azure_routes() -> None:
    openai_router = StaticModelRouter(
        settings=GenAISettings(
            chat_model_default="mini",
            chat_model_smart="smart",
            openai_embed_model="embed",
            openai_transcription_model="transcribe",
        )
    )
    azure_router = StaticModelRouter(
        settings=GenAISettings(
            is_azure=True,
            chat_model_default="azure-mini",
            chat_model_smart="azure-smart",
            openai_embed_model="embed",
            openai_transcription_model="transcribe",
            azure_openai_embed_deployment="embed-deploy",
            azure_openai_transcription_deployment="stt-deploy",
        )
    )

    assert openai_router.route(STRUCTURED_EXTRACTION_TASK).model == "smart"
    assert openai_router.route(EMBEDDING_TASK).model == "embed"
    assert openai_router.route(SPEECH_TO_TEXT_TASK).model == "transcribe"

    azure_embedding = azure_router.route(EMBEDDING_TASK)
    azure_stt = azure_router.route(SPEECH_TO_TEXT_TASK)

    assert azure_embedding.provider == "azure_openai"
    assert azure_embedding.model == "embed-deploy"
    assert azure_embedding.deployment == "embed-deploy"
    assert azure_stt.model == "stt-deploy"
    assert azure_stt.deployment == "stt-deploy"


def test_genai_settings_from_app_settings_includes_transcription_settings() -> None:
    app_settings = Settings(
        _env_file=None,
        OPENAI_TRANSCRIPTION_MODEL="gpt-test-transcribe",
        AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT="stt-deployment",
    )

    settings = genai_settings_from_app_settings(app_settings)

    assert settings.openai_transcription_model == "gpt-test-transcribe"
    assert settings.azure_openai_transcription_deployment == "stt-deployment"


def test_genai_settings_accepts_azure_provider_alias_and_chat_models() -> None:
    app_settings = Settings(
        _env_file=None,
        LLM_PROVIDER="azure",
        AZURE_CHAT_MODEL_DEFAULT="azure-default",
        AZURE_CHAT_MODEL_SMART="azure-smart",
        AZURE_CHAT_MODEL_REASONING="azure-reasoning",
    )

    settings = genai_settings_from_app_settings(app_settings)

    assert app_settings.normalized_llm_provider == "azure_openai"
    assert settings.is_azure is True
    assert settings.chat_model_default == "azure-default"
    assert settings.chat_model_smart == "azure-smart"
    assert settings.chat_model_reasoning == "azure-reasoning"


def test_genai_client_transcribe_audio_passes_normalized_params(tmp_path: Path) -> None:
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"audio")
    transcriptions = StubTranscriptions()
    client = object.__new__(GenAIClient)
    client.settings = GenAISettings(
        openai_transcription_model="gpt-test-transcribe",
    )
    client.client = SimpleNamespace(
        audio=SimpleNamespace(transcriptions=transcriptions)
    )

    result = client.transcribe_audio(
        audio_path,
        language="it",
        prompt="Personal memory voice note.",
    )

    assert result == {"text": "low-level transcript"}
    assert transcriptions.params["model"] == "gpt-test-transcribe"
    assert transcriptions.params["language"] == "it"
    assert transcriptions.params["prompt"] == "Personal memory voice note."
    assert transcriptions.params["response_format"] == "verbose_json"
    assert transcriptions.params["file_name"].endswith("voice.ogg")
