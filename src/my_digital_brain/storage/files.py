from __future__ import annotations

from pathlib import Path

from my_digital_brain.config import Settings


class SourceMediaStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def from_settings(cls, settings: Settings) -> "SourceMediaStore":
        return cls(settings.source_media_root)

    def ensure_root(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root
