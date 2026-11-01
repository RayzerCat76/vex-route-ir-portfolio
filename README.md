# VEX Route IR

An early natural-language interface for VEX autonomous-route planning. It converts a typed instruction into a structured route and checks the result against a small simulated game definition. **It does not drive a robot or generate trajectories or motor code.**

## Try it

Install Python 3.11+ and [Ollama](https://ollama.com/), then run:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
ollama pull qwen3:1.7b
python cli.py "From blue left start, move forward 30 centimeters." --model qwen3:1.7b
```

The program prints Route IR JSON and a deterministic validation result. `configs/fake_game.json` is a small prototype fixture, not an official game manual. See [PORTFOLIO.md](PORTFOLIO.md) for the design history, current test evidence, known limitations, and contribution credits.
