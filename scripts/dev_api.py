"""Run the JSON API locally for the React app: python scripts/dev_api.py [--port 8531].

Runs from the project root so local settings (.env or .streamlit/secrets.toml) are found.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from fip.config import load_dotenv  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8531)
    args = parser.parse_args()
    load_dotenv()
    import uvicorn
    uvicorn.run("fip.api:app", host="127.0.0.1", port=args.port, log_level="warning")
