"""Run from the repository root: python scripts/start_node.py --id 1 --config ..."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.network.node import main

if __name__ == "__main__":
    main()
