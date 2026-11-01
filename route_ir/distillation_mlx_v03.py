from __future__ import annotations

import json
from typing import Any

from .distillation_v03 import ContextSpec, DistillationExample
from .game import GameDefinition
from .prompts import build_system_prompt


_CONTEXT_INSTRUCTIONS = """RUNTIME_CONTEXT
Use the runtime state below only to resolve contextual references in the current request.
Do not invent missing context or override an explicit current-user instruction.
`current_start` supplies route-start metadata only when the request depends on the current start.
`previous_target`, `previous_distance_m`, and `known_referents` may resolve references such as
"the previous target", "the same distance", or a named referent. Other fields are state only.
RUNTIME_CONTEXT_JSON:"""


def operational_context_payload(context: ContextSpec) -> dict[str, Any]:
    """Return only runtime-semantic context; context_id is provenance, not model input."""
    payload = context.model_dump(mode="json", exclude={"context_id"})
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != {} and value != []
    }


def build_contextual_system_prompt(
    game: GameDefinition,
    context: ContextSpec | None = None,
) -> str:
    """Keep the legacy system prompt byte-identical unless runtime context is non-empty."""
    base = build_system_prompt(game)
    if context is None:
        return base
    payload = operational_context_payload(context)
    if not payload:
        return base
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{base}\n\n{_CONTEXT_INSTRUCTIONS}\n{encoded}"


def build_distillation_chat_record(
    example: DistillationExample,
    game: GameDefinition,
) -> dict[str, list[dict[str, str]]]:
    """Serialize one accepted v0.3 example using the production prompt contract."""
    return {
        "messages": [
            {
                "role": "system",
                "content": build_contextual_system_prompt(game, example.context_spec),
            },
            {"role": "user", "content": example.prompt},
            {"role": "assistant", "content": example.route_ir_target.model_dump_json()},
        ]
    }
