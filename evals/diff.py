"""Compare two eval result files. Highlight regressions and improvements."""
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        print("Usage: uv run evals/diff.py <prev_results.json> <curr_results.json>")
        sys.exit(1)

    prev = {r["id"]: r["pass_rate"] for r in json.loads(Path(sys.argv[1]).read_text())["results"]}
    curr = {r["id"]: r["pass_rate"] for r in json.loads(Path(sys.argv[2]).read_text())["results"]}

    case_ids = sorted(set(prev) | set(curr))
    regressions = 0
    improvements = 0
    for cid in case_ids:
        p = prev.get(cid, 0.0)
        c = curr.get(cid, 0.0)
        delta = c - p
        if delta < -0.1:
            print(f"  ⚠ {cid}: {p:.0%} → {c:.0%}  REGRESSION")
            regressions += 1
        elif delta > 0.1:
            print(f"  + {cid}: {p:.0%} → {c:.0%}  improved")
            improvements += 1

    print(f"\n{regressions} regression(s), {improvements} improvement(s)")
    sys.exit(1 if regressions else 0)


if __name__ == "__main__":
    main()
