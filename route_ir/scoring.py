from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


WEIGHTS_V01 = {
    "start": 5.0,
    "objective": 5.0,
    "step_count": 5.0,
    "actions": 20.0,
    "targets": 20.0,
    "motion": 15.0,
    "parameters": 10.0,
    "constraints": 10.0,
    "finish": 5.0,
    "ambiguity": 5.0,
}

WEIGHTS_V02 = {
    "status": 15.0,
    "start": 5.0,
    "objective": 5.0,
    "step_count": 5.0,
    "actions": 15.0,
    "targets": 15.0,
    "motion": 10.0,
    "parameters": 10.0,
    "constraints": 10.0,
    "finish": 5.0,
    "issues": 5.0,
}

# Backward-compatible name used by historical tooling.
WEIGHTS = WEIGHTS_V01


@dataclass
class CaseScore:
    case_id: str
    total: float
    components: dict[str, float]
    details: list[str] = field(default_factory=list)


def weights_for_case(case: dict[str, Any]) -> dict[str, float]:
    return WEIGHTS_V02 if case.get("expected", {}).get("schema_version") == "0.2" else WEIGHTS_V01


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _acceptable(case: dict[str, Any], path: str, expected_value: Any) -> set[Any]:
    values = case.get("acceptable", {}).get(path)
    if values is None:
        return {_enum_value(expected_value)}
    return {_enum_value(v) for v in values}


def _eq(case: dict[str, Any], path: str, actual: Any, expected: Any) -> bool:
    return _enum_value(actual) in _acceptable(case, path, expected)


def _fraction(matches: list[bool]) -> float:
    if not matches:
        return 1.0
    return sum(matches) / len(matches)


def _constraint_key_v01(c: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (c.get("type"), c.get("target"), c.get("value"))


def _constraint_key_v02(c: dict[str, Any]) -> tuple[Any, Any]:
    return (c.get("type"), c.get("target"))


def _issue_key(issue: dict[str, Any]) -> tuple[Any, bool, Any]:
    return (issue.get("kind"), bool(issue.get("blocking", True)), issue.get("step_index"))


def score_route(case: dict[str, Any], predicted: Any) -> CaseScore:
    expected = case["expected"]
    actual = predicted.model_dump(mode="json")
    version = expected.get("schema_version", "0.1")
    weights = weights_for_case(case)
    components: dict[str, float] = {}
    details: list[str] = []

    if version == "0.2":
        components["status"] = weights["status"] if actual.get("status") == expected.get("status") else 0.0
        if not components["status"]:
            details.append(f"status: expected {expected.get('status')}, got {actual.get('status')}")

    components["start"] = weights["start"] if actual.get("start") == expected.get("start") else 0.0
    if not components["start"]:
        details.append(f"start: expected {expected.get('start')}, got {actual.get('start')}")

    components["objective"] = weights["objective"] if actual.get("objective") == expected.get("objective") else 0.0
    if not components["objective"]:
        details.append(f"objective: expected {expected.get('objective')}, got {actual.get('objective')}")

    exp_steps = expected.get("steps", [])
    act_steps = actual.get("steps", [])
    components["step_count"] = weights["step_count"] if len(exp_steps) == len(act_steps) else 0.0
    if len(exp_steps) != len(act_steps):
        details.append(f"step_count: expected {len(exp_steps)}, got {len(act_steps)}")

    aligned = min(len(exp_steps), len(act_steps))
    action_matches: list[bool] = []
    target_matches: list[bool] = []
    motion_matches: list[bool] = []
    parameter_matches: list[bool] = []
    constraint_matches: list[bool] = []

    for i in range(aligned):
        e = exp_steps[i]
        a = act_steps[i]

        ok = _eq(case, f"steps.{i}.action", a.get("action"), e.get("action"))
        action_matches.append(ok)
        if not ok:
            details.append(f"steps[{i}].action: expected {e.get('action')}, got {a.get('action')}")

        ok = _eq(case, f"steps.{i}.target", a.get("target"), e.get("target"))
        target_matches.append(ok)
        if not ok:
            details.append(f"steps[{i}].target: expected {e.get('target')}, got {a.get('target')}")

        em = e.get("motion", {})
        am = a.get("motion", {})
        for field_name in ("speed", "path_style", "preserve_speed"):
            path = f"steps.{i}.motion.{field_name}"
            ok = _eq(case, path, am.get(field_name), em.get(field_name))
            motion_matches.append(ok)
            if not ok:
                details.append(
                    f"steps[{i}].motion.{field_name}: expected {em.get(field_name)}, got {am.get(field_name)}"
                )

        for field_name in ("distance_m", "direction", "angle_deg", "duration_s", "mechanism", "mechanism_state"):
            path = f"steps.{i}.{field_name}"
            av = a.get(field_name)
            ev = e.get(field_name)
            if isinstance(av, float) and isinstance(ev, float):
                ok = abs(av - ev) <= 1e-6
            else:
                ok = _eq(case, path, av, ev)
            parameter_matches.append(ok)
            if not ok:
                details.append(f"steps[{i}].{field_name}: expected {ev}, got {av}")

        if version == "0.2":
            exp_constraints = {_constraint_key_v02(x) for x in e.get("constraints", [])}
            act_constraints = {_constraint_key_v02(x) for x in a.get("constraints", [])}
        else:
            exp_constraints = {_constraint_key_v01(x) for x in e.get("constraints", [])}
            act_constraints = {_constraint_key_v01(x) for x in a.get("constraints", [])}
        ok = exp_constraints == act_constraints
        constraint_matches.append(ok)
        if not ok:
            details.append(
                f"steps[{i}].constraints: expected {sorted(map(str, exp_constraints))}, got {sorted(map(str, act_constraints))}"
            )

    missing = abs(len(exp_steps) - len(act_steps))
    action_matches.extend([False] * missing)
    target_matches.extend([False] * missing)
    motion_matches.extend([False] * (missing * 3))
    parameter_matches.extend([False] * (missing * 6))
    constraint_matches.extend([False] * missing)

    components["actions"] = weights["actions"] * _fraction(action_matches)
    components["targets"] = weights["targets"] * _fraction(target_matches)
    components["motion"] = weights["motion"] * _fraction(motion_matches)
    components["parameters"] = weights["parameters"] * _fraction(parameter_matches)
    components["constraints"] = weights["constraints"] * _fraction(constraint_matches)

    exp_finish = expected.get("finish")
    act_finish = actual.get("finish")
    components["finish"] = weights["finish"] if exp_finish == act_finish else 0.0
    if exp_finish != act_finish:
        details.append(f"finish: expected {exp_finish}, got {act_finish}")

    if version == "0.2":
        exp_issues = {_issue_key(x) for x in expected.get("issues", [])}
        act_issues = {_issue_key(x) for x in actual.get("issues", [])}
        components["issues"] = weights["issues"] if exp_issues == act_issues else 0.0
        if exp_issues != act_issues:
            details.append(f"issues: expected {sorted(map(str, exp_issues))}, got {sorted(map(str, act_issues))}")
    else:
        ambiguity_expected = bool(case.get("ambiguity_required", False))
        ambiguity_actual = bool(actual.get("ambiguities"))
        components["ambiguity"] = weights["ambiguity"] if ambiguity_expected == ambiguity_actual else 0.0
        if ambiguity_expected != ambiguity_actual:
            details.append(
                f"ambiguity presence: expected {ambiguity_expected}, got {ambiguity_actual}"
            )

    total = round(sum(components.values()), 4)
    return CaseScore(case_id=case["id"], total=total, components=components, details=details)
