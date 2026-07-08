# RUNBOOK — running the vision bot

Python: `C:\Users\Tung\AppData\Local\Python\pythoncore-3.12-64\python.exe`
Install deps once: `python -m pip install -r requirements.txt`

## Safety model (read first)
- Default config is **suggest-only**: `DRY_RUN=True`, `MODE=SUGGEST`. The bot reads and
  **drafts** replies but **sends nothing**. This is enforced in code and asserted by tests.
- Real sending requires ALL of: `MODE=SEND`, `DRY_RUN=false`, the message is not flagged for
  human confirmation, and the safety envelope (`safety.py`) allows it.

## 1. Offline replay (safest — no live window)
Drop some captured `.png` full-window frames into a folder, then:
```
python run_suggest.py --frames data/frames
```
Prints drafted replies and writes them to `data/suggestions.jsonl`. Sends nothing, clicks nothing.
(Capture a frame with: `python wechat_capture.py` → saves `data/capture_test.png`.)

## 2. Live suggest-mode (operator present)
With Weixin open (not minimized) and a conversation you want to test currently open:
```
python run_suggest.py --once
```
It captures the window in the background (no focus steal), lists unread conversations, and
drafts a reply for the **open** conversation into `data/suggestions.jsonl`. Still no sending.
> Note: opening/clicking each unread conversation is the SEND-mode/action-layer job (T8);
> suggest-mode only reads the already-open chat.

## 3. Review suggestions
`data/suggestions.jsonl` — one JSON object per line: contact, incoming, draft_reply,
needs_confirmation, reason. Review quality here before ever enabling sending.

## 4. LATER: enabling send-mode (do this WITH a person watching)
Deliberate, ordered steps — do not automate this:
1. Fill `knowledge_base.md` with real business facts.
2. In `.env`: keep `DRY_RUN=true` first and set a **safe test target** — the very first live
   send must go to **文件传输助手 (File Transfer Helper)**, never a real contact.
3. Wire an actuator via `wechat_actuator.make_actuator(dry_run=Config.DRY_RUN, capture=cap)`.
4. Only after the File-Transfer-Helper round-trips correctly, and behavior looks human, set
   `DRY_RUN=false` + `BOT_MODE=SEND` and start with ONE known-friendly contact.
5. Keep the safety envelope on (business hours, min-gap, hourly cap). `touch data/STOP` is the
   kill-switch — its presence blocks all sends immediately.

## Tests / CI
- `bash .ci/ci_check.sh` runs ruff + the mock test suite (must be green before committing).
- Live-only checks: `python -m pytest --run-live` (needs an open Weixin window).
