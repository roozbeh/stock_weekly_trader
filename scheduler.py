import argparse
import logging
import sys
import time
from typing import List, Optional

import schedule

from main import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Market open + 5 min buffer, in US/Eastern — scheduler runs in UTC inside Docker.
# 9:35 ET = 14:35 UTC (EST) / 13:35 UTC (EDT).
# We schedule for 14:35 UTC to be safe year-round in EST; during EDT it fires at 10:35 ET.
# Override with env var SCHEDULE_TIME_UTC (HH:MM).
import os

SCHEDULE_TIME_UTC = os.environ.get("SCHEDULE_TIME_UTC", "14:35")


def _job() -> None:
    logger.info("Scheduled job triggered.")
    try:
        run_pipeline()
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scheduler for weekly swing trade signal generator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run the pipeline immediately instead of waiting for the schedule.",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    if args.now:
        logger.info("--now flag detected, running pipeline immediately.")
        _job()
        sys.exit(0)

    logger.info(
        "Scheduler started. Will run every Monday at %s UTC (env: SCHEDULE_TIME_UTC).",
        SCHEDULE_TIME_UTC,
    )
    schedule.every().monday.at(SCHEDULE_TIME_UTC).do(_job)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
