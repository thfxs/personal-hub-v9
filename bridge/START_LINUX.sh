#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
echo '[Local-only] 此启动方式仅供电脑本机调试；V9 需使用 START_SECURE_MAC_LINUX.sh。'
exec python3 bridge/server.py --bind 127.0.0.1
