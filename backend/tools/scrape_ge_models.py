import argparse
import json
import re
import time
from pathlib import Path
from typing import List, Set
from urllib import request


DEFAULT_BASE_URL = (
    "https://www.whirlpoolparts.com/PartSearch/ProductBrandAllModels?brandId=3&productId=4"
)
PAGE_PATTERN = re.compile(r"[?&]n=(\d+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape appliance model numbers from WhirlpoolParts and save them locally."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Base URL for the brand/model list.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help="Total pages to scrape (default: auto-detect from page 1).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.25,
        help="Delay between page requests in seconds (default: 0.25).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "exports" / "ge_models.json",
        help="Output JSON path.",
    )
    return parser.parse_args()


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.whirlpoolparts.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    req = request.Request(url, headers=headers)
    with request.urlopen(req) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_models(html: str, brand: str) -> List[str]:
    brand_slug = re.escape(brand)
    pattern = re.compile(rf"/Model-([A-Za-z0-9-]+?)-{brand_slug}-", re.IGNORECASE)
    return pattern.findall(html)


def parse_brand_type(html: str) -> tuple[str, str]:
    for pattern in [r"<h1[^>]*>(.*?)</h1>", r"<title>(.*?)</title>"]:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group(1))).strip()
        parsed = re.match(
            r"^(?:ALL\s+)?([A-Za-z0-9&]+)\s+(.+?)\s+MODELS$",
            text,
            re.IGNORECASE,
        )
        if parsed:
            brand = parsed.group(1).strip()
            appliance_type = parsed.group(2).strip()
            if text.isupper():
                if brand.isupper() and len(brand) > 2:
                    brand = brand.title()
                appliance_type = appliance_type.title()
            return brand, appliance_type
    return "Unknown", "Unknown"


def discover_total_pages(html: str) -> int:
    pages = [int(value) for value in PAGE_PATTERN.findall(html)]
    return max(pages) if pages else 1


def build_page_url(base_url: str, page: int) -> str:
    if page <= 1:
        return base_url
    joiner = "&" if "?" in base_url else "?"
    return f"{base_url}{joiner}n={page}"


def scrape_models(
    base_url: str,
    start_page: int,
    total_pages: int,
    delay: float,
    brand: str,
) -> Set[str]:
    models: Set[str] = set()
    for page in range(start_page, total_pages + 1):
        url = build_page_url(base_url, page)
        html = fetch_html(url)
        page_models = parse_models(html, brand)
        models.update(page_models)
        print(f"Page {page}/{total_pages}: {len(page_models)} models (total {len(models)})")
        if page < total_pages and delay:
            time.sleep(delay)
    return models


def main() -> None:
    args = parse_args()

    first_html = fetch_html(args.base_url)
    total_pages = args.pages or discover_total_pages(first_html)
    brand, appliance_type = parse_brand_type(first_html)
    models = set(parse_models(first_html, brand))

    if total_pages > 1:
        models.update(scrape_models(args.base_url, 2, total_pages, args.delay, brand))

    sorted_models = sorted(models)
    output = [
        {
            "brand": brand,
            "model_number": model,
            "appliance_type": appliance_type,
        }
        for model in sorted_models
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {len(sorted_models)} models to {args.output}")


if __name__ == "__main__":
    main()
