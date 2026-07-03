from __future__ import annotations

import argparse
import json

from .data_pipeline import run_public_data_pipeline
from .db import init_db
from .engine import latest_report, run_daily_decision
from .reports import ensure_report_exports
from .seed import seed_if_empty


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync public data for SimVest.")
    parser.add_argument("--generate-report", action="store_true", help="Generate a new simulated decision report after syncing.")
    parser.add_argument("--no-snapshot", action="store_true", help="Do not rebuild the market snapshot.")
    args = parser.parse_args()

    init_db()
    seed_if_empty()
    result = run_public_data_pipeline(generate_snapshot=not args.no_snapshot)
    report_id = None
    if args.generate_report:
        report = run_daily_decision()
        ensure_report_exports(report["id"])
        latest = latest_report()
        report_id = latest["id"] if latest else report["id"]

    print(
        json.dumps(
            {
                "sync": result,
                "generated_report_id": report_id,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
