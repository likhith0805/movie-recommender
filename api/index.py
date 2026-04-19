from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to Python path for Vercel
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app import create_app

# Initialize the Flask app
app = create_app()

# Vercel serverless function handler
def handler(request):
    """Vercel serverless function handler"""
    return app(request.environ, lambda status, headers: None)

# For local testing
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
