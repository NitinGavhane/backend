import sys
from pathlib import Path

# __file__ is <root>/backend/api/index.py, so parent.parent is the backend/
# package root that contains app/. Insert it directly on sys.path (the old
# "BASE / backend" pointed at a non-existent nested backend/backend directory).
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

try:
    from app.main import app
except Exception as e:
    import logging
    logging.basicConfig(level=logging.INFO)
    logging.error(f"Failed to import app: {e}")
    raise
