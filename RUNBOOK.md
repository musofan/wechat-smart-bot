# RUNBOOK — WeChat Smart Bot (night-build)

This runbook describes how to operate the bot in **SUGGEST mode** (the only mode active in this
overnight build). No real messages are ever sent — the bot only reads, drafts, and saves suggestions.

---

## 1. Offline / Fixture Mode (safe, no live window)

```bash
python run_suggest.py --once --frames data/
```

- Reads all `.png` images from `data/` as synthetic chat list + open conversation captures.
- Runs one tick and exits.
- Suggestions are written to `data/suggestions.jsonl` and an in-memory SQLite DB.
- A run report is written to `data/run_report.md`.
- **No real WeChat window is touched; no mouse/keyboard events are emitted.**

To point at a different set of fixtures:

```bash
python run_suggest.py --frames path/to/screenshots/
```

---

## 2. Live Suggest Mode (with operator present)

**Prerequisites:**

1. Weixin (WeChat desktop, version 4.x) is **unlocked and visible on the primary monitor**.
2. The chat list is showing (not minimized, not covered by other windows).
3. The operator must be present to observe and approve (or kill) the process.

```bash
python run_suggest.py
```

- Starts a loop that captures the chat list every `SCAN_INTERVAL` seconds (default: 10).
- For each conversation with an unread badge, reads the latest inbound message, drafts a reply,
  classifies risk, and saves a suggestion.
- **No message is ever sent.** The loop only records suggestions.
- Press `Ctrl+C` to stop. A run report is written on exit.

For a single-tick live run:

```bash
python run_suggest.py --once
```

---

## 3. What happens when the bot runs

1. **Capture** → takes a screenshot of the WeChat window.
2. **Detect unread** → finds conversations with unread badge icons.
3. **Skip lists** → skips:
   - Self / bot accounts (`SKIP_NAMES`)
   - Group chats (names starting with `GROUP_MARKERS`)
   - Known public accounts / bots
4. **Read conversation** → for each unread candidate, simulates opening it, reads the latest
   inbound message bubble.
5. **Draft reply** → `ReplyEngine` composes a reply using persona + knowledge base + LLM.
6. **Classify** → checks sensitive keywords; if flagged, marks `needs_confirmation=True`.
7. **Store** → saves to SQLite + JSONL.
8. **Repeat** → after processing all candidates, re-captures the chat list (if loop mode).

---

## 4. Configuration

All settings live in `config.py`, loaded from `.env` (if present) or defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `DRY_RUN` | `True` | **Must stay `True`** in overnight build — prevents any sending |
| `MODE` | `SUGGEST` | Operation mode: `SUGGEST` or `SEND` (SEND gated OFF) |
| `SCAN_INTERVAL` | `10` | Seconds between chat-list capture cycles |
| `BUSINESS_HOURS` | `09:00-22:00` | Hour range to allow processing |
| `SKIP_NAMES` | ... | Comma-separated names to skip (self, bots) |
| `GROUP_MARKERS` | `▸` | Prefixes that indicate a group chat |
| `SENSITIVE_KEYWORDS` | ... | Triggers `needs_confirmation` flag |
| `SENSENOVA_API_KEY` | — | Required for real LLM; if unset, uses stub |

---

## 5. Safety Notes (action layer)

The **P2 action layer** (`send_text`, `open_conversation`, `focus_input`) is implemented in
`wechat_actuator.py` but:

- `DRY_RUN=True` (default) means the factory returns `DryRunActuator` — it logs but does nothing.
- `LiveActuator` exists but is **never invoked** during this overnight build.
- The `Safety` envelope (`safety.py`) is wired into SEND mode but **SEND mode is Off**.

### To later enable send-mode (DO NOT DO OVERNIGHT)

1. Deploy and test with `文件传输助手` first (safe, self-targeted).
2. Set `DRY_RUN=False` in `.env`.
3. Set `MODE=SEND` in `.env`.
4. Ensure `data/STOP` kill-switch is absent (if present, sending is blocked).
5. Stay present to monitor every action.

---

## 6. Output Files

| Path | Description |
|------|-------------|
| `data/suggestions.jsonl` | Append-only log of every suggestion (one JSON per line) |
| `data/run_report.md` | Summary report written on exit |
| `data/STOP` | If this file exists, the safety layer blocks all sends (P2) |

---

## 7. Monitoring Observability

- Structured logging: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
- Each tick logs: `Tick #N: X unread, Y suggested (total Z suggestions)`
- Exit report at `data/run_report.md` includes:
  - Tick count and conversations scanned
  - Suggestions created / needs_confirmation / skipped

---

## 8. Running Tests

```bash
# Full mock suite (no live window, no real LLM):
python -m pytest

# With coverage:
python -m pytest --cov=.

# Ruff lint:
python -m ruff check .
```

All tests are offline / mocked — no network, no real WeChat.