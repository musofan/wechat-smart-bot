#!/usr/bin/env bash
# Continuous CI monitor for the overnight Cline build.
# Watches a branch for new commits, runs ruff+pytest against each new commit in a
# throwaway *detached* worktree (so it never collides with Cline's checkout), and
# writes the result to .ci/STATUS.md (which Cline reads before each task).
#
# Usage:  bash .ci/monitor.sh [branch] [interval_seconds]
set -u

REPO="C:/Users/Tung/Documents/GitHub/wechat-smart-bot"
PY="C:/Users/Tung/AppData/Local/Python/pythoncore-3.12-64/python.exe"
BRANCH="${1:-night-build}"
INTERVAL="${2:-180}"
WORK="C:/Users/Tung/AppData/Local/Temp/claude/ci-worktree"
STATUS="$REPO/.ci/STATUS.md"
HIST="$REPO/.ci/ci_history.log"
BEAT="$REPO/.ci/monitor_heartbeat.txt"

last=""
mkdir -p "$REPO/.ci" "$REPO/data" 2>/dev/null
echo "[monitor] watching '$BRANCH' every ${INTERVAL}s; python=$PY" >> "$HIST"

while true; do
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  mkdir -p "$REPO/.ci" 2>/dev/null
  echo "alive $ts (last=$last)" > "$BEAT"
  cd "$REPO" 2>/dev/null || { sleep "$INTERVAL"; continue; }

  sha="$(git rev-parse --verify "$BRANCH" 2>/dev/null)"
  if [ -z "$sha" ]; then
    # branch not created yet — Cline hasn't started
    printf '# CI STATUS\n\n_%s_ — branch `%s` not found yet (Cline not started).\n' "$ts" "$BRANCH" > "$STATUS"
    sleep "$INTERVAL"; continue
  fi

  if [ "$sha" = "$last" ]; then
    sleep "$INTERVAL"; continue
  fi
  last="$sha"
  subject="$(git log -1 --pretty=%s "$sha" 2>/dev/null)"

  # fresh detached worktree at this commit
  git worktree remove --force "$WORK" >/dev/null 2>&1
  rm -rf "$WORK" >/dev/null 2>&1
  git worktree prune >/dev/null 2>&1
  if ! git worktree add --detach --force "$WORK" "$sha" >/dev/null 2>&1; then
    printf '# CI STATUS\n\n_%s_ — could not create worktree for %s\n' "$ts" "${sha:0:8}" > "$STATUS"
    sleep "$INTERVAL"; continue
  fi

  cd "$WORK"
  ruff_out="$("$PY" -m ruff check . 2>&1)"; ruff_rc=$?
  test_out="$("$PY" -m pytest 2>&1)"; test_rc=$?
  cd "$REPO"
  git worktree remove --force "$WORK" >/dev/null 2>&1
  rm -rf "$WORK" >/dev/null 2>&1

  if [ $ruff_rc -eq 0 ] && [ $test_rc -eq 0 ]; then
    result="PASS ✅"
    guidance="Baseline is green. Continue the next task in TASKS.md."
  else
    result="FAIL ❌"
    guidance="Fix the failures below BEFORE starting the next task. Run \`bash .ci/ci_check.sh\` locally until green, then commit."
  fi

  {
    echo "# CI STATUS  (auto-generated — do not edit by hand)"
    echo
    echo "- Commit: \`${sha:0:8}\` — $subject"
    echo "- Checked: $ts"
    echo "- Result: **$result**"
    echo
    echo "## Guidance for Cline"
    echo "$guidance"
    if [ "$result" != "PASS ✅" ]; then
      echo
      echo "## ruff (rc=$ruff_rc)"
      echo '```'
      echo "$ruff_out" | tail -40
      echo '```'
      echo "## pytest (rc=$test_rc)"
      echo '```'
      echo "$test_out" | tail -60
      echo '```'
    fi
  } > "$STATUS"

  echo "$ts  ${sha:0:8}  $result  \"$subject\"" >> "$HIST"
  sleep "$INTERVAL"
done
