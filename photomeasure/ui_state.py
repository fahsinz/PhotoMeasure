"""Pure state transitions; no Streamlit imports or image bytes."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SelectionState:
    image_key: str = ""
    reference: list = field(default_factory=list)
    target: list = field(default_factory=list)
    reference_confirmed: bool = False
    target_confirmed: bool = False
    result: dict | None = None
    record: dict | None = None
    revision: int = 0
    settings_key: Any = None

    def invalidate(self) -> None:
        self.result = None
        self.record = None
        self.revision += 1

    def set_image(self, key: str) -> bool:
        if key == self.image_key:
            return False
        self.image_key = key
        self.reset()
        return True

    def reset(self) -> None:
        self.reference = []
        self.target = []
        self.reference_confirmed = False
        self.target_confirmed = False
        self.invalidate()

    def set_points(self, kind: str, points: list) -> None:
        if kind not in ("reference", "target"):
            raise ValueError("Unknown selection kind")
        setattr(self, kind, [[float(x), float(y)] for x, y in points])
        setattr(self, kind + "_confirmed", False)
        self.invalidate()

    def set_settings(self, key: Any) -> bool:
        if key == self.settings_key:
            return False
        self.settings_key = key
        self.reference_confirmed = False
        self.target_confirmed = False
        self.invalidate()
        return True
