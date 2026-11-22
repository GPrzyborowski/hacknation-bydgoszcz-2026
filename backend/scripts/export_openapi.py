"""Zapisuje specyfikację OpenAPI (Swagger) do docs/openapi.json — do przejrzenia bez uruchamiania backendu.

    python backend/scripts/export_openapi.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "app"))

from main import app  # noqa: E402

OUTPUT = ROOT / "docs" / "openapi.json"

if __name__ == "__main__":
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Zapisano {OUTPUT.relative_to(ROOT)} — endpointów: {sum(len(ops) for ops in app.openapi()['paths'].values())}")
