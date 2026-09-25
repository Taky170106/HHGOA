#!/usr/bin/env bash
# Phase A step: verify TigerGraph server + gsql client inside container hhg-tigergraph.
set -e
source /tmp/tg_env.sh
echo "== gsql version =="
gsql --version || true
echo "== gsql list graphs (as default user) =="
gsql -g '' 'ls' 2>&1 | head -40 || true
