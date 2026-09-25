#!/usr/bin/env bash
source /tmp/tg_env.sh
cd /home/tigergraph || exit 1
for f in find_device_connections find_related_cases find_related_transactions; do
  echo "===== $f ====="
  gsql -g hhg_fraud_graph "DROP QUERY $f" </dev/null 2>&1 \
    | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | grep -E 'Successfully dropped|could not be found' | tail -1
  gsql -g hhg_fraud_graph "/tmp/queries/$f.gsql" </dev/null 2>&1 \
    | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | grep -vE '^[[:space:]]*$'
  echo
done
echo FULL_ERRORS_DONE
