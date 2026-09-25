#!/usr/bin/env bash
source /tmp/tg_env.sh
cd /home/tigergraph || exit 1

for n in p3n_l1 p3n_l2; do
  gsql -g hhg_fraud_graph "DROP QUERY $n" </dev/null 2>&1 \
    | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | grep -E 'Successfully dropped|could not be found' | tail -1
done

gsql -g hhg_fraud_graph "DROP QUERY find_related_transactions" </dev/null 2>&1 \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | grep -E 'Successfully dropped|could not be found' | tail -1

echo "== compile =="
gsql -g hhg_fraud_graph /tmp/queries/find_related_transactions.gsql </dev/null 2>&1 \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | grep -vE '^[[:space:]]*$'

echo "== install =="
gsql -g hhg_fraud_graph "INSTALL QUERY find_related_transactions" </dev/null 2>&1 \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | grep -vE '^[[:space:]]*$' | head -6

echo "== final catalog =="
gsql -g hhg_fraud_graph 'ls' </dev/null 2>&1 | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' \
  | grep -E '^  - .*\((installed|draft)' | sort
echo "STAGE_DONE"
