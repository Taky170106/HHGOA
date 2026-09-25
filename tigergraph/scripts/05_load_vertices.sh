#!/usr/bin/env bash
# Phase D: run the vertex loading jobs and print a compact success/error summary.
source /tmp/tg_env.sh
cd /home/tigergraph || exit 1
JOBS="load_billing_region load_closed_case load_card load_benchmark_case load_email_domain load_customer load_device_profile load_transaction"
for j in $JOBS; do
  echo "=== $j ==="
  out=$(gsql -g hhg_fraud_graph "RUN LOADING JOB $j" 2>&1)
  echo "$out" | grep -E 'LOAD SUCCESSFUL|LOAD FAILED|ERRORS|\| *[a-z_]+\.csv' | tail -6
  echo "$out" | grep -E 'LOAD FAILED' >/dev/null && echo "JOB_FAILED: $j" && exit 2
done
echo "ALL_VERTEX_JOBS_DONE"
