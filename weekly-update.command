#!/bin/zsh
cd "$(dirname "$0")"
python3 update_stats.py
echo
read "?Done — press Enter to close this window."
