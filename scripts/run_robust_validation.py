"""
CLI Runner for the Robust SAT-SA Validation Protocol (I-02/I-09).

Executes the robust validation protocol.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.evaluation.robust_validation import RobustValidationEngine
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1

def main():
    parser = argparse.ArgumentParser(
        description="SAT-SA Robust Validation Protocol CLI"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="results/robust_validation.json",
        help="Path to save machine-readable JSON results",
    )
    args = parser.parse_args()

    print("================================================================================")
    print("           SAT-SA ROBUST VALIDATION PROTOCOL RUNNER                             ")
    print("================================================================================")
    print("Executing independent evaluation across Tuning and Held-Out scenario splits...")
    print()

    engine = RobustValidationEngine(n_scenarios=240, n_bootstrap=200, ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    result = engine.run(seed=42)
    
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result.to_dict(), f, indent=2)

    print(f"Validation finished. Results saved to {args.output}")
    print(result.limitation_notice)
    
if __name__ == "__main__":
    main()
