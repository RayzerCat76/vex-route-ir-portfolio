from __future__ import annotations

import os

from ollama import chat

from .distillation_mlx_v03 import build_contextual_system_prompt
from .distillation_v03 import ContextSpec
from .game import GameDefinition
from .models import RouteIR


def interpret_route(
    text: str,
    game: GameDefinition,
    model: str | None = None,
    *,
    context: ContextSpec | None = None,
) -> RouteIR:
    model = model or os.getenv("VEX_ROUTE_MODEL", "qwen3:4b")

    response = chat(
        model=model,
        messages=[
            {"role": "system", "content": build_contextual_system_prompt(game, context)},
            {"role": "user", "content": text},
        ],
        format=RouteIR.model_json_schema(),
        think=False,
        options={"temperature": 0},
    )

    return RouteIR.model_validate_json(response.message.content)
