#!/bin/bash
# Ancilla campaign, family by family (same design as the no-ancilla campaign):
#   per family, 3 concurrent Claude Code sessions (Sonnet 5.5, 3 rounds each):
#     - one anc_shared chain, largest TKET T-count first (its playbook/anc_shared grows as it goes, across families)
#     - two anc_isolated workers (alternate circuits of the same order)
#   then sweep_anc.py over the family: every valid rule of both ancilla playbooks + every run's best.qasm, best per
#   circuit re-verified against the original file -> results/sweep_anc_<family>.csv, results/sweep_anc_<family>/.
# Resumable: a circuit x arm with a finished run (runs/<c>_<arm>_*/best.qasm) is skipped. Account usage limit: the
# run is moved to runs/aborted/, the worker waits 30 min and retries (up to 8 times).
# Usage (from anywhere):  ./campaign/run_anc_campaign.sh     FAMILIES="arithmetic other" ./campaign/run_anc_campaign.sh
# Progress:            python3 campaign/progress.py     (or: watch -n 60 python3 campaign/progress.py)
M="$(cd "$(dirname "$0")/.." && pwd)"; cd "$M"; unset PYTHONSAFEPATH
export PYTHONPATH="$M" CLAUDE_CONFIG_DIR="$M/.cache/claude_config" PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
FAMILIES=${FAMILIES:-"arithmetic other qft_qpe variational hamsim"}
L=logs/campaign_anc; mkdir -p "$L" runs/aborted
caffeinate -i -w $$ 2>/dev/null &                              # keep the Mac awake while this script runs
echo "$(date '+%F %T') campaign start: $FAMILIES" >> "$L/campaign.txt"

run() {  # run CIRCUIT ARM
  if ls runs/$1_$2_*/best.qasm >/dev/null 2>&1; then echo "$(date +%T) skip $1 $2 (done)"; return; fi
  for try in 1 2 3 4 5 6 7 8 9; do
    echo "$(date +%T) start $1 $2"
    out=$(.venv/bin/python agent.py "$1" 3 --arm "$2" 2>&1 | grep -v Warning | tail -3)
    if echo "$out" | grep -q "usage limit"; then
      for d in runs/$1_$2_*; do [ -f "$d/best.qasm" ] || mv "$d" runs/aborted/; done
      echo "$(date +%T) LIMIT $1 $2 (try $try): waiting 30 min"; sleep 1800; continue
    fi
    echo "$out" | tail -1; echo "$(date +%T) end $1 $2"; return
  done
  echo "$(date +%T) GAVE UP $1 $2"
}

for FAM in $FAMILIES; do
  ORDER=$(python3 -c "
import csv, os
rows = [r for r in csv.DictReader(open('benchmarks/MANIFEST.csv')) if r['family'] == '$FAM']
b = 'results/baselines_suite/baselines.csv'                 # largest TKET T-count first, if the baselines are in
T = {r['name']: int(r['T'] or 0) for r in csv.DictReader(open(b)) if r['baseline'] == 'tket'} if os.path.exists(b) else {}
print(' '.join(sorted((r['name'] for r in rows), key=lambda n: -T.get(n, 0))))")
  mkdir -p "$L/$FAM"; echo "$ORDER" > "$L/$FAM/order.txt"
  echo "$(date '+%F %T') family $FAM start: $ORDER" >> "$L/campaign.txt"
  ( for c in $ORDER; do run $c anc_shared; done ) >> "$L/$FAM/shared.txt" 2>&1 &
  ( i=0; for c in $ORDER; do [ $((i % 2)) -eq 0 ] && run $c anc_isolated; i=$((i + 1)); done ) >> "$L/$FAM/isolated_A.txt" 2>&1 &
  ( i=0; for c in $ORDER; do [ $((i % 2)) -eq 1 ] && run $c anc_isolated; i=$((i + 1)); done ) >> "$L/$FAM/isolated_B.txt" 2>&1 &
  wait
  echo "$(date '+%F %T') family $FAM sweep" >> "$L/campaign.txt"
  .venv/bin/python sweep/sweep_anc.py "$FAM" playbook/anc_isolated,playbook/anc_shared --family "$FAM" 2>&1 \
    | grep -v Warning > "$L/$FAM/sweep.txt"
  echo "$(date '+%F %T') family $FAM done" >> "$L/campaign.txt"
done
echo "$(date '+%F %T') CAMPAIGN DONE" >> "$L/campaign.txt"
