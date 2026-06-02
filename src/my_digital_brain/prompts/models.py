from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PromptTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    version: str
    template: str
    state_id: str | None = None
    purpose: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
