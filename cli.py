from __future__ import annotations

import argparse
import json
from pathlib import Path

from route_ir import GameDefinition, interpret_route, validate_route


ROOT = Path(__file__).resolve().parent
DEFAULT_GAME = ROOT / "configs" / "fake_game.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Interpret a natural-language VEX route locally.")
    parser.add_argument("route", nargs="*", help="Route description. If omitted, you will be prompted.")
    parser.add_argument("--game", default=str(DEFAULT_GAME), help="Path to game-definition JSON.")
    parser.add_argument("--model", default=None, help="Ollama model name (default: qwen3:4b).")
    args = parser.parse_args()

    text = " ".join(args.route).strip() or input("Describe your route: ").strip()
    game = GameDefinition.load(args.game)

    route = interpret_route(text, game, model=args.model)
    result = validate_route(route, game)

    print("\n=== ROUTE IR ===")
    print(json.dumps(route.model_dump(mode="json"), indent=2))

    print("\n=== VALIDATION ===")
    print("VALID" if result.valid else "INVALID")
    if not result.issues:
        print("No issues.")
    else:
        for issue in result.issues:
            print(f"[{issue.level}] {issue.path}: {issue.message}")


if __name__ == "__main__":
    main()
