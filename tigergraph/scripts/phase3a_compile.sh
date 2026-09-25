#!/usr/bin/env bash
# Phase 3A: compile the five repaired investigation queries. CREATE QUERY only -
# no install, and no vertex/edge data is touched.
set -u
source /tmp/tg_env.sh
cd /home/tigergraph || exit 1

QUERIES=(benchmark_case_context find_device_connections find_related_cases
         find_related_transactions get_transaction)

echo "== drop stale drafts =="
for q in "${QUERIES[@]}"; do
  printf '  %-28s ' "$q"
  gsql -g hhg_fraud_graph "DROP QUERY $q" </dev/null 2>&1 \
    | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' \
    | grep -E 'Successfully dropped|could not be found' | tail -1
done

echo
echo "== compile =="
for f in "${QUERIES[@]}"; do
  echo "------------------------------------------------------------ $f.gsql"
  gsql -g hhg_fraud_graph "/tmp/queries/$f.gsql" </dev/null 2>&1 \
    | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' \
    | grep -E 'Successfully created|Syntax Error|Type Check Error|Saved as draft|Parsing encountered|In the FROM clause|mixed usage|neither a vertex|cannot find any compatible|cannot be reached' \
    | head -12
done
echo "COMPILE_STAGE_DONE"
