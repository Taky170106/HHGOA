#!/usr/bin/env bash
# Inspect loader logs for load_card + load_benchmark_case (observed evidence, read-only).
for job in load_card load_benchmark_case; do
  d=$(ls -td /home/tigergraph/tigergraph/log/fileLoader/*${job}* 2>/dev/null | head -1)
  echo "=== $job dir: $d ==="
  if [ -n "$d" ]; then
    ls -la "$d"
    for f in "$d"/*; do
      echo "--- file: $f ---"
      head -c 1200 "$f"
      echo ""
    done
  fi
done
