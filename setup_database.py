#!/usr/bin/env python3
"""
Database initialization script for Heroku deployment.
This script will be run automatically when the app starts.
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.init_db import main as init_db_main

def main():
    """Initialize database if it doesn't exist."""
    db_path = os.environ.get('DATABASE_PATH', 'backend/data/movies.db')
    
    # Check if database exists
    if not os.path.exists(db_path):
        print("Initializing database...")
        init_db_main()
        print("Database initialized successfully!")
    else:
        print("Database already exists.")

if __name__ == "__main__":
    main()
