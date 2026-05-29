#!/bin/bash
# Stop any old deploy script still running
pkill -f "deploy.command" 2>/dev/null
sleep 1

# Change to this script's folder
cd "$(dirname "$0")"

# Run the fully automated deploy
python3 auto_deploy.py
