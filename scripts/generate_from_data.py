#!/usr/bin/env python3
"""Generate a guide HTML from an existing *_data.json file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

from generation_pipeline import aggregate_data, generate_html


def generate_from_data(data_path: str, days: int) -> str:
    path = Path(data_path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    destination = data.get("destination") or path.stem.replace("_data", "")
    notes = data.get("notes", [])
    aggregated = aggregate_data(notes, destination)

    saved_aggregated = data.get("aggregated", {}) or {}
    for key in ("spots", "foods", "tips"):
        if saved_aggregated.get(key):
            aggregated[key] = saved_aggregated[key]

    html = generate_html(
        notes,
        aggregated,
        data.get("spot_images", {}),
        destination,
        days,
    )

    output_dir = Path(__file__).parent.parent / "output" / "guides"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{destination}_guide.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(output_path)
    return str(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate HTML from existing scraped data JSON.")
    parser.add_argument("data_path", help="Path to *_data.json")
    parser.add_argument("--days", type=int, default=6)
    args = parser.parse_args()
    generate_from_data(args.data_path, args.days)


if __name__ == "__main__":
    main()
