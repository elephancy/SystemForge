#!/bin/sh
set -eu

NGINX_CONFIG=${SYSTEMFORGE_NGINX_CONFIG:-deploy/nginx.conf}

python3 scripts/edge_contract.py "$NGINX_CONFIG"
python3 -m unittest discover -s tests -p test_edge_contract.py
