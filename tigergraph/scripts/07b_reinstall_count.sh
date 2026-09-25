#!/usr/bin/env bash
# Re-create + explicitly install + run count_all.
source /tmp/tg_env.sh
echo "--- drop existing ---"
gsql -g hhg_fraud_graph 'DROP QUERY count_all' 2>&1 | tail -2
echo "--- create ---"
gsql -g hhg_fraud_graph /tmp/count_all.gsql 2>&1 | tail -3
echo "--- install ---"
gsql -g hhg_fraud_graph 'INSTALL QUERY count_all' 2>&1 | tail -5
echo "--- run ---"
gsql -g hhg_fraud_graph 'RUN QUERY count_all()' 2>&1 | sed 's/\x1b\[[0-9;]*[A-Za-z]//g'
