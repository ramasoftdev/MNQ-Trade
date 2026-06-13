#!/usr/bin/env python
"""
Run MNQ Monitor (Background Exit Tracking)

Starts the background monitor that continuously checks pending alerts
for SL/TP hits and auto-records exits.

Usage:
  python .claude/skills/run_monitor.py
  Or: /run-monitor in Claude Code
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.monitoring.monitor import main

if __name__ == "__main__":
    main()
