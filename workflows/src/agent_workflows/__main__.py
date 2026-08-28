from __future__ import annotations

import argparse
import asyncio

from agent_workflows.workflows.primo_cleanup import run_primo_cleanup_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Primo data cleanup pipeline.")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default="data/sample_extract.csv",
        help="Path to the CSV extract (default: data/sample_extract.csv)",
    )
    args = parser.parse_args()

    outcomes = asyncio.run(run_primo_cleanup_pipeline(args.csv_path))

    print(f"Processed {len(outcomes)} record(s):\n")
    for outcome in outcomes:
        confidence = f"{outcome.confidence:.2f}" if outcome.confidence is not None else "n/a"
        branch = outcome.branch or "n/a (rejected at gate)"
        print(
            f"  record_id={outcome.record_id} policy_id={outcome.policy_id} "
            f"task_type={outcome.task_type} known={outcome.known} "
            f"branch={branch} confidence={confidence}"
        )
        print(f"    {outcome.summary}")


if __name__ == "__main__":
    main()
