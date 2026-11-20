"""Container liveness and persistence check."""
import os
import sqlite3
from pathlib import Path
from urllib.request import urlopen


def main():
    port = int(os.getenv("PORT", "8501"))
    with urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=3) as response:
        if response.status != 200 or response.read().decode().strip() != "ok":
            raise RuntimeError("Streamlit health check failed")
    path = Path(os.getenv("SLR_DATA_DIR", "data"))
    with sqlite3.connect(path / "slr.sqlite3") as db:
        db.execute("CREATE TABLE IF NOT EXISTS health (id INTEGER PRIMARY KEY)")


if __name__ == "__main__":
    main()
