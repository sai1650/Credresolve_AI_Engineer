"""Verify the final CredResolve SmartDialer submission inventory."""

from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).parents[1]


def check(label: str, paths: list[str], required: bool = True) -> bool:
    present = all((ROOT / path).exists() for path in paths)
    status = "PASS" if present or not required else "FAIL"
    qualifier = "" if required else " (optional)"
    print(f"{status}: {label}{qualifier}")
    if not present and required:
        print("  missing:", ", ".join(paths))
    return present or not required


def main() -> int:
    checks = [
        (
            "application directories",
            [
                "app",
                "app/data",
                "app/dialer",
                "app/ml",
                "app/providers",
                "app/safety",
                "app/simulation",
            ],
        ),
        (
            "core source",
            [
                "app/data/normalization.py",
                "app/data/features.py",
                "app/data/feature_pipeline.py",
            ],
        ),
        (
            "prediction source",
            [
                "app/ml/model.py",
                "app/ml/train.py",
                "app/ml/predictor.py",
                "app/ml/evaluation.py",
            ],
        ),
        (
            "dialer and safety source",
            [
                "app/dialer/predictive.py",
                "app/dialer/allocator.py",
                "app/safety/controller.py",
            ],
        ),
        (
            "progressive and agent state source",
            ["app/dialer/progressive.py", "app/state/agent_state.py"],
        ),
        ("API source", ["app/main.py"]),
        (
            "provider source",
            [
                "app/providers/base.py",
                "app/providers/provider_a.py",
                "app/providers/provider_b.py",
                "app/providers/events.py",
                "app/providers/manager.py",
            ],
        ),
        (
            "simulation source",
            [
                "app/simulation/simulator.py",
                "app/simulation/scenarios.py",
                "app/simulation/metrics.py",
                "app/simulation/runner.py",
                "app/simulation/load_test.py",
                "app/simulation/failure_tests.py",
            ],
        ),
        (
            "canonical and modeling data",
            [
                "data/processed/canonical_calls.csv",
                "data/processed/modeling_dataset.csv",
                "data/processed/feature_report.json",
            ],
        ),
        (
            "trained model and reports",
            [
                "models/answer_probability_model.joblib",
                "data/processed/model_report.json",
                "data/processed/load_test_report.json",
            ],
        ),
        (
            "raw datasets",
            [
                "data/accounts.csv",
                "data/calls.csv",
                "data/call_attempts.csv",
                "data/call_dispositions.csv",
            ],
        ),
        (
            "tests",
            [
                "tests/test_features.py",
                "tests/test_predictor.py",
                "tests/test_training.py",
                "tests/test_predictive_pacing.py",
                "tests/test_safety_controller.py",
                "tests/test_allocator.py",
                "tests/test_allocator_concurrency.py",
                "tests/test_providers.py",
                "tests/test_provider_events.py",
                "tests/test_simulation.py",
                "tests/test_load.py",
                "tests/test_failure_recovery.py",
                "tests/test_api.py",
                "tests/test_progressive_and_state.py",
            ],
        ),
        (
            "documentation",
            [
                "README.md",
                "docs/architecture.md",
                "docs/architecture-decisions.md",
                "docs/agent-state-machine.md",
                "docs/call-state-machine.md",
                "docs/submission-checklist.md",
                "docs/interview-notes.md",
            ],
        ),
        (
            "simulation scripts",
            ["scripts/run_simulation.py", "scripts/demo_providers.py"],
        ),
        (
            "dashboard",
            [
                "dashboard/package.json",
                "dashboard/index.html",
                "dashboard/src/main.jsx",
                "dashboard/src/styles.css",
            ],
        ),
        ("optional requirements file", ["requirements.txt"], False),
    ]
    normalized = [
        (item[0], item[1], item[2] if len(item) == 3 else True)
        for item in checks
    ]
    passed = sum(
        check(label, paths, required) for label, paths, required in normalized
    )
    credential_pattern = re.compile(
        r"api[_-]?key|secret|password|passwd|bearer\s+token|private_key",
        re.IGNORECASE,
    )
    suspicious = []
    for path in (ROOT / "app",):
        for source in path.rglob("*.py"):
            for line_number, line in enumerate(
                source.read_text(encoding="utf-8").splitlines(), 1
            ):
                if credential_pattern.search(line):
                    suspicious.append(f"{source}:{line_number}")
    if not suspicious:
        print("PASS: no credential-like patterns in application source")
    else:
        print("FAIL: credential-like patterns found")
    if suspicious:
        print("  ", "\n  ".join(suspicious))
        passed = 0
    print(f"Project check: {passed}/{len(normalized)} checks satisfied")
    return 0 if passed == len(normalized) else 1


if __name__ == "__main__":
    raise SystemExit(main())
