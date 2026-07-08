#!/usr/bin/env bash
# CI monitor for the overnight Cline build.
# Reports the AUTHORITATIVE GitHub Actions conclusion for the watched branch into
# .ci/STATUS.md (which Cline reads before each task). We report GH Actions rather
# than a local pytest run because the dev machine has extra packages installed
# (e.g. python-dotenv) that the lean CI env does NOT — a local run can be a false
# green. GH Actions installs only requirements-dev.txt, so it is the honest signal.
#
# Usage:  bash .ci/monitor.sh [branch] [interval_seconds]
set -u

REPO="C:/Users/Tung/Documents/GitHub/wechat-smart-bot"
BRANCH="${1:-night-build}"
INTERVAL="${2:-150}"
STATUS="$REPO/.ci/STATUS.md"
HIST="$REPO/.ci/ci_history.log"
BEAT="$REPO/.ci/monitor_heartbeat.txt"

mkdir -p "$REPO/.ci"
last=""
echo "[monitor] reporting GitHub Actions for '$BRANCH' every ${INTERVAL}s" >> "$HIST"

while true; do
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "alive $ts (last=$last)" > "$BEAT"
  cd "$REPO" 2>/dev/null || { sleep "$INTERVAL"; continue; }

  # Latest workflow run for the branch (JSON via gh --jq).
  read -r gid status concl sha title < <(
    gh run list --branch "$BRANCH" --limit 1 \
      --json databaseId,status,conclusion,headSha,displayTitle \
      --jq '"\(.[0].databaseId) \(.[0].status) \(.[0].conclusion) \(.[0].headSha[0:8]) \(.[0].displayTitle)"' 2>/dev/null
  )

  if [ -z "${gid:-}" ] || [ "$gid" = "null" ]; then
    printf '# CI STATUS\n\n_%s_ — no GitHub Actions run found for `%s` yet.\n' "$ts" "$BRANCH" > "$STATUS"
    sleep "$INTERVAL"; continue
  fi

  key="$gid:$status:$concl"
  if [ "$key" = "$last" ]; then
    sleep "$INTERVAL"; continue
  fi
  last="$key"

  if [ "$status" != "completed" ]; then
    result="⏳ IN PROGRESS"; guidance="A CI run is in progress for \`$sha\`. Wait for it before assuming green."
  elif [ "$concl" = "success" ]; then
    result="PASS ✅"; guidance="GitHub Actions is green for \`$sha\`. Continue the next task in TASKS.md."
  else
    result="FAIL ❌"; guidance="GitHub Actions FAILED for \`$sha\`. Fix the errors below, then commit + push. NOTE: a local pytest may pass because this machine has extra deps (e.g. python-dotenv) that the lean CI env lacks — trust CI. Reproduce with only requirements-dev.txt installed."
  fi

  {
    echo "# CI STATUS  (auto-generated from GitHub Actions — do not edit by hand)"
    echo
    echo "- Branch: \`$BRANCH\`  Commit: \`$sha\` — $title"
    echo "- Run: $gid  Status: $status  Conclusion: ${concl:-n/a}"
    echo "- Checked: $ts"
    echo "- Result: **$result**"
    echo
    echo "## Guidance for Cline"
    echo "$guidance"
    if [ "${concl:-}" != "success" ] && [ "$status" = "completed" ]; then
      echo
      echo "## Failing log (excerpt)"
      echo '```'
      gh run view "$gid" --log-failed 2>/dev/null \
        | grep -iE "error|ModuleNotFound|No module|assert|^E |E   |F[0-9]{3}|FAILED|Traceback" \
        | sed 's/^[^Z]*Z //' | head -30
      echo '```'
    fi
  } > "$STATUS"

  echo "$ts  $sha  $result  (run $gid) \"$title\"" >> "$HIST"
  sleep "$INTERVAL"
done
