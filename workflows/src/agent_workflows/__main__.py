from __future__ import annotations

import argparse

from agent_workflows.workflows.dummy_wait import run_dummy_wait


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the dummy wait workflow.")
    parser.add_argument(
        "--seconds",
        type=float,
        default=1.0,
        help="How long to wait (default: 1)",
    )
    args = parser.parse_args()
    result = run_dummy_wait(seconds=args.seconds)
    print(f"status={result.status} seconds={result.seconds}")


if __name__ == "__main__":
    main()
