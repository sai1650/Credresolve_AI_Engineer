"""Run the complete deterministic SmartDialer simulation."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.simulation.runner import print_results, run

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["A", "B", "C", "D"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    names = [args.scenario] if args.scenario else None
    print_results(run(names, args.seed))
