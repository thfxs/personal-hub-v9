#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
echo '[Local-only] 此启动方式仅供电脑本机 HTTP 调试；V9 需使用 START_SECURE_MAC_LINUX.sh。'
python3 bridge/server.py --bind 127.0.0.1
printf '\n按回车键关闭窗口...'
read -r
