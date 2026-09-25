#!/usr/bin/env bash
# Phase A step: list existing graphs + show user.
source /tmp/tg_env.sh
echo "== whoami =="
whoami
echo "== gsql ls =="
gsql 'ls' 2>&1 | head -40
