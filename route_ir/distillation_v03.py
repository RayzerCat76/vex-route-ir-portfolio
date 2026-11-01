from __future__ import annotations

import hashlib
import json
from collections import Counter
from enum import Enum
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .game import GameDefinition
from .models import (
    ActionType,
    ConstraintType,
    FinishPreference,
    IssueKind,
    MotionPreference,
    OptimizationGoal,
    RelativeDirection,
    RouteConstraint,
    RouteIR,
    RouteIssue,
    RouteStatus,
    RouteStep,
)
from .validator import validate_route


SCHEMA_VERSION = "distillation-v0.3"

class EntityRefKind(str, Enum):
    LITERAL = "LITERAL"
    PREVIOUS_TARGET = "PREVIOUS_TARGET"
    KNOWN_REFERENT = "KNOWN_REFERENT"


class DistanceRefKind(str, Enum):
    LITERAL = "LITERAL"
    PREVIOUS_DISTANCE = "PREVIOUS_DISTANCE"


class RealizationStrategy(str, Enum):
    DIRECT = "DIRECT"
    CONTEXTUAL = "CONTEXTUAL"
    AUTHENTIC_PATTERN = "AUTHENTIC_PATTERN"
    REPAIR = "REPAIR"
    NOISY = "NOISY"


class IssueCode(str, Enum):
    MISSING_DISTANCE = "MISSING_DISTANCE"
    UNRESOLVED_REFERENCE = "UNRESOLVED_REFERENCE"
    UNKNOWN_ENTITY = "UNKNOWN_ENTITY"
    INVALID_TARGET_TYPE = "INVALID_TARGET_TYPE"
    INVALID_MECHANISM_STATE = "INVALID_MECHANISM_STATE"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    CONTRADICTION = "CONTRADICTION"
    UNIT_AMBIGUITY = "UNIT_AMBIGUITY"
    PHYSICS_MISCONCEPTION = "PHYSICS_MISCONCEPTION"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class DialogueTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=1000)


class ContextSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_id: str = Field(min_length=1, max_length=160)
    current_start: str | None = None
    current_heading_deg: float | None = Field(default=None, ge=-360.0, le=360.0)
    previous_target: str | None = None
    previous_distance_m: float | None = Field(default=None, gt=0.0, le=5.0)
    known_referents: dict[str, str] = Field(default_factory=dict)
    active_mechanisms: dict[str, str] = Field(default_factory=dict)
    dialogue_history: list[DialogueTurn] = Field(default_factory=list, max_length=12)

    @field_validator("context_id")
    @classmethod
    def nonblank_context_id(cls, value: str) -> str:
        return value.strip()


class EntityReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: EntityRefKind
    value: str | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "EntityReference":
        if self.kind in {EntityRefKind.LITERAL, EntityRefKind.KNOWN_REFERENT}:
            if self.value is None or not self.value.strip():
                raise ValueError(f"{self.kind.value} requires a nonblank value")
            self.value = self.value.strip()
        elif self.value is not None:
            raise ValueError(f"{self.kind.value} does not accept value")
        return self


class DistanceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: DistanceRefKind
    value_m: float | None = Field(default=None, gt=0.0, le=5.0)

    @model_validator(mode="after")
    def validate_shape(self) -> "DistanceReference":
        if self.kind == DistanceRefKind.LITERAL and self.value_m is None:
            raise ValueError("LITERAL distance requires value_m")
        if self.kind == DistanceRefKind.PREVIOUS_DISTANCE and self.value_m is not None:
            raise ValueError("PREVIOUS_DISTANCE does not accept value_m")
        return self


class SemanticConstraintSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ConstraintType
    target: EntityReference | None = None


class SemanticStepSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ActionType
    target: EntityReference | None = None
    motion: MotionPreference = Field(default_factory=MotionPreference)
    distance: DistanceReference | None = None
    direction: RelativeDirection | None = None
    angle_deg: float | None = Field(default=None, ge=-360.0, le=360.0)
    duration_s: float | None = Field(default=None, gt=0.0, le=15.0)
    mechanism: str | None = None
    mechanism_state: str | None = None
    constraints: list[SemanticConstraintSpec] = Field(default_factory=list, max_length=8)


class SemanticFinishSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    face_target: EntityReference | None = None
    near_target: EntityReference | None = None


class SemanticIssueSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: IssueCode
    subject: str | None = Field(default=None, max_length=160)


class SemanticSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.3"] = "0.3"
    semantic_id: str = Field(min_length=1, max_length=160)
    start: str | None = None
    use_context_start: bool = False
    objective: OptimizationGoal = OptimizationGoal.BALANCED
    steps: list[SemanticStepSpec] = Field(default_factory=list, max_length=20)
    finish: SemanticFinishSpec | None = None
    issue: SemanticIssueSpec | None = None

    @field_validator("semantic_id")
    @classmethod
    def nonblank_semantic_id(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_semantic_shape(self) -> "SemanticSpec":
        if self.start is not None and self.use_context_start:
            raise ValueError("start and use_context_start are mutually exclusive")
        if self.issue is not None and self.steps:
            raise ValueError("explicit non-ready semantics must not contain executable steps")
        if self.issue is None and not self.steps:
            raise ValueError("ready semantic specs require at least one step")
        return self


class CompiledSemanticExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["distillation-v0.3"] = SCHEMA_VERSION
    compiled_id: str
    semantic_id: str
    context_id: str
    semantic_signature: str
    context_signature: str
    context_spec: ContextSpec
    target_signature: str
    route_ir_target: RouteIR


class DistillationExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["distillation-v0.3"] = SCHEMA_VERSION
    example_id: str
    compiled_id: str
    semantic_id: str
    context_id: str
    context_signature: str
    context_spec: ContextSpec
    language: Literal["en", "zh"]
    prompt: str = Field(min_length=1, max_length=2000)
    route_ir_target: RouteIR
    target_signature: str
    realization_strategy: RealizationStrategy
    teacher_id: str = "gpt-5.6-sol"
    authentic_pattern_ids: list[str] = Field(default_factory=list)
    source_group_ids: list[str] = Field(default_factory=list)

    @field_validator("example_id", "compiled_id", "semantic_id", "context_id", "context_signature", "prompt")
    @classmethod
    def nonblank_text_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class DistillationValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    example_count: int
    unique_prompt_count: int
    duplicate_prompt_count: int
    unique_target_count: int


class SemanticCompilationError(ValueError):
    pass


class DistillationConflictError(ValueError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _model_signature(model: BaseModel, *, exclude: set[str] | None = None) -> str:
    payload = model.model_dump(mode="json", exclude=exclude or set())
    return _sha256_text(_canonical_json(payload))


def route_target_signature(route: RouteIR) -> str:
    return _sha256_text(_canonical_json(route.model_dump(mode="json")))


def normalized_prompt(text: str) -> str:
    return " ".join(text.casefold().split())


def validate_context_against_game(context: ContextSpec, game: GameDefinition) -> None:
    if context.current_start is not None and context.current_start not in game.starts:
        raise SemanticCompilationError(f"Unknown context start: {context.current_start}")
    for label, target in (("previous_target", context.previous_target), *context.known_referents.items()):
        if target is not None and target not in game.targets:
            raise SemanticCompilationError(f"Unknown context target for {label}: {target}")
    for mechanism, state in context.active_mechanisms.items():
        if mechanism not in game.mechanisms:
            raise SemanticCompilationError(f"Unknown context mechanism: {mechanism}")
        if state not in game.mechanisms[mechanism]:
            raise SemanticCompilationError(f"Invalid context state {state!r} for {mechanism}")


def _resolve_entity(ref: EntityReference | None, context: ContextSpec) -> str | None:
    if ref is None:
        return None
    if ref.kind == EntityRefKind.LITERAL:
        return ref.value
    if ref.kind == EntityRefKind.PREVIOUS_TARGET:
        return context.previous_target
    if ref.kind == EntityRefKind.KNOWN_REFERENT:
        assert ref.value is not None
        return context.known_referents.get(ref.value)
    raise AssertionError(f"Unhandled entity reference kind: {ref.kind}")


def _resolve_distance(ref: DistanceReference | None, context: ContextSpec) -> float | None:
    if ref is None:
        return None
    if ref.kind == DistanceRefKind.LITERAL:
        return ref.value_m
    if ref.kind == DistanceRefKind.PREVIOUS_DISTANCE:
        return context.previous_distance_m
    raise AssertionError(f"Unhandled distance reference kind: {ref.kind}")


def _unresolved_reference_route(subject: str) -> RouteIR:
    return RouteIR(
        status=RouteStatus.NEEDS_CLARIFICATION,
        steps=[],
        issues=[RouteIssue(
            kind=IssueKind.AMBIGUOUS_REFERENCE,
            message=f"Context does not resolve {subject}.",
            blocking=True,
            clarification_question=f"What does {subject} refer to?",
        )],
    )


def _explicit_issue_route(issue: SemanticIssueSpec) -> RouteIR:
    subject = issue.subject or "the request"
    mapping: dict[IssueCode, tuple[RouteStatus, IssueKind, str, str | None]] = {
        IssueCode.MISSING_DISTANCE: (
            RouteStatus.NEEDS_CLARIFICATION,
            IssueKind.MISSING_INFORMATION,
            f"{subject} requires a distance.",
            "How far should the robot move?",
        ),
        IssueCode.UNRESOLVED_REFERENCE: (
            RouteStatus.NEEDS_CLARIFICATION,
            IssueKind.AMBIGUOUS_REFERENCE,
            f"{subject} cannot be resolved from context.",
            f"What does {subject} refer to?",
        ),
        IssueCode.UNKNOWN_ENTITY: (
            RouteStatus.NEEDS_CLARIFICATION,
            IssueKind.UNKNOWN_ENTITY,
            f"Unknown entity: {subject}.",
            "Which known target do you mean?",
        ),
        IssueCode.INVALID_TARGET_TYPE: (
            RouteStatus.NEEDS_CLARIFICATION,
            IssueKind.INVALID_TARGET_TYPE,
            f"{subject} has the wrong target type for the requested action.",
            "Which compatible target should be used?",
        ),
        IssueCode.INVALID_MECHANISM_STATE: (
            RouteStatus.NEEDS_CLARIFICATION,
            IssueKind.INVALID_MECHANISM_STATE,
            f"{subject} is not a valid mechanism state.",
            "Which supported mechanism state should be used?",
        ),
        IssueCode.UNSUPPORTED_CAPABILITY: (
            RouteStatus.UNSUPPORTED,
            IssueKind.UNSUPPORTED_CAPABILITY,
            f"{subject} is not supported by the configured robot.",
            None,
        ),
        IssueCode.CONTRADICTION: (
            RouteStatus.NEEDS_CLARIFICATION,
            IssueKind.CONTRADICTION,
            f"{subject} contains contradictory requirements.",
            "Which requirement should take priority?",
        ),
        IssueCode.UNIT_AMBIGUITY: (
            RouteStatus.NEEDS_CLARIFICATION,
            IssueKind.UNIT_AMBIGUITY,
            f"{subject} has an ambiguous unit.",
            "Which unit did you intend?",
        ),
        IssueCode.PHYSICS_MISCONCEPTION: (
            RouteStatus.NEEDS_CLARIFICATION,
            IssueKind.PHYSICS_MISCONCEPTION,
            f"{subject} assumes an unsupported physical behavior.",
            "What achievable robot behavior do you intend?",
        ),
        IssueCode.OUT_OF_SCOPE: (
            RouteStatus.NEEDS_CLARIFICATION,
            IssueKind.OUT_OF_SCOPE,
            f"{subject} is outside the Route IR interpretation task.",
            None,
        ),
    }
    status, kind, message, question = mapping[issue.code]
    return RouteIR(
        status=status,
        steps=[],
        issues=[RouteIssue(
            kind=kind,
            message=message,
            blocking=True,
            clarification_question=question,
        )],
    )


def _compile_constraint(
    spec: SemanticConstraintSpec,
    context: ContextSpec,
) -> tuple[RouteConstraint | None, str | None]:
    target = _resolve_entity(spec.target, context)
    if spec.target is not None and target is None:
        return None, f"constraint target for {spec.type.value}"
    return RouteConstraint(type=spec.type, target=target), None


def _compile_step(
    spec: SemanticStepSpec,
    context: ContextSpec,
) -> tuple[RouteStep | None, str | None]:
    target = _resolve_entity(spec.target, context)
    if spec.target is not None and target is None:
        return None, f"target for {spec.action.value}"

    distance_m = _resolve_distance(spec.distance, context)
    if spec.distance is not None and distance_m is None:
        return None, f"distance for {spec.action.value}"

    constraints: list[RouteConstraint] = []
    for constraint_spec in spec.constraints:
        constraint, unresolved = _compile_constraint(constraint_spec, context)
        if unresolved is not None:
            return None, unresolved
        assert constraint is not None
        constraints.append(constraint)

    return RouteStep(
        action=spec.action,
        target=target,
        motion=spec.motion,
        distance_m=distance_m,
        direction=spec.direction,
        angle_deg=spec.angle_deg,
        duration_s=spec.duration_s,
        mechanism=spec.mechanism,
        mechanism_state=spec.mechanism_state,
        constraints=constraints,
    ), None


def _compile_finish(
    spec: SemanticFinishSpec | None,
    context: ContextSpec,
) -> tuple[FinishPreference | None, str | None]:
    if spec is None:
        return None, None
    face_target = _resolve_entity(spec.face_target, context)
    if spec.face_target is not None and face_target is None:
        return None, "finish face target"
    near_target = _resolve_entity(spec.near_target, context)
    if spec.near_target is not None and near_target is None:
        return None, "finish near target"
    return FinishPreference(face_target=face_target, near_target=near_target), None


def _validated_route(route: RouteIR, game: GameDefinition) -> RouteIR:
    result = validate_route(route, game)
    if not result.valid:
        detail = "; ".join(f"{issue.path}: {issue.message}" for issue in result.issues)
        raise SemanticCompilationError(f"Compiled RouteIR is invalid: {detail}")
    return route


def compile_semantic_spec(
    spec: SemanticSpec,
    context: ContextSpec,
    game: GameDefinition,
) -> CompiledSemanticExample:
    validate_context_against_game(context, game)

    if spec.issue is not None:
        route = _validated_route(_explicit_issue_route(spec.issue), game)
    else:
        start = context.current_start if spec.use_context_start else spec.start
        if spec.use_context_start and start is None:
            route = _validated_route(_unresolved_reference_route("the current start"), game)
        else:
            compiled_steps: list[RouteStep] = []
            unresolved: str | None = None
            for step_spec in spec.steps:
                step, unresolved = _compile_step(step_spec, context)
                if unresolved is not None:
                    break
                assert step is not None
                compiled_steps.append(step)

            if unresolved is not None:
                route = _validated_route(_unresolved_reference_route(unresolved), game)
            else:
                finish, unresolved_finish = _compile_finish(spec.finish, context)
                if unresolved_finish is not None:
                    route = _validated_route(
                        _unresolved_reference_route(unresolved_finish),
                        game,
                    )
                else:
                    route = _validated_route(
                        RouteIR(
                            status=RouteStatus.READY,
                            start=start,
                            objective=spec.objective,
                            steps=compiled_steps,
                            finish=finish,
                            issues=[],
                        ),
                        game,
                    )

    semantic_signature = _model_signature(spec, exclude={"semantic_id"})
    context_signature = _model_signature(context, exclude={"context_id"})
    target_signature = route_target_signature(route)
    compiled_id = _sha256_text(
        "\x1f".join((spec.semantic_id, context.context_id, semantic_signature, context_signature, target_signature))
    )[:24]
    return CompiledSemanticExample(
        compiled_id=compiled_id,
        semantic_id=spec.semantic_id,
        context_id=context.context_id,
        semantic_signature=semantic_signature,
        context_signature=context_signature,
        context_spec=context,
        target_signature=target_signature,
        route_ir_target=route,
    )


def build_distillation_example(
    compiled: CompiledSemanticExample,
    *,
    prompt: str,
    language: Literal["en", "zh"],
    realization_strategy: RealizationStrategy,
    teacher_id: str = "gpt-5.6-sol",
    authentic_pattern_ids: Sequence[str] = (),
    source_group_ids: Sequence[str] = (),
) -> DistillationExample:
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("prompt must not be blank")
    target_signature = route_target_signature(compiled.route_ir_target)
    if target_signature != compiled.target_signature:
        raise ValueError("compiled target signature drift detected")

    example_id = _sha256_text(
        "\x1f".join((compiled.compiled_id, language, realization_strategy.value, normalized_prompt(prompt)))
    )[:24]
    context_signature = _model_signature(compiled.context_spec, exclude={"context_id"})
    if context_signature != compiled.context_signature:
        raise ValueError("compiled context signature drift detected")

    return DistillationExample(
        example_id=example_id,
        compiled_id=compiled.compiled_id,
        semantic_id=compiled.semantic_id,
        context_id=compiled.context_id,
        context_signature=compiled.context_signature,
        context_spec=compiled.context_spec,
        language=language,
        prompt=prompt,
        route_ir_target=compiled.route_ir_target,
        target_signature=compiled.target_signature,
        realization_strategy=realization_strategy,
        teacher_id=teacher_id,
        authentic_pattern_ids=sorted(set(authentic_pattern_ids)),
        source_group_ids=sorted(set(source_group_ids)),
    )


def validate_distillation_examples(
    examples: Sequence[DistillationExample],
    game: GameDefinition,
) -> DistillationValidationReport:
    input_to_targets: dict[tuple[str, str], set[str]] = {}
    example_ids: set[str] = set()
    targets: set[str] = set()

    for example in examples:
        if example.example_id in example_ids:
            raise DistillationConflictError(f"Duplicate example_id: {example.example_id}")
        example_ids.add(example.example_id)

        actual_context_signature = _model_signature(
            example.context_spec,
            exclude={"context_id"},
        )
        if example.context_spec.context_id != example.context_id:
            raise DistillationConflictError(
                f"Context id drift for example {example.example_id}"
            )
        if actual_context_signature != example.context_signature:
            raise DistillationConflictError(
                f"Context signature drift for example {example.example_id}"
            )

        actual_signature = route_target_signature(example.route_ir_target)
        if actual_signature != example.target_signature:
            raise DistillationConflictError(
                f"Target signature drift for example {example.example_id}"
            )
        result = validate_route(example.route_ir_target, game)
        if not result.valid:
            raise DistillationConflictError(
                f"Invalid RouteIR target for example {example.example_id}"
            )

        key = (example.context_signature, normalized_prompt(example.prompt))
        input_to_targets.setdefault(key, set()).add(example.target_signature)
        targets.add(example.target_signature)

    conflicts = {
        key: signatures
        for key, signatures in input_to_targets.items()
        if len(signatures) > 1
    }
    if conflicts:
        first_context, first_prompt = sorted(conflicts)[0]
        raise DistillationConflictError(
            "Normalized prompt in the same context maps to multiple RouteIR targets: "
            f"context={first_context!r}, prompt={first_prompt!r}"
        )

    input_counts = Counter(
        (example.context_signature, normalized_prompt(example.prompt))
        for example in examples
    )
    duplicate_prompt_count = sum(
        count - 1 for count in input_counts.values() if count > 1
    )
    return DistillationValidationReport(
        example_count=len(examples),
        unique_prompt_count=len(input_to_targets),
        duplicate_prompt_count=duplicate_prompt_count,
        unique_target_count=len(targets),
    )


def build_teacher_realization_request(
    spec: SemanticSpec,
    context: ContextSpec,
    *,
    language: Literal["en", "zh"],
    authentic_patterns: Sequence[str] = (),
) -> dict[str, object]:
    """Build the teacher payload without exposing or asking it to invent RouteIR."""
    return {
        "schema_version": SCHEMA_VERSION,
        "role": "natural-language-realizer-only",
        "language": language,
        "semantic_spec": spec.model_dump(mode="json"),
        "context_spec": context.model_dump(mode="json"),
        "authentic_language_patterns": list(authentic_patterns),
        "output_contract": {
            "return": "one natural user utterance only",
            "must_preserve_semantics": True,
            "must_not_emit_route_ir": True,
            "must_not_add_actions_quantities_targets_or_constraints": True,
        },
    }
