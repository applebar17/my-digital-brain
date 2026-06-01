from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class IngestionModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        use_enum_values=True,
    )
