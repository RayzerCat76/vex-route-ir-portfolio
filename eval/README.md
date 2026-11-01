# Route IR v0.1 Evaluation Set

This file documents the historical frozen v0.1 corpus. The current portfolio runtime uses Route IR v0.2; the `corpus_v02_*.jsonl` files are separate v0.2 fixtures. See the [build-process map](../docs/BUILD_PROCESS.md) and [README](../README.md) for the current reviewer path.

This benchmark is the first frozen human-authored test set for the natural-language -> Route IR boundary.

## Composition

- 40 total prompts
- 10 `basic`
- 10 `motion`
- 10 `sequence`
- 10 `ambiguity`

Each JSONL record contains:

- a unique case ID and category
- the natural-language prompt
- the expected Route IR semantic interpretation
- whether deterministic validation should pass
- whether the interpreter must surface an ambiguity
- optional explicitly accepted semantic alternatives

## Scoring

The score is normalized to 100 points:

- start: 5
- objective: 5
- step count: 5
- action sequence: 20
- targets: 20
- motion preferences: 15
- action parameters: 10
- constraints: 10
- finish preference: 5
- ambiguity presence: 5

Free-form ambiguity wording is not compared verbatim. The benchmark checks whether ambiguity is surfaced when required.

## Benchmark integrity rule

Do not modify expected outputs after inspecting a candidate model's failures unless the design itself is intentionally revised and the change is entered in the Master Bible Decision Log. If the Route IR schema changes, create a new benchmark version rather than silently rewriting v0.1.
