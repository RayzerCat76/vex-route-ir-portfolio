from .game import GameDefinition
from .models import RouteIR, RouteStatus
from .validator import execution_allowed, validate_route


def interpret_route(*args, **kwargs):
    """Lazy wrapper so non-LLM tooling does not require the Ollama package."""
    from .llm import interpret_route as _interpret_route

    return _interpret_route(*args, **kwargs)


__all__ = [
    "GameDefinition",
    "RouteIR",
    "RouteStatus",
    "interpret_route",
    "validate_route",
    "execution_allowed",
]
