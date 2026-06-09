"""
MNQ Trading Agent — Entry Point
================================
Run the agent with:
  python -m src.core.run

or from project root:
  python src/core/run.py
"""

import sys
from pathlib import Path

# Add project root to path so src can be imported
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    from src.core.agent import main
    main()
