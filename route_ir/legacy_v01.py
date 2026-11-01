"""Frozen Route IR v0.1 schema used only to reproduce historical evidence.

New language-layer work must use route_ir.models.RouteIR (v0.2).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LegacyActionType(str, Enum):
    MOVE_TO = "MOVE_TO"
    COLLECT = "COLLECT"
    SCORE = "SCORE"
    FACE = "FACE"
    MOVE_RELATIVE = "MOVE_RELATIVE"
    WAIT = "WAIT"
    SET_MECHANISM = "SET_MECHANISM"
    REPOSITION = "REPOSITION"


class LegacySpeedProfile(str, Enum):
    CRAWL = "CRAWL"
    SLOW = "SLOW"
    NORMAL = "NORMAL"
    FAST = "FAST"
    AGGRESSIVE = "AGGRESSIVE"
    MAXIMUM = "MAXIMUM"


class LegacyPathStyle(str, Enum):
    DIRECT = "DIRECT"
    SMOOTH = "SMOOTH"
    WIDE = "WIDE"
    TIGHT = "TIGHT"
    MINIMUM_TIME = "MINIMUM_TIME"
    MINIMUM_DISTANCE = "MINIMUM_DISTANCE"


class LegacyOptimizationGoal(str, Enum):
    BALANCED = "BALANCED"
    MINIMUM_TIME = "MINIMUM_TIME"
    RELIABILITY = "RELIABILITY"
    SMOOTHNESS = "SMOOTHNESS"
    MINIMUM_DISTANCE = "MINIMUM_DISTANCE"
    POSITIONING = "POSITIONING"


class LegacyRelativeDirection(str, Enum):
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"


class LegacyConstraintType(str, Enum):
    AVOID_TARGET = "AVOID_TARGET"
    PASS_LEFT_OF = "PASS_LEFT_OF"
    PASS_RIGHT_OF = "PASS_RIGHT_OF"
    KEEP_WIDE = "KEEP_WIDE"
    LIMIT_TURN_SHARPNESS = "LIMIT_TURN_SHARPNESS"
    PRESERVE_SPEED = "PRESERVE_SPEED"
    END_FACING = "END_FACING"


class LegacyMotionPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    speed: LegacySpeedProfile = LegacySpeedProfile.NORMAL
    path_style: LegacyPathStyle = LegacyPathStyle.SMOOTH
    preserve_speed: bool = False


class LegacyRouteConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: LegacyConstraintType
    target: str | None = None
    value: float | None = None


class LegacyRouteStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: LegacyActionType
    target: str | None = None
    motion: LegacyMotionPreference = Field(default_factory=LegacyMotionPreference)
    distance_m: float | None = Field(default=None, ge=0.0, le=5.0)
    direction: LegacyRelativeDirection | None = None
    angle_deg: float | None = Field(default=None, ge=-360.0, le=360.0)
    duration_s: float | None = Field(default=None, ge=0.0, le=15.0)
    mechanism: str | None = None
    mechanism_state: str | None = None
    constraints: list[LegacyRouteConstraint] = Field(default_factory=list, max_length=8)


class LegacyFinishPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    face_target: str | None = None
    near_target: str | None = None


class LegacyRouteIR(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["0.1"] = "0.1"
    start: str
    objective: LegacyOptimizationGoal = LegacyOptimizationGoal.BALANCED
    steps: list[LegacyRouteStep] = Field(min_length=1, max_length=20)
    finish: LegacyFinishPreference | None = None
    assumptions: list[str] = Field(default_factory=list, max_length=8)
    ambiguities: list[str] = Field(default_factory=list, max_length=8)
