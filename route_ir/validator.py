from __future__ import annotations

from dataclasses import dataclass
import re

from .game import GameDefinition
from .models import ActionType, ConstraintType, RelativeDirection, RouteIR, RouteStatus


_LITERAL_MOVE = re.compile(
    r"\b(?P<direction>reverse|back\s+up|backwards?|forward)\s+"
    r"(?P<amount>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>centimet(?:er|re)s?|cm|met(?:er|re)s?|m)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValidationIssue:
    level: str  # ERROR or WARNING
    path: str
    message: str


@dataclass
class ValidationResult:
    issues: list[ValidationIssue]
    route_status: RouteStatus

    @property
    def valid(self) -> bool:
        """Whether the Route IR object is internally consistent."""
        return not any(i.level == "ERROR" for i in self.issues)

    @property
    def execution_allowed(self) -> bool:
        """Deterministic execution gate.

        A non-ready interpretation is never executable even when its
        non-executable representation is itself valid.
        """
        return self.valid and self.route_status == RouteStatus.READY


def validate_route(route: RouteIR, game: GameDefinition, *, source_text: str | None = None) -> ValidationResult:
    issues: list[ValidationIssue] = []

    blocking_model_issues = [issue for issue in route.issues if issue.blocking]

    if route.status == RouteStatus.READY:
        if not route.steps:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "steps",
                    "READY routes require at least one executable step.",
                )
            )
        if blocking_model_issues:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "issues",
                    "READY routes cannot contain blocking issues.",
                )
            )
    else:
        if not blocking_model_issues:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "issues",
                    f"{route.status.value} routes require at least one blocking issue.",
                )
            )

    if route.start is not None and route.start not in game.starts:
        issues.append(ValidationIssue("ERROR", "start", f"Unknown start '{route.start}'."))

    def check_target(target: str | None, path: str, required: bool = False) -> None:
        if target is None:
            if required:
                issues.append(ValidationIssue("ERROR", path, "A target is required."))
            return
        if target not in game.targets:
            issues.append(ValidationIssue("ERROR", path, f"Unknown target '{target}'."))

    def forbid(value: object | None, path: str, action: ActionType) -> None:
        if value is not None:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    path,
                    f"{path.rsplit('.', 1)[-1]} is not legal for {action.value}.",
                )
            )

    target_actions = {
        ActionType.MOVE_TO,
        ActionType.COLLECT,
        ActionType.SCORE,
        ActionType.FACE,
        ActionType.REPOSITION,
    }

    for i, step in enumerate(route.steps):
        p = f"steps[{i}]"

        if step.action in target_actions:
            check_target(step.target, f"{p}.target", required=True)
        else:
            forbid(step.target, f"{p}.target", step.action)

        # Mechanism fields are legal only for explicit SET_MECHANISM actions.
        if step.action != ActionType.SET_MECHANISM:
            forbid(step.mechanism, f"{p}.mechanism", step.action)
            forbid(step.mechanism_state, f"{p}.mechanism_state", step.action)

        if step.action == ActionType.MOVE_TO:
            forbid(step.distance_m, f"{p}.distance_m", step.action)
            forbid(step.direction, f"{p}.direction", step.action)
            forbid(step.angle_deg, f"{p}.angle_deg", step.action)
            forbid(step.duration_s, f"{p}.duration_s", step.action)

        elif step.action == ActionType.MOVE_RELATIVE:
            if step.distance_m is None:
                issues.append(
                    ValidationIssue("ERROR", f"{p}.distance_m", "MOVE_RELATIVE requires distance_m.")
                )
            if step.direction is None:
                issues.append(
                    ValidationIssue("ERROR", f"{p}.direction", "MOVE_RELATIVE requires direction.")
                )
            forbid(step.angle_deg, f"{p}.angle_deg", step.action)
            forbid(step.duration_s, f"{p}.duration_s", step.action)

        elif step.action == ActionType.TURN_RELATIVE:
            if step.angle_deg is None:
                issues.append(
                    ValidationIssue("ERROR", f"{p}.angle_deg", "TURN_RELATIVE requires angle_deg.")
                )
            forbid(step.distance_m, f"{p}.distance_m", step.action)
            forbid(step.direction, f"{p}.direction", step.action)
            forbid(step.duration_s, f"{p}.duration_s", step.action)

        elif step.action in {
            ActionType.COLLECT,
            ActionType.SCORE,
            ActionType.FACE,
            ActionType.REPOSITION,
        }:
            forbid(step.distance_m, f"{p}.distance_m", step.action)
            forbid(step.direction, f"{p}.direction", step.action)
            forbid(step.angle_deg, f"{p}.angle_deg", step.action)
            forbid(step.duration_s, f"{p}.duration_s", step.action)

        elif step.action == ActionType.WAIT:
            if step.duration_s is None:
                issues.append(ValidationIssue("ERROR", f"{p}.duration_s", "WAIT requires duration_s."))
            forbid(step.distance_m, f"{p}.distance_m", step.action)
            forbid(step.direction, f"{p}.direction", step.action)
            forbid(step.angle_deg, f"{p}.angle_deg", step.action)

        elif step.action == ActionType.SET_MECHANISM:
            forbid(step.distance_m, f"{p}.distance_m", step.action)
            forbid(step.direction, f"{p}.direction", step.action)
            forbid(step.angle_deg, f"{p}.angle_deg", step.action)
            forbid(step.duration_s, f"{p}.duration_s", step.action)

            if not step.mechanism:
                issues.append(
                    ValidationIssue("ERROR", f"{p}.mechanism", "SET_MECHANISM requires mechanism.")
                )
            elif step.mechanism not in game.mechanisms:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        f"{p}.mechanism",
                        f"Unknown mechanism '{step.mechanism}'.",
                    )
                )
            elif not step.mechanism_state:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        f"{p}.mechanism_state",
                        "SET_MECHANISM requires mechanism_state.",
                    )
                )
            elif step.mechanism_state not in game.mechanisms[step.mechanism]:
                allowed = ", ".join(game.mechanisms[step.mechanism])
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        f"{p}.mechanism_state",
                        f"Invalid state '{step.mechanism_state}'. Allowed: {allowed}.",
                    )
                )

        if step.action == ActionType.COLLECT and step.target in game.targets:
            if "collectable" not in game.targets[step.target].tags:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        f"{p}.target",
                        f"'{step.target}' is not collectable.",
                    )
                )

        if step.action == ActionType.SCORE and step.target in game.targets:
            if "scoring" not in game.targets[step.target].tags:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        f"{p}.target",
                        f"'{step.target}' is not a scoring target.",
                    )
                )

        for j, constraint in enumerate(step.constraints):
            cp = f"{p}.constraints[{j}]"
            if constraint.type in {
                ConstraintType.AVOID_TARGET,
                ConstraintType.PASS_LEFT_OF,
                ConstraintType.PASS_RIGHT_OF,
            }:
                check_target(constraint.target, f"{cp}.target", required=True)
            elif constraint.target is not None:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        f"{cp}.target",
                        f"{constraint.type.value} does not take a target.",
                    )
                )

    if route.finish:
        check_target(route.finish.face_target, "finish.face_target")
        check_target(route.finish.near_target, "finish.near_target")

        # Terminal FACE + finish.face_target is a duplicate terminal semantic
        # channel and is forbidden in v0.2.
        if route.finish.face_target is not None and route.steps:
            last = route.steps[-1]
            if last.action == ActionType.FACE:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "finish.face_target",
                        "Terminal facing must be represented either by the final FACE step or by finish.face_target, not both.",
                    )
                )

    # Audit only a single, literal relative-move request. The general validator
    # checks Route IR structure; this narrow source check prevents the CLI demo
    # from presenting an opposite-direction model interpretation as valid.
    if source_text and route.status == RouteStatus.READY:
        matches = list(_LITERAL_MOVE.finditer(source_text))
        # Do not apply the one-step assertion to a request with other actions.
        has_other_action = re.search(r"\b(?:then|and|after|before|collect|score|wait|turn|face|reposition)\b", source_text, re.IGNORECASE)
        if len(matches) == 1 and not has_other_action:
            match = matches[0]
            prefix = source_text[max(0, match.start() - 16):match.start()]
            if not re.search(r"(?:do\s+not|don't|never|without)\s*$", prefix, re.IGNORECASE):
                expected_direction = (
                    RelativeDirection.FORWARD
                    if match.group("direction").lower() == "forward"
                    else RelativeDirection.BACKWARD
                )
                if len(route.steps) != 1:
                    issues.append(ValidationIssue("ERROR", "steps", "One explicit relative move must produce exactly one step."))
                else:
                    step = route.steps[0]
                    if step.action != ActionType.MOVE_RELATIVE:
                        issues.append(ValidationIssue("ERROR", "steps[0].action", "Explicit relative move was not represented."))
                        step = None
                if len(route.steps) == 1 and step is not None:
                    if step.direction != expected_direction:
                        issues.append(ValidationIssue("ERROR", "steps[0].direction", f"Direction conflicts with explicit '{match.group('direction')}'."))
                    unit = match.group("unit").lower()
                    expected_distance = float(match.group("amount")) / (100 if unit.startswith(("cm", "centim")) else 1)
                    if step.distance_m is None or abs(step.distance_m - expected_distance) > 0.005:
                        issues.append(ValidationIssue("ERROR", "steps[0].distance_m", "Distance conflicts with the explicit request."))

    return ValidationResult(issues=issues, route_status=route.status)


def execution_allowed(route: RouteIR, game: GameDefinition) -> bool:
    """Return the deterministic execution-gate decision."""
    return validate_route(route, game).execution_allowed
