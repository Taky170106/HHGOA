#!/usr/bin/env bash
source /tmp/tg_env.sh
cd /home/tigergraph || exit 1

echo "== install probes =="
gsql -g hhg_fraud_graph 'INSTALL QUERY p3j_in, p3j_inv, p3j_order, p3j_concat2' </dev/null 2>&1 \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | grep -E 'nstalled|rror' | head -5

echo
echo "== p3j_in (attribute join txn 3514030 -> card) =="
gsql -g hhg_fraud_graph 'RUN QUERY p3j_in("3514030")' </dev/null 2>&1 \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | tr -d ' \n' | head -c 600
echo
echo "== p3j_inv (inverted device traversal) =="
gsql -g hhg_fraud_graph 'RUN QUERY p3j_inv("3514030")' </dev/null 2>&1 \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | tr -d ' \n' | head -c 900
echo
echo "== p3j_concat2 (string +) =="
gsql -g hhg_fraud_graph 'RUN QUERY p3j_concat2()' </dev/null 2>&1 \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | tr -d ' \n' | head -c 400
echo
echo "PROBE8_RUN_DONE"
