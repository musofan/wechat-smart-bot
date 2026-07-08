# TASKS — overnight backlog (work top-to-bottom)

Tick a box only when `bash .ci/ci_check.sh` is green AND the commit is pushed.
Every task: add tests (offline/mocked), keep the baseline green. Honor DEV_BRIEF safety guardrails.

## P1 — Suggest-only pipeline (highest priority)

- [x] **T1. Config surface.** Extend `config.py` with typed settings loaded from `.env`/defaults:
  `PERSONA_PROMPT` (natural-person), `MONITOR_ACCOUNT` (default `musomuso`), `BOT_ACCOUNT`
  (`NeXTSCENE小助手`), `SKIP_NAMES` (bots/self/公众号), `GROUP_MARKERS`, `SENSITIVE_KEYWORDS`
  (投诉/退款/赔偿/合同/报价/律师…), `BUSINESS_HOURS`, `SCAN_INTERVAL`, `DRY_RUN=True`, `MODE=SUGGEST`.
  *Done when:* `tests/test_config.py` loads config with env overrides + sane defaults; DRY_RUN defaults True.

- [ ] **T2. Vision hardening.** In `wechat_vision.py`: split name / snippet / timestamp cleanly
  (timestamps like `14:33`, `昨天22:53`, `星期一` must not pollute the name); mark `[图片]/[语音]/
  [文件]/[链接]` snippet types; make `LAYOUT` overridable. Improve first-row grouping (a lone snippet
  shouldn't become the name).
  *Done when:* `tests/test_vision.py` gains cases (mocked OCR) asserting name/snippet/timestamp split
  and media-type tagging; existing tests stay green.

- [ ] **T3. `wechat_reader.py`.** `Message` dataclass (sender: 'me'|'other'|'system', text, kind).
  `read_open_conversation(full_img) -> list[Message]` from the `messages` region; discriminate own
  vs other bubbles by **bubble color / x-position** (own = green, right-aligned); drop timestamps &
  system lines; `latest_inbound()` helper. Header→contact name via `read_header`.
  *Done when:* `tests/test_reader.py` feeds a synthetic message image (draw a right-green + left-grey
  bubble) and asserts correct sender tagging + latest_inbound; OCR mocked.

- [ ] **T4. Knowledge base + `reply_engine.py`.** Flesh out `knowledge_base.md` structure (Q&A/facts;
  the operator fills content later). `ReplyEngine(llm=...)` composes persona + KB into the system
  prompt and returns a reply; `classify(message)` → `{needs_confirmation, reason}` via keywords +
  (injected) LLM. LLM is **injected** (use `fake_llm` in tests).
  *Done when:* `tests/test_reply_engine.py` verifies KB+persona reach the prompt, keyword hits force
  `needs_confirmation`, and no network is used (fake LLM).

- [ ] **T5. Suggestion store.** Extend `database.py` (or `store.py`) with a `suggestions` table +
  `data/suggestions.jsonl` append: {ts, contact, incoming, draft_reply, needs_confirmation, reason,
  status='suggested'}. Dedup by (contact, hash(incoming)).
  *Done when:* `tests/test_store.py` covers insert + dedup + jsonl append (use tmp_path).

- [ ] **T6. `bot_core.py` orchestrator (SUGGEST mode).** Wire it: `Bot(capture, vision, reader,
  reply_engine, store, actuator, config)`; one `tick(full_img)` = detect unread → for each candidate
  (skip self/bots/groups) → read latest inbound → draft → classify → store suggestion + build a
  monitor-forward record. **No sending** (actuator only records). Inject everything.
  *Done when:* `tests/test_bot_core.py` drives `tick()` with `synth_full` + fakes and asserts a
  suggestion is produced and `actuator.actions` contains NO `send`.

- [ ] **T7. `run_suggest.py` entrypoint.** Loop skeleton: locate window → capture → `tick()` →
  write suggestions; guarded by business-hours + `SCAN_INTERVAL`; `--once` flag; `--frames DIR` to
  replay saved fixtures instead of the live window (for safe testing). Prints a summary; sends nothing.
  *Done when:* `tests/test_run_suggest.py` runs `--once --frames <fixtures>` with a saved image and
  asserts suggestions.jsonl is written; no live window needed.

## P2 — Action layer (coded + tested via fakes, gated OFF overnight)

- [ ] **T8. `wechat_actuator.py`.** `Actuator` protocol; `DryRunActuator` (logs intended actions);
  `LiveActuator` using `win32clipboard` paste + `ctypes` `SendInput` + click at (x,y), with
  human-like log-normal delays and optional bezier mouse move. `open_conversation(y)`, `focus_input()`,
  `send_text(text)`. Default factory returns DryRun when `DRY_RUN`.
  *Done when:* `tests/test_actuator.py` asserts `DryRunActuator` records the right action sequence for
  a send; `LiveActuator` is imported but NOT executed (guard with `@pytest.mark.live`).

- [ ] **T9. Safety envelope `safety.py`.** Rate limiter (min gap + per-hour cap), business-hours gate,
  existing-conversation-only guard, and a kill-switch (`data/STOP` file halts sending). `can_send()`
  returns (bool, reason).
  *Done when:* `tests/test_safety.py` covers each gate (freeze time via injected clock).

- [ ] **T10. SEND mode wiring (guarded).** In `bot_core`, add `MODE=SEND` path that, *only if*
  `not DRY_RUN and safety.can_send()`, would call the actuator to reply + forward. Since DRY_RUN is
  True, this path uses the DryRun actuator. Add the human-confirm queue (monitor replies `1`/`2 <text>`/`3`).
  *Done when:* `tests/test_send_flow.py` uses a DryRun actuator + `DRY_RUN=True` and asserts NO real
  send; with an injected fake "live" actuator + `DRY_RUN=False` in-test, asserts the intended
  reply+forward sequence and that safety gates block when they should.

## Hardening

- [ ] **T11. Robustness.** Handle: window not found / minimized, all-black capture (detect blank
  frame), empty-OCR retry, exceptions per-conversation isolated (one bad convo doesn't kill the loop).
  *Done when:* `tests/test_robustness.py` covers blank-frame detection + isolated failure.

- [ ] **T12. Observability.** Structured logging (levels, per-tick summary), and a `data/run_report.md`
  written on exit (counts: scanned/suggested/needs-confirm/skipped).
  *Done when:* a test asserts the report is produced from a fake run.

- [ ] **T13. Docs.** Write `RUNBOOK.md`: how to run `run_suggest.py --once --frames`, how to run live
  suggest-mode (with the operator present), and the exact, deliberate steps to LATER enable send-mode
  (flip DRY_RUN, pick a safe test contact = 文件传输助手 first). Update `README.md` module map.
  *Done when:* files exist and are accurate; links resolve.

- [ ] **T14. Final sweep.** Full `ruff check .` clean on new files; `pytest` all green; remove dead
  code; ensure `.ci/BLOCKED.md` lists anything deferred. Write a short `NIGHT_SUMMARY.md` of what got done.
  *Done when:* green + summary committed + pushed.

---
_If you finish early:_ add more OCR/vision fixture tests from real captures (keep them gitignored),
improve reply quality prompts, or add a tiny CLI to review/approve suggestions. Do NOT enable sending.
