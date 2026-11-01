# VEX Route IR — portfolio guide

**What it is:** a prototype that turns a typed VEX autonomous-route request into structured Route IR, then checks that structure against a small simulated game definition. It does not generate trajectories, C++, motor commands, or control a physical robot.

## Try the current prototype

The [guided browser prototype](https://rayzercat76.github.io/vex-route-ir-portfolio/) demonstrates one relative move without installation. It uses a deliberately narrow deterministic parser and a direction sketch, not the Ollama model or a robot. For the actual model path, use the CLI below.

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

On 1 November 2026, the current portfolio snapshot passed six focused validator tests. A local `qwen3:1.7b` run correctly converted the forward-30-centimeter example above and returned `VALID`. The earlier reverse request had produced a structurally valid but semantically wrong forward move, so the CLI now audits a single explicit direction and distance against the request. In a fresh local reverse run, the model still emitted malformed extra or missing fields; the validator returned `INVALID` rather than accepting them. The browser walkthrough handles that narrow reverse example deterministically, but this does not establish reliable natural-language interpretation across requests. The larger `qwen3:4b` model timed out in a prior 75-second local trial. These are local tests, not an external accuracy claim.

## Source and contributions

Ray Liu developed the route representation, validation prototype, evaluation approach, and this demonstration, with OpenAI Codex assisting with implementation, tests, debugging, and documentation. No other human collaborator contributed to this project. Ollama and Qwen provide third-party model inference; Pydantic supplies schema validation. The model weights are not included here.

This is a clean snapshot of the current committed Route IR runtime and evaluator from the private `feature/robotics-crawler-v01` branch, commit `f99aa6e`. Experimental crawler and training modules, uncommitted experiments, and unrelated robotics material are excluded.
