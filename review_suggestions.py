"""Operator CLI: review the drafted (un-sent) suggestions in suggestions.jsonl.

Read-only reporting — it does not send anything. Use it to eyeball reply quality
before ever enabling send-mode.

  python review_suggestions.py
  python review_suggestions.py --path data/suggestions.jsonl --only-confirm
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_suggestions(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def summarize(suggestions: list[dict]) -> dict:
    total = len(suggestions)
    need = sum(1 for s in suggestions if s.get("needs_confirmation"))
    return {"total": total, "needs_confirmation": need, "auto": total - need}


def format_suggestion(i: int, s: dict) -> str:
    flag = "⚠需确认" if s.get("needs_confirmation") else "可自动"
    lines = [
        f"[{i}] {s.get('contact', '?')}  ({flag})",
        f"    收到: {s.get('incoming', '')}",
        f"    建议: {s.get('draft_reply', '')}",
    ]
    if s.get("reason"):
        lines.append(f"    原因: {s.get('reason')}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Review drafted suggestions (read-only)")
    ap.add_argument("--path", default=None, help="path to suggestions.jsonl")
    ap.add_argument("--only-confirm", action="store_true", help="only show items needing confirmation")
    args = ap.parse_args()

    path = args.path
    if path is None:
        from config import Config
        path = Config.SUGGESTIONS_PATH

    suggestions = load_suggestions(path)
    if args.only_confirm:
        suggestions = [s for s in suggestions if s.get("needs_confirmation")]

    if not suggestions:
        print("暂无建议（suggestions.jsonl 为空或不存在）。")
        return

    for i, s in enumerate(suggestions, 1):
        print(format_suggestion(i, s))
        print()

    summ = summarize(load_suggestions(path))
    print(f"共 {summ['total']} 条：{summ['auto']} 条可自动、{summ['needs_confirmation']} 条需人工确认。")


if __name__ == "__main__":
    main()
