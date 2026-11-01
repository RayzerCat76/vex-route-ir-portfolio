# VEX Route IR

An early natural-language interface for VEX autonomous-route planning. It converts a typed instruction into a structured route and checks the result against a small simulated game definition. **It does not drive a robot or generate trajectories or motor code.**

## Try it

Open the [guided browser prototype](https://rayzercat76.github.io/vex-route-ir-portfolio/) to enter a one-step forward or reverse request, inspect the Route IR JSON, and see a direction sketch and validation result. This page is a deterministic, model-free walkthrough of a small supported subset. It does not run the Ollama interpreter or a robot.

Watch the [6.67-second guided demo](docs/guided-demo.mp4) for a valid reverse request, an ambiguous request that stops at **Needs clarification**, and a return to the forward example. The recording shows the model-free browser walkthrough.

For the actual local-model interpreter, install Python 3.11+ and [Ollama](https://ollama.com/), then run:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
ollama pull qwen3:1.7b
python cli.py "From blue left start, move forward 30 centimeters." --model qwen3:1.7b
```

The program prints Route IR JSON and a deterministic validation result. For a single explicit move, the CLI now checks the source wording against the model's direction and distance so an opposite-direction interpretation is marked invalid. The small local model can still make other interpretation errors. `configs/fake_game.json` is a small prototype fixture, not an official game manual. See [PORTFOLIO.md](PORTFOLIO.md) for the design history, current test evidence, known limitations, and contribution credits.

## Where to look in the source

The [build-process map](docs/BUILD_PROCESS.md) connects the first schema, a detected reverse-direction error, and the current guarded interpreter. Follow [CLI input](cli.py) → [Ollama interpretation](route_ir/llm.py) → [Route IR schema](route_ir/models.py) → [deterministic validation](route_ir/validator.py). [Focused tests](tests/test_validator.py) cover the validator, and [a real local-model forward run](docs/real-model-forward.txt) records the CLI output. The [browser page](docs/index.html) is a separate, narrow deterministic demonstration. The `eval/` directory holds frozen test corpora; `distillation_*` modules are not used by either reviewer demo.
