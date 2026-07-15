#!/bin/zsh

REPO="/Users/william.blatzheim/Documents/projects/billblatzheim-website"
LOG_DIR="$REPO/scripts/logs"
LOG="$LOG_DIR/$(date '+%Y-%m-%d').log"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"

mkdir -p "$LOG_DIR"

{
  echo "=== Daily update started: $(date) ==="

  cd "$REPO" || { echo "FATAL: could not cd to $REPO"; exit 1; }

  echo "--- mlb-newspaper/update.py ---"
  "$PYTHON" mlb-newspaper/update.py
  MLB_STATUS=$?

  echo "--- mlb-newspaper/update_nyt.py ---"
  "$PYTHON" mlb-newspaper/update_nyt.py
  NYT_STATUS=$?

  echo "--- nba-importance/update.py ---"
  "$PYTHON" nba-importance/update.py
  NBA_STATUS=$?

  if [[ $MLB_STATUS -ne 0 || $NYT_STATUS -ne 0 || $NBA_STATUS -ne 0 ]]; then
    echo "WARNING: one or more scripts exited with errors (mlb=$MLB_STATUS nyt=$NYT_STATUS nba=$NBA_STATUS)"
    COMMIT_MSG="Automated update $(date '+%Y-%m-%d') [partial errors]"
  else
    COMMIT_MSG="Automated update $(date '+%Y-%m-%d')"
  fi

  echo "--- git ---"
  GIT_STATUS=0
  if ! git add mlb-newspaper/index.html mlb-newspaper/nyt.html mlb-newspaper/mlb_cache.json nba-importance/; then
    echo "ERROR: git add failed."
    GIT_STATUS=1
  fi

  if [[ $GIT_STATUS -eq 0 ]]; then
    if git diff --cached --quiet; then
      echo "Nothing to commit."
    elif git commit -m "$COMMIT_MSG" && git push; then
      echo "Pushed to GitHub."
    else
      echo "ERROR: git commit/push failed."
      GIT_STATUS=1
    fi
  fi

  echo "=== Done: $(date) ==="

  # macOS notification
  if [[ $MLB_STATUS -eq 0 && $NYT_STATUS -eq 0 && $NBA_STATUS -eq 0 && $GIT_STATUS -eq 0 ]]; then
    osascript -e 'display notification "All scripts ran successfully." with title "Daily Update"'
  else
    osascript -e 'display notification "One or more scripts had errors — check logs." with title "Daily Update ⚠️"'
  fi

} >> "$LOG" 2>&1
