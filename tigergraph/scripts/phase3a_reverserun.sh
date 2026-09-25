#!/usr/bin/env bash
source /tmp/tg_env.sh
cd /home/tigergraph || exit 1

echo "== install the two runtime probes =="
gsql -g hhg_fraud_graph 'INSTALL QUERY p3g_rev, p3g_fwd' </dev/null 2>&1 \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | grep -E 'installed|error|Error' | head -5

echo
echo "== FORWARD: card C12382-K1 -(MADE)-> transactions =="
gsql -g hhg_fraud_graph 'RUN QUERY p3g_fwd("C12382-K1")' </dev/null 2>&1 \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g'

echo
echo "== REVERSE: transaction 3514030 -(<-MADE)- card =="
gsql -g hhg_fraud_graph 'RUN QUERY p3g_rev("3514030")' </dev/null 2>&1 \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g'
echo "RUN_DONE"
