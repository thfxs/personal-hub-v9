#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
SECRET_DIR="$HOME/.personal-hub-bridge/security"
if [ ! -s "$SECRET_DIR/server.crt" ] || [ ! -s "$SECRET_DIR/server.key" ] || [ ! -s "$SECRET_DIR/vault-passphrase.txt" ]; then
  echo '尚未初始化电脑安全配置；先运行： python3 tools/setup_secure_bridge.py'
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "请先运行 bridge/SETUP_AND_START_MAC_LINUX.sh 配置隔离的 Python 环境"
  exit 1
fi
exec .venv/bin/python bridge/server.py --tls-cert "$SECRET_DIR/server.crt" --tls-key "$SECRET_DIR/server.key" --vault-passphrase-file "$SECRET_DIR/vault-passphrase.txt"
