import os
import sys

# Add the root directory to Python's module search path so we can import app.py correctly on Vercel
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
