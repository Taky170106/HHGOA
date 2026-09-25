#!/usr/bin/env bash
# Phase E: install + run count_all validation query, print raw JSON.
source /tmp/tg_env.sh
gsql -g hhg_fraud_graph /tmp/count_all.gsql 2>&1 | tail -3
echo "=== RUN count_all ==="
gsql -g hhg_fraud_graph 'RUN QUERY count_all()' 2>&1 | sed 's/\x1b\[[0-9;]*[A-Za-z]//g'
