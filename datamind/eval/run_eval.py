"""DataMind: Automated evaluation benchmark comparing Agent queries against Ground Truth."""

import argparse
import os
import sys
import time
import yaml
from typing import Any, List
from dotenv import load_dotenv

from datamind.config import load_config
from datamind.snowflake_client import SnowflakeClient
from datamind.schema import build_schema_text
from datamind.agent import answer

load_dotenv()

# Ensure safe UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def normalize_val(val: Any) -> str:
    """Normalize values for robust equality comparison (float precision, string stripping)."""
    if val is None:
        return "NULL"
    try:
        f = float(val)
        return str(round(f, 2))
    except (ValueError, TypeError):
        return str(val).strip().upper()


def rows_match(agent_rows: List[List[Any]], truth_rows: List[List[Any]]) -> bool:
    """Check if agent result rows match ground truth rows regardless of ordering."""
    if len(agent_rows) != len(truth_rows):
        return False

    norm_agent = sorted(["|".join(normalize_val(c) for c in r) for r in agent_rows])
    norm_truth = sorted(["|".join(normalize_val(c) for c in r) for r in truth_rows])
    return norm_agent == norm_truth


def run(
    cfg_path: str = "configs/tpch.yaml",
    eval_path: str = "eval/golden_tpch.yaml",
    limit: int = 0,
):
    """Run golden evaluation suite."""
    print("=" * 70)
    print("🧠 DataMind Evaluation Benchmark (Ground Truth Verification)")
    print("=" * 70)

    cfg = load_config(cfg_path)
    sf = SnowflakeClient()
    schema_text = build_schema_text(cfg, sf)

    with open(eval_path, "r", encoding="utf-8") as f:
        cases = yaml.safe_load(f)

    if limit > 0:
        cases = cases[:limit]

    total = len(cases)
    passed = 0
    start_time = time.time()

    print(f"Target Dataset: {cfg.database}.{cfg.schema_}")
    print(f"Total Test Cases: {total}")
    print("-" * 70)

    for i, c in enumerate(cases, 1):
        q = c["question"]
        truth_sql = c["truth_sql"]

        try:
            truth_res = sf.run(truth_sql)
            truth_rows = truth_res.get("rows", [])
        except Exception as e:
            print(f"[{i:02d}/{total:02d}] ⚠️ TRUTH ERROR: {q} -> {e}")
            continue

        agent_res = answer(q, cfg, sf, schema_text)

        ok = False
        if agent_res.get("type") == "ok":
            agent_rows = agent_res.get("rows", [])
            ok = rows_match(agent_rows, truth_rows)

        if ok:
            passed += 1
            print(f"[{i:02d}/{total:02d}] ✅ PASS | {q}")
        else:
            print(f"[{i:02d}/{total:02d}] ❌ FAIL | {q}")
            print(f"    Expected SQL : {truth_sql}")
            print(f"    Agent SQL    : {agent_res.get('sql')}")
            print(f"    Agent Type   : {agent_res.get('type')}")
            if agent_res.get("message"):
                print(f"    Agent Message: {agent_res.get('message')}")

    duration = time.time() - start_time
    pct = (passed / total) * 100 if total > 0 else 0

    print("=" * 70)
    print(f"Benchmark Results: {passed}/{total} Passed ({pct:.1f}%) in {duration:.2f}s")
    if pct >= 85.0:
        print("Rubric Band: 🌟 Outstanding (85-100%)")
    elif pct >= 60.0:
        print("Rubric Band: 👍 Good (60-84%)")
    elif pct >= 25.0:
        print("Rubric Band: ⚠️ Acceptable (25-59%)")
    else:
        print("Rubric Band: ❌ Poor (0-24%) - Attention: Trust Cap Risk")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run DataMind Evaluation Benchmark")
    parser.add_argument("--config", default="configs/tpch.yaml", help="Path to dataset YAML config")
    parser.add_argument("--eval", default="eval/golden_tpch.yaml", help="Path to golden questions YAML")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of cases to test")
    args = parser.parse_args()

    run(cfg_path=args.config, eval_path=args.eval, limit=args.limit)
