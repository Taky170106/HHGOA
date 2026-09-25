#!/usr/bin/env bash
# Phase B: show schema of hhg_fraud_graph (vertex/edge types) after install.
source /tmp/tg_env.sh
gsql -g hhg_fraud_graph 'SHOW VERTEX *' 2>&1 | head -60
echo "== EDGES =="
gsql -g hhg_fraud_graph 'SHOW EDGE *' 2>&1 | head -60
