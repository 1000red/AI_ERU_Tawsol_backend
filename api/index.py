"""Vercel Serverless Function entrypoint for FastAPI."""

import sys
import os

# Ensure backend root is on sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.main import app
