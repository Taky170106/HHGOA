#!/usr/bin/env bash
# TigerGraph container environment helper (hhg-tigergraph, CE 4.2.5)
# Sourced inside the container: adds gsql to PATH and defines GSQL alias.
export PATH="$PATH:/home/tigergraph/tigergraph/app/cmd:/home/tigergraph/tigergraph/app/4.2.5"
export HOME=/home/tigergraph
TG_APP=/home/tigergraph/tigergraph/app
GSQL="$TG_APP/cmd/gsql"
