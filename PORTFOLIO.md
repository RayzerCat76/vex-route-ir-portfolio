# VEX Route IR — portfolio guide

**What it is:** a prototype that turns a typed VEX autonomous-route request into structured Route IR, then checks that structure against a small simulated game definition. It does not generate trajectories, C++, motor commands, or control a physical robot.

## Try the current prototype

Requirements: Python 3.11+, [Ollama](https://ollama.com/), and a downloaded model. From this repository:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
ollama pull qwen3:1.7b
python cli.py "From blue left start, move forward 30 centimeters." --model qwen3:1.7b
```

The command prints the model's Route IR JSON followed by the deterministic validator's result. The included `configs/fake_game.json` is deliberately small; it is not a current VEX game manual. To inspect the validator without downloading a model, install pytest and run `python -m pytest -q tests/test_validator.py`.

## What changed

The first design separated language interpretation from deterministic validation. The current source uses a v0.2 schema with explicit readiness status, route steps, issues, and motion constraints. That separation makes an incorrect route inspectable before any robot execution stage is built.

## Verified scope and limitation

On 1 November 2026, the exported snapshot passed its three focused validator tests. A local `qwen3:1.7b` run correctly converted the forward-30-centimeter example above and the validator returned `VALID`. Another request to reverse 30 centimeters produced a structurally valid but semantically wrong forward move. The validator checks structure and game constraints; it does not prove the model understood the original sentence. The larger `qwen3:4b` model timed out in a 75-second local trial. These examples are local tests, not an external accuracy claim.

## Source and contributions

Ray Liu developed the route representation, validation prototype, evaluation approach, and this demonstration, with OpenAI Codex assisting with implementation, tests, debugging, and documentation. No other human collaborator contributed to this project. Ollama and Qwen provide third-party model inference; Pydantic supplies schema validation. The model weights are not included here.

This is a clean snapshot of the current committed Route IR runtime and evaluator from the private `feature/robotics-crawler-v01` branch, commit `f99aa6e`. Experimental crawler and training modules, uncommitted experiments, and unrelated robotics material are excluded.
