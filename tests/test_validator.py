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
