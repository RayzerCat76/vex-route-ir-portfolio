from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

from pydantic import ValidationError

from route_ir.game import GameDefinition
from route_ir.legacy_v01 import LegacyRouteIR
from route_ir.models import RouteIR, RouteStatus
from route_ir.scoring import score_route, weights_for_case
from route_ir.validator import validate_route

ROOT = Path(__file__).resolve().parent
DEFAULT_CORPUS = ROOT / "eval" / "corpus_v02_smoke.jsonl"
DEFAULT_GAME = ROOT / "configs" / "fake_game.json"


def load_corpus(path: Path) -> list[dict]:
    cases = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
    return cases


def _schema_version(case: dict) -> str:
    return str(case.get("expected", {}).get("schema_version", "0.1"))


def build_summary(
    *,
    args: argparse.Namespace,
    rows: list[dict],
    total_cases: int,
    category_scores: dict[str, list[float]],
    parse_failures: int,
    validity_mismatches: int,
    execution_mismatches: int,
    latencies_ms: list[float],
    component_totals: dict[str, list[float]],
    hallucinated_entity_cases: int,
    weights: dict[str, float],
    schema_version: str,
) -> dict:
    scores = [r["score"] for r in rows]
    completed = len(rows)
    return {
        "schema_version": schema_version,
        "mode": args.mode,
        "model": args.model if args.mode == "ollama" else None,
        "cases": completed,
        "total_cases": total_cases,
        "complete": completed == total_cases,
        "mean_score": round(statistics.mean(scores), 3) if scores else 0.0,
        "median_score": round(statistics.median(scores), 3) if scores else 0.0,
        "parse_failures": parse_failures,
        "validity_mismatches": validity_mismatches,
        "validity_accuracy": round(100 * (completed - validity_mismatches) / completed, 3) if completed else 0.0,
        "execution_mismatches": execution_mismatches,
        "execution_gate_accuracy": round(100 * (completed - execution_mismatches) / completed, 3) if completed else 0.0,
        "hallucinated_entity_cases": hallucinated_entity_cases,
        "hallucinated_entity_rate": round(100 * hallucinated_entity_cases / completed, 3) if completed else 0.0,
        "component_accuracy": {
            name: round(100 * statistics.mean(values) / weights[name], 3)
            for name, values in sorted(component_totals.items())
            if name in weights and weights[name] > 0
        },
        "category_mean_scores": {
            k: round(statistics.mean(v), 3) for k, v in sorted(category_scores.items())
        },
        "latency_ms": {
            "mean": round(statistics.mean(latencies_ms), 2) if latencies_ms else 0.0,
            "median": round(statistics.median(latencies_ms), 2) if latencies_ms else 0.0,
        },
    }


def write_checkpoint(
    output: Path,
    *,
    args: argparse.Namespace,
    rows: list[dict],
    total_cases: int,
    category_scores: dict[str, list[float]],
    parse_failures: int,
    validity_mismatches: int,
    execution_mismatches: int,
    latencies_ms: list[float],
    component_totals: dict[str, list[float]],
    hallucinated_entity_cases: int,
    weights: dict[str, float],
    schema_version: str,
) -> dict:
    summary = build_summary(
        args=args,
        rows=rows,
        total_cases=total_cases,
        category_scores=category_scores,
        parse_failures=parse_failures,
        validity_mismatches=validity_mismatches,
        execution_mismatches=execution_mismatches,
        latencies_ms=latencies_ms,
        component_totals=component_totals,
        hallucinated_entity_cases=hallucinated_entity_cases,
        weights=weights,
        schema_version=schema_version,
    )
    result = {"summary": summary, "cases": rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def evaluate(args: argparse.Namespace) -> dict:
    corpus = load_corpus(Path(args.corpus))
    if not corpus:
        raise ValueError("Evaluation corpus is empty.")

    versions = {_schema_version(case) for case in corpus}
    if len(versions) != 1:
        raise ValueError(f"A single evaluation run cannot mix schema versions: {sorted(versions)}")
    schema_version = versions.pop()

    if args.mode == "ollama" and schema_version != "0.2":
        raise ValueError(
            "The active language layer emits Route IR v0.2. Use the frozen v0.1 report for historical baseline evidence rather than rerunning v0.1 through the v0.2 model."
        )

    game = GameDefinition.load(Path(args.game))
    output = Path(args.output)
    weights = weights_for_case(corpus[0])

    rows = []
    category_scores: dict[str, list[float]] = defaultdict(list)
    parse_failures = 0
    validity_mismatches = 0
    execution_mismatches = 0
    latencies_ms: list[float] = []
    component_totals: dict[str, list[float]] = defaultdict(list)
    hallucinated_entity_cases = 0

    total_cases = len(corpus)

    for index, case in enumerate(corpus, 1):
        started = time.perf_counter()
        error = None
        try:
            if args.mode == "golden":
                if schema_version == "0.2":
                    prediction = RouteIR.model_validate(case["expected"])
                else:
                    prediction = LegacyRouteIR.model_validate(case["expected"])
            else:
                from route_ir.llm import interpret_route

                prediction = interpret_route(case["prompt"], game, model=args.model)
        except (ValidationError, Exception) as exc:  # captures local-runtime failures too
            prediction = None
            error = f"{type(exc).__name__}: {exc}"

        elapsed_ms = (time.perf_counter() - started) * 1000
        latencies_ms.append(elapsed_ms)

        if prediction is None:
            parse_failures += 1
            validity_mismatches += 1
            execution_mismatches += 1
            row = {
                "id": case["id"],
                "category": case["category"],
                "score": 0.0,
                "validity_match": False,
                "execution_match": False,
                "latency_ms": round(elapsed_ms, 2),
                "error": error,
                "details": ["No valid RouteIR prediction was produced."],
            }
            # A parse/schema failure is a real zero-score observation, not
            # missing data. Include it in category and component aggregates so
            # summaries cannot silently overstate performance.
            category_scores[case["category"]].append(0.0)
            for name in weights:
                component_totals[name].append(0.0)
        else:
            scored = score_route(case, prediction)

            if schema_version == "0.2":
                validation = validate_route(prediction, game)
                predicted_valid = validation.valid
                predicted_executable = validation.execution_allowed
                expected_valid = bool(case.get("expect_valid", True))
                expected_status = case["expected"].get("status", "READY")
                expected_executable = bool(
                    case.get(
                        "expect_executable",
                        expected_valid and expected_status == RouteStatus.READY.value,
                    )
                )
                validation_issues = [
                    {"level": i.level, "path": i.path, "message": i.message}
                    for i in validation.issues
                ]
            else:
                # Historical v0.1 re-scoring is supported for semantic evidence
                # only. Deterministic validity/execution belongs to the frozen
                # v0.1 report and is not recomputed with the v0.2 validator.
                predicted_valid = bool(case.get("expect_valid", True))
                predicted_executable = predicted_valid
                expected_valid = bool(case.get("expect_valid", True))
                expected_executable = expected_valid
                validation_issues = []

            validity_match = predicted_valid == expected_valid
            execution_match = predicted_executable == expected_executable
            if not validity_match:
                validity_mismatches += 1
            if not execution_match:
                execution_mismatches += 1

            for name, value in scored.components.items():
                component_totals[name].append(value)

            hallucinated = False
            if schema_version == "0.2":
                if prediction.start is not None and prediction.start not in game.starts:
                    hallucinated = True
                for step in prediction.steps:
                    if step.target is not None and step.target not in game.targets:
                        hallucinated = True
                    if step.mechanism is not None:
                        if step.mechanism not in game.mechanisms:
                            hallucinated = True
                        elif (
                            step.mechanism_state is not None
                            and step.mechanism_state not in game.mechanisms[step.mechanism]
                        ):
                            hallucinated = True
                    for constraint in step.constraints:
                        if constraint.target is not None and constraint.target not in game.targets:
                            hallucinated = True
                if prediction.finish:
                    if (
                        prediction.finish.face_target is not None
                        and prediction.finish.face_target not in game.targets
                    ):
                        hallucinated = True
                    if (
                        prediction.finish.near_target is not None
                        and prediction.finish.near_target not in game.targets
                    ):
                        hallucinated = True
            if hallucinated:
                hallucinated_entity_cases += 1

            row = {
                "id": case["id"],
                "category": case["category"],
                "score": scored.total,
                "validity_match": validity_match,
                "execution_match": execution_match,
                "hallucinated_entity": hallucinated,
                "predicted_valid": predicted_valid,
                "expected_valid": expected_valid,
                "predicted_executable": predicted_executable,
                "expected_executable": expected_executable,
                "latency_ms": round(elapsed_ms, 2),
                "error": error,
                "details": scored.details,
                "validation_issues": validation_issues,
                "prediction": prediction.model_dump(mode="json"),
            }
            category_scores[case["category"]].append(scored.total)

        rows.append(row)

        write_checkpoint(
            output,
            args=args,
            rows=rows,
            total_cases=total_cases,
            category_scores=category_scores,
            parse_failures=parse_failures,
            validity_mismatches=validity_mismatches,
            execution_mismatches=execution_mismatches,
            latencies_ms=latencies_ms,
            component_totals=component_totals,
            hallucinated_entity_cases=hallucinated_entity_cases,
            weights=weights,
            schema_version=schema_version,
        )

        status = "OK" if error is None else "ERROR"
        print(
            f"[{index:02d}/{total_cases:02d}] {case['id']}  "
            f"{elapsed_ms / 1000:.1f}s  score={row['score']:.1f}  {status}",
            flush=True,
        )

    return write_checkpoint(
        output,
        args=args,
        rows=rows,
        total_cases=total_cases,
        category_scores=category_scores,
        parse_failures=parse_failures,
        validity_mismatches=validity_mismatches,
        execution_mismatches=execution_mismatches,
        latencies_ms=latencies_ms,
        component_totals=component_totals,
        hallucinated_entity_cases=hallucinated_entity_cases,
        weights=weights,
        schema_version=schema_version,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Route IR interpretation accuracy.")
    parser.add_argument("--mode", choices=["golden", "ollama"], default="golden")
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--game", default=str(DEFAULT_GAME))
    parser.add_argument("--output", default=str(ROOT / "eval_outputs" / "latest_v02.json"))
    args = parser.parse_args()

    result = evaluate(args)

    s = result["summary"]
    print(f"Schema: Route IR v{s['schema_version']}")
    print(f"Cases: {s['cases']}/{s['total_cases']}")
    print(f"Mean semantic score: {s['mean_score']:.3f}/100")
    print(f"Validity accuracy: {s['validity_accuracy']:.3f}%")
    print(f"Execution-gate accuracy: {s['execution_gate_accuracy']:.3f}%")
    print(f"Parse failures: {s['parse_failures']}")
    print(f"Validity mismatches: {s['validity_mismatches']}")
    print(f"Execution mismatches: {s['execution_mismatches']}")
    print(f"Hallucinated-entity cases: {s['hallucinated_entity_cases']}")
    print("Category means:")
    for category, score in s["category_mean_scores"].items():
        print(f"  {category}: {score:.3f}")
    print(f"Report: {Path(args.output)}")


if __name__ == "__main__":
    main()
