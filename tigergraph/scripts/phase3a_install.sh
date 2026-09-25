#!/usr/bin/env bash
# Phase 3A: drop every diagnostic probe query, then install the five repaired
# investigation queries one at a time. Read-only w.r.t. graph data/schema.
source /tmp/tg_env.sh
cd /home/tigergraph || exit 1

echo "== drop diagnostic probes =="
PROBES=$(gsql -g hhg_fraud_graph 'ls' </dev/null 2>&1 \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' \
  | grep -E '^  - p3[a-z]_' \
  | sed -E 's/^  - ([A-Za-z0-9_]+)\(.*$/\1/')
for n in $PROBES; do
  out=$(gsql -g hhg_fraud_graph "DROP QUERY $n" </dev/null 2>&1 \
        | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | grep -E 'Successfully dropped|could not be found' | tail -1)
  echo "  $n -> $out"
done

echo
echo "== remaining probes (must be empty) =="
gsql -g hhg_fraud_graph 'ls' </dev/null 2>&1 | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' \
  | grep -E '^  - p3[a-z]_' || echo "  (none)"

echo
echo "== install the five repaired queries =="
for q in get_transaction find_related_transactions find_device_connections \
         find_related_cases benchmark_case_context; do
  echo "------------------------------------------------ $q"
  gsql -g hhg_fraud_graph "INSTALL QUERY $q" </dev/null 2>&1 \
    | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | grep -vE '^[[:space:]]*$' | head -8
done

echo
echo "== catalog state =="
gsql -g hhg_fraud_graph 'ls' </dev/null 2>&1 | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' \
  | grep -E '^  - .*\((installed|draft)' | sort
echo "INSTALL_STAGE_DONE"
