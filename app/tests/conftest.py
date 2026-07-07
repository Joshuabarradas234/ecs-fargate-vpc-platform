"""
Ensure the app package directory is on sys.path so `import main` works
whether pytest is run from app/ or from the repo root.
"""

import os
import sys

# app/ is the parent of this tests/ directory.
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
