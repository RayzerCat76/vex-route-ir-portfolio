from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RouteStatus(str, Enum):
    READY = "READY"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    UNSUPPORTED = "UNSUPPORTED"


class IssueKind(str, Enum):
    MISSING_INFORMATION = "MISSING_INFORMATION"
    AMBIGUOUS_REFERENCE = "AMBIGUOUS_REFERENCE"
    UNKNOWN_ENTITY = "UNKNOWN_ENTITY"
    INVALID_TARGET_TYPE = "INVALID_TARGET_TYPE"
    INVALID_MECHANISM_STATE = "INVALID_MECHANISM_STATE"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    CONTRADICTION = "CONTRADICTION"
    UNIT_AMBIGUITY = "UNIT_AMBIGUITY"
    PHYSICS_MISCONCEPTION = "PHYSICS_MISCONCEPTION"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class ActionType(str, Enum):
    MOVE_TO = "MOVE_TO"
    MOVE_RELATIVE = "MOVE_RELATIVE"
    TURN_RELATIVE = "TURN_RELATIVE"
    COLLECT = "COLLECT"
    SCORE = "SCORE"
    FACE = "FACE"
    WAIT = "WAIT"
    SET_MECHANISM = "SET_MECHANISM"
    REPOSITION = "REPOSITION"


class SpeedProfile(str, Enum):
    CRAWL = "CRAWL"
    SLOW = "SLOW"
    NORMAL = "NORMAL"
    FAST = "FAST"
    AGGRESSIVE = "AGGRESSIVE"
    MAXIMUM = "MAXIMUM"


class PathStyle(str, Enum):
    DIRECT = "DIRECT"
    SMOOTH = "SMOOTH"
    WIDE = "WIDE"
    TIGHT = "TIGHT"


class OptimizationGoal(str, Enum):
    BALANCED = "BALANCED"
    MINIMUM_TIME = "MINIMUM_TIME"
    RELIABILITY = "RELIABILITY"
    SMOOTHNESS = "SMOOTHNESS"
    MINIMUM_DISTANCE = "MINIMUM_DISTANCE"
    POSITIONING = "POSITIONING"


class RelativeDirection(str, Enum):
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"


class ConstraintType(str, Enum):
    AVOID_TARGET = "AVOID_TARGET"
    PASS_LEFT_OF = "PASS_LEFT_OF"
    PASS_RIGHT_OF = "PASS_RIGHT_OF"
    KEEP_WIDE = "KEEP_WIDE"
    LIMIT_TURN_SHARPNESS = "LIMIT_TURN_SHARPNESS"


class MotionPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speed: SpeedProfile = SpeedProfile.NORMAL
    path_style: PathStyle = PathStyle.SMOOTH
    preserve_speed: bool = False


class RouteConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ConstraintType
    target: str | None = None


class RouteIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: IssueKind
    message: str = Field(min_length=1, max_length=500)
    blocking: bool = True
    step_index: int | None = Field(default=None, ge=0, le=19)
    clarification_question: str | None = Field(default=None, max_length=500)


class RouteStep(BaseModel):
    """Canonical semantic route step for Route IR v0.2.

    Cross-field action invariants are intentionally enforced by the
    deterministic validator rather than inferred from schema shape alone.
    """

    model_config = ConfigDict(extra="forbid")

    action: ActionType
    target: str | None = None
    motion: MotionPreference = Field(default_factory=MotionPreference)

    # SI-normalized semantic quantities. Geometry/control values remain
    # downstream responsibilities.
    distance_m: float | None = Field(default=None, gt=0.0, le=5.0)
    direction: RelativeDirection | None = None
    angle_deg: float | None = Field(default=None, ge=-360.0, le=360.0)
    duration_s: float | None = Field(default=None, gt=0.0, le=15.0)

    mechanism: str | None = None
    mechanism_state: str | None = None

    constraints: list[RouteConstraint] = Field(default_factory=list, max_length=8)


class FinishPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    face_target: str | None = None
    near_target: str | None = None


class RouteIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.2"] = "0.2"
    status: RouteStatus = RouteStatus.READY

    # Start may be supplied by the natural-language instruction or by a
    # higher-level session/robot context. When present it must resolve to a
    # GameDefinition start; the deterministic validator enforces that.
    start: str | None = None
    objective: OptimizationGoal = OptimizationGoal.BALANCED

    # Non-ready interpretations are allowed to contain zero executable steps.
    steps: list[RouteStep] = Field(default_factory=list, max_length=20)
    finish: FinishPreference | None = None
    issues: list[RouteIssue] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def canonicalize_empty_finish(self) -> "RouteIR":
        """An empty finish object carries no control semantics.

        Qwen commonly emits the optional object with both fields null. Route
        IR keeps a single canonical representation so semantically identical
        outputs do not diverge downstream.
        """
        if (
            self.finish is not None
            and self.finish.face_target is None
            and self.finish.near_target is None
        ):
            self.finish = None
        return self
