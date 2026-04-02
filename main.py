import argparse
import logging
import sys
from typing import List, Optional

from analyzer import run_analysis
from report import generate_report
from signals import generate_signals
from watchlist import get_symbols

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Weekly swing trade signal generator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full pipeline but skip saving the HTML report to disk.",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        metavar="TICKER",
        default=None,
        help="Override watchlist with specific ticker symbols.",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=4,
        metavar="N",
        help="Minimum signal score to include in output.",
    )
    return parser.parse_args(argv)


def run_pipeline(
    dry_run: bool = False,
    symbols: Optional[List[str]] = None,
    min_score: int = 4,
) -> int:
    target_symbols = symbols if symbols else get_symbols()
    logger.info(
        "Starting pipeline: %d symbols, min_score=%d, dry_run=%s",
        len(target_symbols),
        min_score,
        dry_run,
    )

    candidates = run_analysis(symbols=target_symbols, min_score=min_score)
    if not candidates:
        logger.warning("No candidates met the score threshold of %d.", min_score)

    signals = generate_signals(candidates)
    report_path = generate_report(signals, dry_run=dry_run)

    if report_path:
        logger.info("Report written to: %s", report_path)

    return 0


def main() -> None:
    args = parse_args()
    exit_code = run_pipeline(
        dry_run=args.dry_run,
        symbols=args.symbols,
        min_score=args.min_score,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
