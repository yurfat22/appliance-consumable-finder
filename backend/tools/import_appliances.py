import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert an appliances CSV into the JSON format used by the API."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "appliances.csv",
        help="Path to the source CSV (default: backend/data/appliances.csv).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "exports" / "appliances.json",
        help="Path to write the JSON output (default: backend/exports/appliances.json).",
    )
    return parser.parse_args()


def load_rows(csv_path: Path) -> List[Dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"model", "brand", "category", "consumable_name", "consumable_type", "sku"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
        rows = []
        for row in reader:
            if not row.get("model") or not row.get("brand") or not row.get("category"):
                continue
            if not row.get("consumable_name") or not row.get("sku"):
                continue
            rows.append({k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()})
        return rows


def build_structure(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row["model"], row["brand"], row["category"])
        consumable = {
            "name": row["consumable_name"],
            "type": row["consumable_type"],
            "sku": row["sku"],
        }
        if row.get("notes"):
            consumable["notes"] = row["notes"]
        if row.get("purchase_url"):
            consumable["purchase_url"] = row["purchase_url"]
        grouped[key].append(consumable)

    appliances = []
    for (model, brand, category), consumables in grouped.items():
        appliances.append(
            {
                "model": model,
                "brand": brand,
                "category": category,
                "consumables": consumables,
            }
        )

    appliances.sort(key=lambda x: (x["category"], x["brand"], x["model"]))
    return appliances


def main() -> None:
    args = parse_args()
    rows = load_rows(args.input)
    appliances = build_structure(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(appliances, f, indent=2)
    print(f"Wrote {len(appliances)} appliances with consumables to {args.output}")


if __name__ == "__main__":
    main()
