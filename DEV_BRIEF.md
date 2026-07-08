# DEV BRIEF — Overnight autonomous build (for Cline)

You are building the **vision-driven WeChat personal-account auto-reply bot** described in
[SOLUTION.md](SOLUTION.md). Read `SOLUTION.md` first, then this file, then work through
[TASKS.md](TASKS.md) **in order**. A separate CI monitor (run by the operator) tests every
commit and writes feedback to [.ci/STATUS.md](.ci/STATUS.md).

This is an unattended overnight run. Optimize for a **green, well-tested, safe codebase** —
NOT for running the live bot. Correctness and safety over feature count.

---

## 0. HARD SAFETY GUARDRAILS — read every time, never violate

1. **NEVER send a real message to a real contact.** The whole run is *suggest-only / dry-run*.
   The sending code you write must default to `DRY_RUN = True` and a `RecordingActuator`/
   `DryRunActuator` that only *logs* intended actions. Do not flip DRY_RUN off anywhere.
2. **NEVER run the live monitor loop against WeChat for more than a few seconds.** Do not sit
   in a live capture/click loop overnight — that both risks the account and steals the mouse.
   All behavior is validated with **mocks and saved fixtures**, not the live client.
3. **No injection / no DB decryption / no protocol libs.** Do not add `wcferry`, `wxauto`,
   `wxautox`, `pyweixin`, `PyWxDump`, any DLL-injection, memory-reading, or WeChat-DB-decrypt
   dependency. Perception is screenshots + OCR only.
4. **Never commit secrets.** `.env` stays untracked. Do not print or commit API keys, chat
   contents, or captured screenshots (they're gitignored under `data/` — keep it that way).
5. **Stay in your lane.** Work only in the main repo files on branch `night-build`. Do NOT
   touch anything under `.claude/`, do not switch/rebase other branches, do not `git push --force`.
6. **When a task needs a live send, real-account action, or anything risky/uncertain → STOP that
   task.** Append a note to `.ci/BLOCKED.md` (what/why/what you'd need) and move to the next task.

If any instruction here conflicts with a task, the guardrails win.

---

## 1. Operating loop (do this for every task)

1. Open `.ci/STATUS.md`. If Result is **FAIL ❌**, fix those failures first.
2. Pick the next unchecked task in `TASKS.md`. Implement it.
3. Write/extend tests (mock-based, offline). Run the gate until green:
   ```
   bash .ci/ci_check.sh
   ```
   (or: `python -m ruff check .` then `python -m pytest`)
4. Commit small, conventional message, then push:
   ```
   git add -A && git commit -m "feat(vision): ..." && git push
   ```
5. Tick the task's checkbox in `TASKS.md` (commit that too). Move on.

Rules of thumb: **commit after every green task** (don't batch many tasks into one commit).
If you're stuck >20 min on one failure, write to `.ci/BLOCKED.md` and move on. Don't thrash.

---

## 2. Environment

- Python: `C:\Users\Tung\AppData\Local\Python\pythoncore-3.12-64\python.exe` (3.12). Use this exact one.
- Deps already installed: `rapidocr-onnxruntime`, `onnxruntime`, `pywin32`, `numpy`, `Pillow`,
  `pytest`, `ruff`. Runtime deps in `requirements.txt`; CI/test deps in `requirements-dev.txt`.
- Tests must pass **without** a live window or real OCR (both mocked). Live-only checks are
  marked `@pytest.mark.live` and are skipped unless `pytest --run-live` (don't run that in the loop).
- Target client: Weixin 4.1.10.53, window class `Qt51514QWindowIcon`, size sampled at 705x999.

---

## 3. Architecture / module map (build toward this)

Already built (foundation — extend, don't rewrite):
- `wechat_capture.py` — background `PrintWindow(PW_RENDERFULLCONTENT)` capture. **Verified working.**
- `wechat_vision.py` — RapidOCR read + red-badge/change detection + relative `LAYOUT` regions.
- `dryrun_vision.py` — read-only demo.

To build (see TASKS.md for order + acceptance criteria):
- `wechat_reader.py` — high-level read: open-conversation → structured `Message`s; own-vs-other
  bubble discrimination (bubble color / x-position); skip system lines & timestamps.
- `reply_engine.py` — draft a natural-person reply via `llm_client` + `knowledge_base.md` + persona;
  sensitive classification (报价/合同/投诉/退款…). Must accept an injected LLM (mockable).
- `wechat_actuator.py` — `Actuator` interface + `DryRunActuator` (default, logs) + `LiveActuator`
  (SendInput/click/clipboard-paste, human-like timing). LiveActuator is NOT exercised in tests.
- `safety.py` — rate limiter, business-hours gate, existing-conversation-only guard, kill-switch file.
- `bot_core.py` — orchestrator: capture → detect unread → read → draft → classify → route
  (forward to monitor + suggest). Mode: `SUGGEST` (default) vs `SEND` (guarded, off overnight).
- `run_suggest.py` — entrypoint for suggest-only: writes suggestions to `data/suggestions.jsonl`,
  sends nothing.
- Reuse/refactor existing `config.py`, `database.py`, `llm_client.py`, `message_router.py`.

Keep perception, decision, and action **decoupled** so everything is unit-testable with fakes
(see `tests/conftest.py`: `synth_full`, `fake_ocr_lines`, `fake_llm`, `actuator`).

---

## 4. Conventions

- Conventional commits (`feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`).
- Type hints + short docstrings. Keep functions small and injectable (pass deps in).
- New code should pass full `ruff check` (the repo config only enforces a critical subset as a
  baseline gate, but write clean code).
- Don't break the existing green tests. Add tests with each feature.

## 5. Definition of Done (overall, by morning)

- `bash .ci/ci_check.sh` is green; GitHub Actions green.
- P1 (suggest-only) works end-to-end against fixtures: given a captured frame, the bot detects
  unread → reads the message → drafts a persona reply → classifies sensitivity → writes a
  suggestion record + a monitor-forward record. **No real sending anywhere.**
- P2 action layer is fully coded and unit-tested via fakes, but gated (DRY_RUN default), never live.
- `RUNBOOK.md` explains how the operator runs suggest-mode and how send-mode would later be enabled.
- Anything unfinished/risky is listed in `.ci/BLOCKED.md`.
