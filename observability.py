"""Observability — structured logging and run-report generation.

Provides helpers to write a ``data/run_report.md`` after each run with counts
of conversations scanned, suggestions made, and items needing confirmation.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


def write_run_report(
    report_path: str | Path,
    tick_count: int,
    total_scanned: int,
    get_counts_fn: Callable[[], dict[str, int]],
    *,
    notes: list[str] | None = None,
) -> Path:
    """Write a run report markdown file with summary statistics.

    Args:
        report_path: Destination file path (e.g. ``data/run_report.md``).
        tick_count: Number of ticks executed in this run.
        total_scanned: Total conversations scanned across all ticks.
        get_counts_fn: Callable returning dict with keys like
            ``suggested``, ``needs_confirmation``, ``skipped``, ``sent``.
        notes: Optional list of additional notes to append to the report.

    Returns:
        The resolved Path to the written report.
    """
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    counts = get_counts_fn()
    suggested = counts.get("suggested", 0)
    needs_confirm = counts.get("needs_confirmation", 0)
    skipped = counts.get("skipped", 0)
    sent = counts.get("sent", 0)
    total = suggested + skipped + sent

    lines = [
        "# Run Report",
        "",
        f"- **Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Ticks**: {tick_count}",
        f"- **Conversations scanned**: {total_scanned}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Suggestions created | {suggested} |",
        f"| Needs confirmation | {needs_confirm} |",
        f"| Skipped (dup/skip) | {skipped} |",
        f"| Sent | {sent} |",
        f"| **Total processed** | {total} |",
        "",
    ]
    if notes:
        lines.append("## Notes\n")
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Run report written to %s", path)
    return path


def configure_logging(
    log_file: str | Path | None = None,
    level: int = logging.INFO,
) -> None:
    """Configure structured logging to console and optionally to a file.

    Args:
        log_file: Optional path to a file for persistent logs.
        level: Logging level (default: INFO).
    """
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
    ]
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(str(log_path), encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )