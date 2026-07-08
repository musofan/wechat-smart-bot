"""Tiny run-report accumulator written on exit for the operator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunReport:
    scanned: int = 0
    suggested: int = 0
    needs_confirm: int = 0
    skipped: int = 0
    errors: int = 0

    def to_markdown(self, title: str = "Suggest-mode run report") -> str:
        return (
            f"# {title}\n\n"
            f"- 扫描的会话 scanned: {self.scanned}\n"
            f"- 生成建议 suggested: {self.suggested}\n"
            f"- 需人工确认 needs_confirm: {self.needs_confirm}\n"
            f"- 跳过 skipped: {self.skipped}\n"
            f"- 错误 errors: {self.errors}\n"
        )

    def write(self, path: str, title: str = "Suggest-mode run report"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(self.to_markdown(title), encoding="utf-8")
