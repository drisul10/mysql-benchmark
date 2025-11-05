#!/bin/bash
#
# MySQL Performance Test Runner
# Automatically uses virtual environment
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv "$VENV_DIR"
    echo "Installing dependencies..."
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

# Run the script with the virtual environment's Python
"$VENV_DIR/bin/python3" "$SCRIPT_DIR/mysql_test.py" "$@"
