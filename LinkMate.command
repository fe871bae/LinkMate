#!/bin/bash
# Double-click on a Mac to set up and start LinkMate.

cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if ! python3 --version >/dev/null 2>&1; then
  echo "Python is not installed. Get it from https://www.python.org/downloads/ and start LinkMate again."
  read -r -p "Press Enter to close this window."
  exit 1
fi

python3 start_linkmate.py "$@"
