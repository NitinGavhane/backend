import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "backend"))

try:
    from app.main import app
except Exception as e:
    import logging
    logging.basicConfig(level=logging.INFO)
    logging.error(f"Failed to import app: {e}")
    raise
