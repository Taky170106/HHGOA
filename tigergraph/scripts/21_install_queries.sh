#!/usr/bin/env bash
# Phase 2: deploy the existing investigation query files into TigerGraph.
# These queries were authored in Phase 1/2 (tigergraph/queries/*.gsql); the MCP live
# path calls them by name (RESTPP /query/hhg_fraud_graph/<name>), so they must be
# installed for the graph interface to be usable. Nothing here is newly authored.
set -u
source /tmp/tg_env.sh
cd /home/tigergraph || exit 1

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
)

echo "== drop (ignore 'not found') =="
for q in "${QUERIES[@]}"; do
  gsql -g hhg_fraud_graph "DROP QUERY $q" </dev/null 2>&1 | grep -E 'Successfully dropped|could not be found' | tail -1
done

echo "== create from files =="
for f in benchmark_case_context calculate_exposure find_device_connections \
         find_related_cases find_related_transactions get_card_history \
         get_customer_history get_transaction temporal_chain; do
  echo "-- $f.gsql"
  gsql -g hhg_fraud_graph "/tmp/queries/$f.gsql" </dev/null 2>&1 | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | grep -E 'Successfully created|error|Error|Semantic' | tail -4
done

echo "== install all =="
gsql -g hhg_fraud_graph 'INSTALL QUERY ALL' </dev/null 2>&1 | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | tail -8
echo "QUERY_INSTALL_DONE"
