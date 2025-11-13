#!/bin/bash
# Wrapper script to run the bot in native ARM64 mode

cd "$(dirname "$0")"
source venv/bin/activate
arch -arm64 python -u bot.py

