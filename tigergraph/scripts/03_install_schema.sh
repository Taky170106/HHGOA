#!/usr/bin/env bash
# Phase B: install the Phase-1 schema (8 vertices, 11 edges, 1 graph) into hhg-tigergraph.
set -e
source /tmp/tg_env.sh
echo "== whoami =="
whoami
echo "== installing schema =="
gsql /tmp/schema.gsql 2>&1 | tail -40
echo "== verify: list graphs =="
gsql 'ls' 2>&1 | head -30
