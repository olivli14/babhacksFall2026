"""Run both agents LIVE on the Gemini sandbox for a few minutes (see live.py).

Usage: python scripts/live_demo.py [seconds=300]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from live import LiveRun  # noqa: E402

if __name__ == "__main__":
    run = LiveRun(int(sys.argv[1]) if len(sys.argv) > 1 else 300, echo=True)
    try:
        run.run()
    except KeyboardInterrupt:
        run.stop()
        run.cleanup()
