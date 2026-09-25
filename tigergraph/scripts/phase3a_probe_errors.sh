#!/usr/bin/env bash
# Phase 3A step 1: capture the EXACT GSQL compiler output for each of the five
# non-installed investigation queries, using the same invocation that the Phase 2
# deploy script (21_install_queries.sh) used successfully.
# Graph data is never touched: a failing CREATE QUERY only records a draft.
set -u
source /tmp/tg_env.sh
cd /home/tigergraph || exit 1

LOG=/tmp/phase3a_probe.log
: > "$LOG"

for f in benchmark_case_context find_device_connections find_related_cases find_related_transactions get_transaction; do
  {
    echo "################ FILE: $f.gsql ################"
    gsql -g hhg_fraud_graph "/tmp/queries/$f.gsql" </dev/null 2>&1 \
      | sed 's/\x1b\[[0-9;]*[A-Za-z]//g'
    echo "----- end $f -----"
    echo
  } >> "$LOG" 2>&1
done

echo PROBE_DONE
cat "$LOG"
