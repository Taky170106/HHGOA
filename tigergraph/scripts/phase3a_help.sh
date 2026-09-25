#!/usr/bin/env bash
source /tmp/tg_env.sh
for t in select select_statement "select statement" "help" "basic"; do
  echo "=== gsql help $t ==="
  gsql help "$t" </dev/null 2>&1 | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | head -40
  echo
done
