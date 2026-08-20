from app.simulation.load_test import (
    LoadTestConfig,
    run_load_matrix,
    run_load_test,
)


def test_baseline_load_invariants():
    report = run_load_test(LoadTestConfig(workers=5, seed=42))
    assert report["calls_created"] == 100
    assert report["duplicate_jobs"] >= 1
    assert report["invariant_violations"] == []
    assert report["p95_allocation_latency_seconds"] >= 0


def test_worker_scale_matrix_is_reproducible():
    first = run_load_matrix((5, 10, 20, 50))
    second = run_load_matrix((5, 10, 20, 50))
    for workers in ("5", "10", "20", "50"):
        assert first[workers]["calls_created"] == 100
        assert first[workers]["invariant_violations"] == []
        assert (
            first[workers]["calls_created"] == second[workers]["calls_created"]
        )


def test_load_has_no_network_dependency():
    text = open("app/simulation/load_test.py", encoding="utf-8").read()
    assert "requests." not in text
    assert "socket" not in text
