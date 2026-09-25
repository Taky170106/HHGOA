#!/usr/bin/env bash
# Dump every loader 'summary' file (valid/invalid object counts) for observed evidence.
for d in /home/tigergraph/tigergraph/log/fileLoader/*/; do
  s="$d/summary"
  if [ -f "$s" ]; then
    echo "=== $(basename $d) ==="
    cat "$s"
    echo ""
  fi
done
