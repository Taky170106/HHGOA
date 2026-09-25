#!/usr/bin/env bash
# Phase 2: deterministic, dependency-ordered load of hhg_fraud_graph.
# Vertices first (all 8), then edges (all 11). Idempotent: every job upserts by PK,
# so re-running reproduces the same graph state from data/vertices + data/edges.
#
# Usage: bash tigergraph/scripts/17_phase2_load.sh
# Full output: /tmp/phase2_load.log  (copied to tigergraph/validation/phase2_load.log)
set -u
source /tmp/tg_env.sh
cd /home/tigergraph || exit 1

LOG=/tmp/phase2_load.log
: > "$LOG"

RUN() {
  local j="$1"
  echo "===== $j =====" >> "$LOG"
  # shellcheck disable=SC2086
  out=$(gsql -g hhg_fraud_graph "RUN LOADING JOB $j" 2>&1)
  printf '%s\n' "$out" | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' >> "$LOG"
  if printf '%s' "$out" | grep -qiE 'LOAD FAILED|error|invalid|reject'; then
    echo "FLAG: $j"
    printf '%s\n' "$out" | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' \
      | grep -iE 'LOAD FAILED|error|invalid|reject|^[|].*[|]$' | tail -25
  else
    echo "OK: $j"
  fi
}

echo "== VERTICES (dependency order) =="
for j in load_customer load_card load_transaction load_device_profile \
         load_email_domain load_billing_region load_closed_case load_benchmark_case; do
  RUN "$j"
done

echo "== EDGES =="
for j in load_owns load_made load_next load_billed_in load_purchaser_email \
         load_recipient_email load_from_device load_involves load_on_card \
         load_connected_to load_triggers; do
  RUN "$j"
done

echo "== load log: $LOG =="
grep -E 'Load Status|Total|rejected|Invalid|LOAD' "$LOG" | tail -80
echo "PHASE2_LOAD_DONE"
