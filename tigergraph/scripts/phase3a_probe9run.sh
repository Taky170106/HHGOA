#!/usr/bin/env bash
source /tmp/tg_env.sh
cd /home/tigergraph || exit 1

echo "== install inverted-traversal probes =="
gsql -g hhg_fraud_graph 'INSTALL QUERY p3k_k3, p3k_k4' </dev/null 2>&1 \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | grep -E 'nstalled|rror' | head -5

echo
echo "== k3: SELECT SOURCE alias after forward hop (txn 3514030) =="
gsql -g hhg_fraud_graph 'RUN QUERY p3k_k3("3514030")' </dev/null 2>&1 \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | tr -d ' \n' | head -c 500
echo
echo "== k4: same via IN @@set =="
gsql -g hhg_fraud_graph 'RUN QUERY p3k_k4("3514030")' </dev/null 2>&1 \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | tr -d ' \n' | head -c 700
echo
echo "PROBE9_RUN_DONE"
