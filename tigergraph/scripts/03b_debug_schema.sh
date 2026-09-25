#!/usr/bin/env bash
source /tmp/tg_env.sh
echo "== run schema file, full output =="
gsql /tmp/schema.gsql
echo "== exit code: $? =="
echo "== ls =="
gsql 'ls'
