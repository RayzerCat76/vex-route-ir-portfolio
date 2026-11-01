from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class TargetDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    x_m: float
    y_m: float
    tags: list[str] = []


class DriveDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    can_strafe: bool = False


class GameDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    game_id: str
    starts: dict[str, tuple[float, float, float]]
    targets: dict[str, TargetDefinition]
    mechanisms: dict[str, list[str]]
    drive: DriveDefinition

    @classmethod
    def load(cls, path: str | Path) -> "GameDefinition":
        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate(json.load(f))

    def compact_context(self) -> dict:
        """Only semantic information is shown to the LLM.

        Exact coordinates stay out of the prompt so the model cannot pretend
        to be the geometric planner.
        """
        return {
            "game_id": self.game_id,
            "starts": list(self.starts.keys()),
            "targets": {
                name: {"kind": target.kind, "tags": target.tags}
                for name, target in self.targets.items()
            },
            "mechanisms": self.mechanisms,
            "drive": self.drive.model_dump(),
        }
