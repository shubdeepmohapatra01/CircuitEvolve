#!/bin/zsh
# Overnight guard for P2: keeps the Mac awake while P2 runs and resumes P2 if it exits for a harness reason or
# dies without finishing (max 3 restarts). Never restarts after a usage-limit / credential stop or a STOP file.
#   nohup zsh v3/agent/watchdog.sh > v3/results/p2/watchdog.log 2>&1 &
cd "$(dirname "$0")/../.."
restarts=0
while true; do
  pid=$(pgrep -f "v3.agent.run" | head -1)
  if [[ -z "$pid" ]]; then
    stopped=$(.venv/bin/python -c "import json;print(json.load(open('v3/results/p2/state.json')).get('stopped') or '')")
    done_all=$(.venv/bin/python -c "import json;s=json.load(open('v3/results/p2/state.json'));print(all(s['done'][l]>=b for l,b in s['plan']))")
    echo "$(date) P2 not running; stopped='$stopped' all_done=$done_all restarts=$restarts"
    if [[ "$done_all" == "True" || "$stopped" == usage-limit* || -e v3/results/p2/STOP || $restarts -ge 3 ]]; then
      echo "$(date) watchdog exits"; exit 0
    fi
    restarts=$((restarts + 1))
    echo "$(date) restarting P2 ($restarts/3)"
    nohup .venv/bin/python -m v3.agent.run >> v3/results/p2/run_watchdog.log 2>&1 &
    sleep 10
    continue
  fi
  caffeinate -ims -w "$pid"          # holds the no-sleep assertion until this P2 process exits
done
