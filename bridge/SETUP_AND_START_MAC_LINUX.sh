#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -x '.venv/bin/python' ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r bridge/requirements-security.txt
.venv/bin/python tools/setup_secure_bridge.py
exec bridge/START_SECURE_MAC_LINUX.sh
