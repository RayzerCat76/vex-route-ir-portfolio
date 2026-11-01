from pathlib import Path

from route_ir.game import GameDefinition
from route_ir.models import ActionType, RelativeDirection, RouteIR, RouteStep
from route_ir.validator import validate_route


ROOT = Path(__file__).resolve().parents[1]
GAME = GameDefinition.load(ROOT / "configs" / "fake_game.json")


def test_valid_route():
    route = RouteIR(
        start="BLUE_LEFT_START",
        steps=[
            RouteStep(action=ActionType.COLLECT, target="CENTER_OBJECT"),
            RouteStep(action=ActionType.SCORE, target="LEFT_GOAL"),
            RouteStep(action=ActionType.MOVE_RELATIVE, distance_m=0.30, direction=RelativeDirection.BACKWARD),
        ],
    )
    assert validate_route(route, GAME).valid


def test_collecting_goal_is_invalid():
    route = RouteIR(
        start="BLUE_LEFT_START",
        steps=[RouteStep(action=ActionType.COLLECT, target="LEFT_GOAL")],
    )
    result = validate_route(route, GAME)
    assert not result.valid
    assert any("not collectable" in issue.message for issue in result.issues)


def test_unknown_target_is_invalid():
    route = RouteIR(
        start="BLUE_LEFT_START",
        steps=[RouteStep(action=ActionType.MOVE_TO, target="MADE_UP_TARGET")],
    )
    assert not validate_route(route, GAME).valid


def test_explicit_reverse_direction_is_checked_against_source():
    route = RouteIR(
        start="BLUE_LEFT_START",
        steps=[RouteStep(action=ActionType.MOVE_RELATIVE, distance_m=0.30, direction=RelativeDirection.FORWARD)],
    )
    result = validate_route(route, GAME, source_text="From blue left start, reverse 30 centimeters.")
    assert not result.valid
    assert any(issue.path == "steps[0].direction" for issue in result.issues)


def test_correct_explicit_reverse_move_passes_source_check():
    route = RouteIR(
        start="BLUE_LEFT_START",
        steps=[RouteStep(action=ActionType.MOVE_RELATIVE, distance_m=0.30, direction=RelativeDirection.BACKWARD)],
    )
    assert validate_route(route, GAME, source_text="From blue left start, reverse 30 centimeters.").valid


def test_simple_reverse_request_rejects_extra_turn():
    route = RouteIR(
        start="BLUE_LEFT_START",
        steps=[
            RouteStep(action=ActionType.TURN_RELATIVE, angle_deg=180),
            RouteStep(action=ActionType.MOVE_RELATIVE, distance_m=0.30, direction=RelativeDirection.BACKWARD),
        ],
    )
    result = validate_route(route, GAME, source_text="From blue left start, reverse 30 centimeters.")
    assert not result.valid
    assert any(issue.path == "steps" for issue in result.issues)
