#!/usr/bin/env bash
# Q1 read-only live check: which query definitions actually exist in the
# hhg_fraud_graph catalogue right now? Nothing is created, dropped or executed.
set -u
source /tmp/tg_env.sh

QUERIES=(
  benchmark_case_context
  calculate_exposure
  calculate_exposure_list
  find_device_connections
  find_related_cases
  find_related_transactions
  get_card_history
  get_customer_history
  get_transaction
  temporal_chain
  count_all
  phase2_validate
)

echo "== SHOW QUERY <name> (read-only catalogue inspection) =="
for q in "${QUERIES[@]}"; do
  out=$(gsql -g hhg_fraud_graph "SHOW QUERY $q" </dev/null 2>&1 | sed 's/\x1b\[[0-9;]*[A-Za-z]//g')
  first=$(printf '%s\n' "$out" | head -1)
  if printf '%s' "$out" | grep -qiE 'could not be found|not found'; then
    printf 'NOT_IN_CATALOG  %-28s %s\n' "$q" "$first"
  elif printf '%s' "$out" | grep -qiE 'error'; then
    printf 'ERROR           %-28s %s\n' "$q" "$(printf '%s\n' "$out" | grep -i error | head -1)"
  else
    printf 'PRESENT         %-28s\n' "$q"
  fi
done
echo "Q1_LIVE_CHECK_DONE"
