"""FastAPI read-only dashboard API over simulation components."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.providers.provider_a import ProviderA
from app.providers.provider_b import ProviderB
from app.providers.manager import ProviderManager
from app.simulation.runner import run

app = FastAPI(title="CredResolve SmartDialer")


class SimulationRequest(BaseModel):
    scenario: str = "A"
    seed: int = 42


_last_results: list[dict] = run(["A"], 42)


def _latest() -> dict:
    return _last_results[0]


@app.get("/api/dashboard/summary")
def dashboard_summary() -> dict:
    result = _latest()
    return {"scenario": result["scenario"], **result}


@app.get("/api/pacing/current")
def current_pacing() -> dict:
    result = _latest()
    return result["pacing_log"][-1] if result["pacing_log"] else {}


@app.get("/api/metrics")
def metrics() -> dict:
    return _latest()


@app.get("/api/calls")
def calls() -> list[dict]:
    return []


@app.get("/api/agents")
def agents() -> list[dict]:
    return []


@app.get("/api/providers")
def providers() -> dict:
    manager = ProviderManager([ProviderA(seed=42), ProviderB(seed=43)])
    return {name: health.__dict__ for name, health in manager.health().items()}


@app.post("/api/simulation/run")
def run_simulation(request: SimulationRequest) -> dict:
    global _last_results
    if request.scenario not in {"A", "B", "C", "D"}:
        raise HTTPException(status_code=400, detail="unknown scenario")
    _last_results = run([request.scenario], request.seed)
    return _latest()
