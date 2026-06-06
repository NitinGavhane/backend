import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from app.main import app
except Exception as e:
    import logging
    logging.basicConfig(level=logging.INFO)
    logging.error(f"Failed to import app: {e}")
    raise
