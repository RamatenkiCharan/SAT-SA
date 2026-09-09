"""
Utility to export standalone sample dataset bundles to JSON for live UI upload demonstrations.
"""
import json
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from uuid import uuid4
from analytics.synthetic_generator import generate_synthetic_soc_benchmark

def export_sample_bundles():
    out_dir = Path(__file__).resolve().parent.parent / "sample_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Default Multi-Sector Benchmark
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=uuid4(), is_held_out=False)
    file_path1 = out_dir / "multi_sector_soc_benchmark.json"
    with open(file_path1, "w", encoding="utf-8") as f:
        json.dump(raw_bundle, f, indent=2, default=str)
    print(f"Generated: {file_path1}")
    
    # 2. Held-Out Evaluation Dataset
    held_out_bundle, _ = generate_synthetic_soc_benchmark(seed=101, dataset_version_id=uuid4(), is_held_out=True)
    file_path2 = out_dir / "held_out_validation_benchmark.json"
    with open(file_path2, "w", encoding="utf-8") as f:
        json.dump(held_out_bundle, f, indent=2, default=str)
    print(f"Generated: {file_path2}")

if __name__ == "__main__":
    export_sample_bundles()
