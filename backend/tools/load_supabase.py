import argparse
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import psycopg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load appliance models and consumables into Supabase (Postgres)."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to appliances.json (optional if only loading contractor data).",
    )
    parser.add_argument(
        "--contractor",
        type=Path,
        default=None,
        help="Path to contractor.json (optional).",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Postgres connection string (defaults to DATABASE_URL env var).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for bulk inserts.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate existing tables before loading.",
    )
    return parser.parse_args()


def chunked(items: List[Tuple], size: int) -> Iterable[List[Tuple]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def load_appliances(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    return data


def load_contractor(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in {path}")
    return data


def normalize_key(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def build_consumable_key(row: dict) -> str:
    sku = normalize_key(row.get("sku"))
    if sku:
        return f"sku:{sku}"
    name = normalize_key(row.get("name"))
    ctype = normalize_key(row.get("type"))
    return f"name:{name}|type:{ctype}"


def connect(dsn: str) -> psycopg.Connection:
    sslmode = os.getenv("PGSSLMODE", "require")
    return psycopg.connect(dsn, sslmode=sslmode)


def main() -> None:
    args = parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL is required.")

    if not args.input and not args.contractor:
        raise SystemExit("Provide --input and/or --contractor.")

    appliances: List[dict] = []
    if args.input:
        if not args.input.exists():
            raise SystemExit(f"Missing input file: {args.input}")
        appliances = load_appliances(args.input)

    contractor: Optional[dict] = None
    if args.contractor:
        if not args.contractor.exists():
            raise SystemExit(f"Missing contractor file: {args.contractor}")
        contractor = load_contractor(args.contractor)

    brands: Set[str] = set()
    categories: Set[str] = set()
    consumables: Dict[str, dict] = {}

    for item in appliances:
        brand = str(item.get("brand", "")).strip()
        category = str(item.get("category", "")).strip()
        if brand:
            brands.add(brand)
        if category:
            categories.add(category)
        for consumable in item.get("consumables", []) or []:
            key = build_consumable_key(consumable)
            if key not in consumables:
                consumables[key] = {
                    "name": str(consumable.get("name", "")).strip(),
                    "type": str(consumable.get("type", "")).strip(),
                    "sku": str(consumable.get("sku", "")).strip() or None,
                    "purchase_url": str(consumable.get("purchase_url", "")).strip() or None,
                }

    with connect(args.database_url) as conn:
        with conn.cursor() as cur:
            if args.truncate:
                cur.execute(
                    "TRUNCATE model_consumables, models, consumables, brands, categories, contractors RESTART IDENTITY CASCADE"
                )

            if brands:
                cur.executemany(
                    "INSERT INTO brands (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                    [(name,) for name in sorted(brands)],
                )
            if categories:
                cur.executemany(
                    "INSERT INTO categories (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                    [(name,) for name in sorted(categories)],
                )

            cur.execute("SELECT id, name FROM brands")
            brand_map = {row[1]: row[0] for row in cur.fetchall()}

            cur.execute("SELECT id, name FROM categories")
            category_map = {row[1]: row[0] for row in cur.fetchall()}

            consumable_rows = []
            if consumables:
                consumable_rows = [
                    (row["name"], row["type"], row["sku"], row["purchase_url"])
                    for row in consumables.values()
                    if row["name"] and row["type"]
                ]
                for chunk in chunked(consumable_rows, args.batch_size):
                    cur.executemany(
                        """
                        INSERT INTO consumables (name, type, sku, purchase_url)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (sku) DO UPDATE SET
                            name = EXCLUDED.name,
                            type = EXCLUDED.type,
                            purchase_url = COALESCE(consumables.purchase_url, EXCLUDED.purchase_url)
                        """,
                        chunk,
                    )

            cur.execute("SELECT id, sku, name, type FROM consumables")
            consumable_map: Dict[str, int] = {}
            for row in cur.fetchall():
                sku = normalize_key(row[1])
                if sku:
                    key = f"sku:{sku}"
                else:
                    key = f"name:{normalize_key(row[2])}|type:{normalize_key(row[3])}"
                consumable_map.setdefault(key, row[0])

            model_rows: List[Tuple[int, int, str]] = []
            if appliances:
                seen_models: Set[Tuple[int, int, str]] = set()
                for item in appliances:
                    brand = str(item.get("brand", "")).strip()
                    category = str(item.get("category", "")).strip()
                    model_number = str(item.get("model", "")).strip()
                    if not brand or not category or not model_number:
                        continue
                    brand_id = brand_map.get(brand)
                    category_id = category_map.get(category)
                    if not brand_id or not category_id:
                        continue
                    key = (brand_id, category_id, model_number)
                    if key in seen_models:
                        continue
                    seen_models.add(key)
                    model_rows.append(key)

                for chunk in chunked(model_rows, args.batch_size):
                    cur.executemany(
                        """
                        INSERT INTO models (brand_id, category_id, model_number)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (brand_id, category_id, model_number) DO NOTHING
                        """,
                        chunk,
                    )

            cur.execute("SELECT id, brand_id, category_id, model_number FROM models")
            model_map = {
                (row[1], row[2], row[3]): row[0]
                for row in cur.fetchall()
            }

            model_consumable_rows: List[Tuple[int, int, Optional[str]]] = []
            if appliances:
                seen_links: Set[Tuple[int, int]] = set()
                for item in appliances:
                    brand = str(item.get("brand", "")).strip()
                    category = str(item.get("category", "")).strip()
                    model_number = str(item.get("model", "")).strip()
                    if not brand or not category or not model_number:
                        continue
                    brand_id = brand_map.get(brand)
                    category_id = category_map.get(category)
                    model_id = model_map.get((brand_id, category_id, model_number))
                    if not model_id:
                        continue
                    for consumable in item.get("consumables", []) or []:
                        key = build_consumable_key(consumable)
                        consumable_id = consumable_map.get(key)
                        if not consumable_id:
                            continue
                        link_key = (model_id, consumable_id)
                        if link_key in seen_links:
                            continue
                        seen_links.add(link_key)
                        notes = str(consumable.get("notes", "")).strip() or None
                        model_consumable_rows.append((model_id, consumable_id, notes))

                for chunk in chunked(model_consumable_rows, args.batch_size):
                    cur.executemany(
                        """
                        INSERT INTO model_consumables (model_id, consumable_id, notes)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (model_id, consumable_id) DO NOTHING
                        """,
                        chunk,
                    )

            contractor_loaded = 0
            if contractor:
                cur.execute(
                    """
                    INSERT INTO contractors (
                        name, company, phone, email, service_area, license, photo, bio
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        contractor.get("name"),
                        contractor.get("company"),
                        contractor.get("phone"),
                        contractor.get("email"),
                        contractor.get("service_area"),
                        contractor.get("license"),
                        contractor.get("photo"),
                        contractor.get("bio"),
                    ),
                )
                contractor_loaded = 1

        conn.commit()

    print(
        "Loaded brands={brands} categories={categories} models={models} consumables={consumables} links={links} contractors={contractors}".format(
            brands=len(brands),
            categories=len(categories),
            models=len(model_rows),
            consumables=len(consumable_rows),
            links=len(model_consumable_rows),
            contractors=contractor_loaded,
        )
    )


if __name__ == "__main__":
    main()
