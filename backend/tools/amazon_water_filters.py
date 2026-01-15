import argparse
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from urllib import request

import psycopg


DEFAULT_HOST = os.getenv("AMAZON_PAAPI_HOST", "webservices.amazon.com")
DEFAULT_REGION = os.getenv("AMAZON_PAAPI_REGION", "us-east-1")
DEFAULT_MARKETPLACE = os.getenv("AMAZON_PAAPI_MARKETPLACE", "www.amazon.com")
DEFAULT_SEARCH_INDEX = os.getenv("AMAZON_PAAPI_SEARCH_INDEX", "Appliances")
AFFILIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG", "be3857-20")

CONTENT_ENCODING = "amz-1.0"
CONTENT_TYPE = "application/json; charset=utf-8"
SERVICE = "ProductAdvertisingAPI"
TARGET = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"


@dataclass
class PaapiConfig:
    access_key: str
    secret_key: str
    partner_tag: str
    host: str = DEFAULT_HOST
    region: str = DEFAULT_REGION
    marketplace: str = DEFAULT_MARKETPLACE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search Amazon for refrigerator water filters and insert results into Postgres."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Postgres connection string (defaults to DATABASE_URL env var).",
    )
    parser.add_argument(
        "--access-key",
        default=os.getenv("AMAZON_PAAPI_ACCESS_KEY"),
        help="Amazon PA-API access key.",
    )
    parser.add_argument(
        "--secret-key",
        default=os.getenv("AMAZON_PAAPI_SECRET_KEY"),
        help="Amazon PA-API secret key.",
    )
    parser.add_argument(
        "--partner-tag",
        default=os.getenv("AMAZON_ASSOCIATE_TAG"),
        help="Amazon associate tag (defaults to AMAZON_ASSOCIATE_TAG).",
    )
    parser.add_argument(
        "--marketplace",
        default=DEFAULT_MARKETPLACE,
        help="Marketplace domain (default: www.amazon.com).",
    )
    parser.add_argument(
        "--search-index",
        default=DEFAULT_SEARCH_INDEX,
        help="PA-API search index (default: Appliances).",
    )
    parser.add_argument(
        "--category",
        default="refrigerator",
        help="Category name to target (default: refrigerator).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Max models to process (default: 100).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between API calls in seconds (default: 1.0).",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only process models with no existing water filter link.",
    )
    parser.add_argument(
        "--require-filter",
        action="store_true",
        help="Only accept items with 'water' + 'filter' in the title.",
    )
    parser.add_argument(
        "--progress-file",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "exports"
        / "amazon_water_filters_progress.json",
        help="JSON file used to track progress and resume runs.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not resume from an existing progress file.",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Reprocess models that previously errored in the progress file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log results without writing to the database.",
    )
    return parser.parse_args()


def sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def get_signature_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = sign(k_date, region)
    k_service = sign(k_region, service)
    k_signing = sign(k_service, "aws4_request")
    return k_signing


def build_amazon_product_url(asin: str, tag: str) -> str:
    return f"https://www.amazon.com/dp/{asin}?tag={tag}"


def add_amazon_affiliate_tag(url: Optional[str], tag: str) -> Optional[str]:
    if not url:
        return url
    cleaned = url.strip()
    if not cleaned:
        return None
    # Only append tag if it is missing.
    if "amazon." not in cleaned:
        return cleaned
    if "tag=" in cleaned:
        return cleaned
    joiner = "&" if "?" in cleaned else "?"
    return f"{cleaned}{joiner}tag={tag}"


def make_signed_headers(
    method: str, uri: str, host: str, payload: str, config: PaapiConfig
) -> Dict[str, str]:
    amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    date_stamp = amz_date[:8]

    canonical_headers = (
        f"content-encoding:{CONTENT_ENCODING}\n"
        f"content-type:{CONTENT_TYPE}\n"
        f"host:{host}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-target:{TARGET}\n"
    )
    signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"
    payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    canonical_request = "\n".join(
        [
            method,
            uri,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    credential_scope = f"{date_stamp}/{config.region}/{SERVICE}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signing_key = get_signature_key(config.secret_key, date_stamp, config.region, SERVICE)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={config.access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    return {
        "Content-Encoding": CONTENT_ENCODING,
        "Content-Type": CONTENT_TYPE,
        "Host": host,
        "X-Amz-Date": amz_date,
        "X-Amz-Target": TARGET,
        "Authorization": authorization,
    }


def search_items(
    keywords: str, config: PaapiConfig, search_index: str, item_count: int = 5
) -> Dict[str, object]:
    payload = {
        "Keywords": keywords,
        "SearchIndex": search_index,
        "ItemCount": item_count,
        "PartnerTag": config.partner_tag,
        "PartnerType": "Associates",
        "Marketplace": config.marketplace,
        "Resources": ["ItemInfo.Title", "Offers.Listings.Price"],
    }
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    uri = "/paapi5/searchitems"
    url = f"https://{config.host}{uri}"
    headers = make_signed_headers("POST", uri, config.host, body, config)
    req = request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
    with request.urlopen(req) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def extract_item(items: Sequence[dict], require_filter: bool) -> Optional[dict]:
    if not items:
        return None
    if not require_filter:
        return items[0]
    for item in items:
        title = (
            item.get("ItemInfo", {})
            .get("Title", {})
            .get("DisplayValue", "")
            .lower()
        )
        if "water" in title and "filter" in title:
            return item
    return None


def load_models(
    cur: psycopg.Cursor, category: str, limit: int, only_missing: bool
) -> List[Tuple[int, str, str]]:
    if only_missing:
        cur.execute(
            """
            SELECT m.id, m.model_number, b.name
            FROM models m
            JOIN categories c ON m.category_id = c.id
            JOIN brands b ON m.brand_id = b.id
            LEFT JOIN model_consumables mc ON mc.model_id = m.id
            LEFT JOIN consumables cons ON cons.id = mc.consumable_id
              AND LOWER(cons.name) LIKE '%water filter%'
            WHERE LOWER(c.name) = %s
              AND COALESCE(m.water_filter_missing, false) = false
            GROUP BY m.id, m.model_number, b.name
            HAVING COUNT(cons.id) = 0
            ORDER BY b.name, m.model_number
            LIMIT %s
            """,
            (category.lower(), limit),
        )
    else:
        cur.execute(
            """
            SELECT m.id, m.model_number, b.name
            FROM models m
            JOIN categories c ON m.category_id = c.id
            JOIN brands b ON m.brand_id = b.id
            WHERE LOWER(c.name) = %s
            ORDER BY b.name, m.model_number
            LIMIT %s
            """,
            (category.lower(), limit),
        )
    return cur.fetchall()


def upsert_consumable(
    cur: psycopg.Cursor,
    name: str,
    asin: str,
    purchase_url: Optional[str],
) -> int:
    cur.execute(
        """
        INSERT INTO consumables (name, type, asin, sku, purchase_url)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (asin) DO UPDATE SET
            name = EXCLUDED.name,
            type = EXCLUDED.type,
            purchase_url = COALESCE(EXCLUDED.purchase_url, consumables.purchase_url)
        RETURNING id
        """,
        (name, "filter", asin, None, purchase_url),
    )
    return cur.fetchone()[0]


def link_consumable(
    cur: psycopg.Cursor, model_id: int, consumable_id: int, notes: Optional[str]
) -> None:
    cur.execute(
        """
        INSERT INTO model_consumables (model_id, consumable_id, notes)
        VALUES (%s, %s, %s)
        ON CONFLICT (model_id, consumable_id) DO NOTHING
        """,
        (model_id, consumable_id, notes),
    )


def ensure_water_filter_column(cur: psycopg.Cursor, allow_write: bool) -> None:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'models'
          AND column_name = 'water_filter_missing'
        """
    )
    exists = cur.fetchone() is not None
    if exists:
        return
    if not allow_write:
        raise SystemExit(
            "models.water_filter_missing is missing. Run a migration or rerun without --dry-run."
        )
    cur.execute(
        """
        ALTER TABLE models
        ADD COLUMN IF NOT EXISTS water_filter_missing BOOLEAN NOT NULL DEFAULT FALSE
        """
    )


def set_water_filter_missing(cur: psycopg.Cursor, model_id: int, missing: bool) -> None:
    cur.execute(
        "UPDATE models SET water_filter_missing = %s WHERE id = %s",
        (missing, model_id),
    )


def load_progress(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {"models": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"models": {}}
    if not isinstance(data, dict):
        return {"models": {}}
    if "models" not in data or not isinstance(data.get("models"), dict):
        data["models"] = {}
    return data


def write_progress(path: Path, data: Dict[str, object]) -> None:
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
    tmp_path.replace(path)


def should_skip_model(
    progress_models: Dict[str, object], model_id: int, retry_errors: bool
) -> bool:
    entry = progress_models.get(str(model_id))
    if not entry:
        return False
    status = ""
    if isinstance(entry, dict):
        status = str(entry.get("status", ""))
    if retry_errors and status == "error":
        return False
    return True


def update_progress_entry(
    progress_models: Dict[str, object],
    model_id: int,
    model_number: str,
    brand: str,
    status: str,
    asin: Optional[str] = None,
    title: Optional[str] = None,
    detail_url: Optional[str] = None,
    message: Optional[str] = None,
) -> None:
    entry: Dict[str, object] = {
        "model_number": model_number,
        "brand": brand,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if asin:
        entry["asin"] = asin
    if title:
        entry["title"] = title
    if detail_url:
        entry["detail_url"] = detail_url
    if message:
        entry["message"] = message
    progress_models[str(model_id)] = entry


def main() -> None:
    args = parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL is required.")
    if not args.access_key or not args.secret_key:
        raise SystemExit("AMAZON_PAAPI_ACCESS_KEY and AMAZON_PAAPI_SECRET_KEY are required.")
    partner_tag = args.partner_tag or AFFILIATE_TAG
    if not partner_tag:
        raise SystemExit("AMAZON_ASSOCIATE_TAG (partner tag) is required.")

    config = PaapiConfig(
        access_key=args.access_key,
        secret_key=args.secret_key,
        partner_tag=partner_tag,
        marketplace=args.marketplace,
    )

    with psycopg.connect(args.database_url, sslmode=os.getenv("PGSSLMODE", "require")) as conn:
        with conn.cursor() as cur:
            ensure_water_filter_column(cur, allow_write=not args.dry_run)
            conn.commit()

            progress_data: Dict[str, object] = {"models": {}}
            resume = not args.no_resume
            progress_path = args.progress_file
            if resume and progress_path:
                progress_data = load_progress(progress_path)
            progress_models: Dict[str, object] = progress_data.get("models", {})

            models = load_models(cur, args.category, args.limit, args.only_missing)
            print(f"Loaded {len(models)} models (category={args.category}).")

            processed = 0
            added = 0
            skipped = 0
            for model_id, model_number, brand in models:
                if resume and should_skip_model(progress_models, model_id, args.retry_errors):
                    skipped += 1
                    continue

                processed += 1
                keywords = f"{model_number} water filter"
                try:
                    response = search_items(keywords, config, args.search_index)
                except Exception as exc:
                    print(f"[{processed}/{len(models)}] ERROR {model_number}: {exc}")
                    update_progress_entry(
                        progress_models,
                        model_id,
                        model_number,
                        brand,
                        "error",
                        message=str(exc),
                    )
                    if progress_path:
                        write_progress(progress_path, progress_data)
                    if args.delay:
                        time.sleep(args.delay)
                    continue

                items = response.get("SearchResult", {}).get("Items", [])
                item = extract_item(items, args.require_filter)
                if not item:
                    print(f"[{processed}/{len(models)}] SKIP {model_number}: no match")
                    update_progress_entry(
                        progress_models,
                        model_id,
                        model_number,
                        brand,
                        "no_match",
                    )
                    if not args.dry_run:
                        set_water_filter_missing(cur, model_id, True)
                        conn.commit()
                    if progress_path:
                        write_progress(progress_path, progress_data)
                    if args.delay:
                        time.sleep(args.delay)
                    continue

                asin = item.get("ASIN")
                title = (
                    item.get("ItemInfo", {})
                    .get("Title", {})
                    .get("DisplayValue", "Water filter")
                )
                if not asin:
                    print(f"[{processed}/{len(models)}] SKIP {model_number}: missing ASIN")
                    update_progress_entry(
                        progress_models,
                        model_id,
                        model_number,
                        brand,
                        "missing_asin",
                        title=title,
                    )
                    if not args.dry_run:
                        set_water_filter_missing(cur, model_id, True)
                        conn.commit()
                    if progress_path:
                        write_progress(progress_path, progress_data)
                    if args.delay:
                        time.sleep(args.delay)
                    continue

                detail_url = item.get("DetailPageURL")
                purchase_url = add_amazon_affiliate_tag(detail_url, partner_tag)
                if not purchase_url:
                    purchase_url = build_amazon_product_url(asin, partner_tag)

                note = f"Auto-added from Amazon search for model {model_number}."
                if args.dry_run:
                    print(f"[{processed}/{len(models)}] DRY {model_number} -> {asin} {title}")
                    update_progress_entry(
                        progress_models,
                        model_id,
                        model_number,
                        brand,
                        "found",
                        asin=asin,
                        title=title,
                        detail_url=detail_url,
                    )
                    if progress_path:
                        write_progress(progress_path, progress_data)
                else:
                    consumable_id = upsert_consumable(cur, title, asin, purchase_url)
                    link_consumable(cur, model_id, consumable_id, note)
                    set_water_filter_missing(cur, model_id, False)
                    conn.commit()
                    added += 1
                    print(f"[{processed}/{len(models)}] OK {model_number} -> {asin}")
                    update_progress_entry(
                        progress_models,
                        model_id,
                        model_number,
                        brand,
                        "found",
                        asin=asin,
                        title=title,
                        detail_url=detail_url,
                    )
                    if progress_path:
                        write_progress(progress_path, progress_data)

                if args.delay:
                    time.sleep(args.delay)

    print(
        "Done. Processed={processed} Added/Linked={added} Skipped={skipped}".format(
            processed=processed,
            added=added,
            skipped=skipped,
        )
    )


if __name__ == "__main__":
    main()
