"""Tests for observability — run report generation and logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path

from observability import write_run_report, configure_logging


def _make_counts_fn(counts: dict[str, int]):
    return lambda: dict(counts)


class TestWriteRunReport:
    """write_run_report edge cases and output format."""

    def test_writes_report_with_counts(self, tmp_path: Path):
        report_path = tmp_path / "run_report.md"
        result = write_run_report(
            report_path=str(report_path),
            tick_count=5,
            total_scanned=12,
            get_counts_fn=_make_counts_fn({
                "suggested": 8,
                "needs_confirmation": 2,
                "skipped": 3,
                "sent": 0,
            }),
        )
        assert result == report_path
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "Run Report" in content
        assert "8" in content  # suggestions
        assert "2" in content  # needs_confirmation
        assert "5" in content  # ticks
        assert "12" in content  # scanned

    def test_handles_empty_counts(self, tmp_path: Path):
        report_path = tmp_path / "empty.md"
        result = write_run_report(
            report_path=str(report_path),
            tick_count=0,
            total_scanned=0,
            get_counts_fn=_make_counts_fn({}),
        )
        assert result == report_path
        content = report_path.read_text(encoding="utf-8")
        assert "0" in content  # all zeros
        assert "Total processed" in content

    def test_includes_notes(self, tmp_path: Path):
        report_path = tmp_path / "notes.md"
        result = write_run_report(
            report_path=str(report_path),
            tick_count=1,
            total_scanned=3,
            get_counts_fn=_make_counts_fn({"suggested": 1}),
            notes=["DRY_RUN=True", "No API key set"],
        )
        assert result == report_path
        content = report_path.read_text(encoding="utf-8")
        assert "DRY_RUN=True" in content
        assert "No API key set" in content

    def test_creates_parent_directory(self, tmp_path: Path):
        deep_path = tmp_path / "sub" / "nested" / "report.md"
        result = write_run_report(
            report_path=str(deep_path),
            tick_count=1,
            total_scanned=1,
            get_counts_fn=_make_counts_fn({"suggested": 1}),
        )
        assert result == deep_path
        assert deep_path.parent.exists()

    def test_uses_get_counts_fn_lazily(self, tmp_path: Path):
        """The get_counts_fn is called when report is written, not before."""
        call_count = 0

        def lazy_counts():
            nonlocal call_count
            call_count += 1
            return {"suggested": 3}

        report_path = tmp_path / "lazy.md"
        write_run_report(
            report_path=str(report_path),
            tick_count=1,
            total_scanned=3,
            get_counts_fn=lazy_counts,
        )
        assert call_count == 1, "get_counts_fn should be called exactly once"


class TestConfigureLogging:
    """configure_logging setup."""

    def test_console_handler(self):
        """Configure logging without file handler."""
        # Reset root logger for test
        root = logging.getLogger()
        old_handlers = list(root.handlers)
        root.handlers.clear()

        try:
            configure_logging(level=logging.WARNING)
            assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)
            assert root.level == logging.WARNING
        finally:
            root.handlers.clear()
            for h in old_handlers:
                root.addHandler(h)

    def test_file_handler(self, tmp_path: Path):
        """Configure logging with file handler."""
        log_file = tmp_path / "test.log"
        root = logging.getLogger()
        old_handlers = list(root.handlers)
        root.handlers.clear()

        try:
            configure_logging(log_file=str(log_file), level=logging.DEBUG)
            assert log_file.exists()
            assert any(isinstance(h, logging.FileHandler) for h in root.handlers)
        finally:
            root.handlers.clear()
            for h in old_handlers:
                root.addHandler(h)