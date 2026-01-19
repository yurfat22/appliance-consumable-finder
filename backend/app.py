import os
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qsl, quote_plus, urlencode, urlparse, urlunparse

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

class Consumable(BaseModel):
    name: str
    type: str
    asin: Optional[str] = None
    sku: str
    notes: Optional[str] = None
    purchase_url: Optional[str] = None


class Appliance(BaseModel):
    model: str
    brand: str
    category: str
    consumables: List[Consumable]


class BrandGroup(BaseModel):
    brand: str
    appliances: List[Appliance]


class Contractor(BaseModel):
    name: str
    company: str
    phone: str
    email: EmailStr
    service_area: Optional[str] = None
    license: Optional[str] = None
    photo: Optional[str] = None
    bio: Optional[str] = None


class Suggestion(BaseModel):
    model_number: str
    brand: str
    category: str


load_dotenv(Path(__file__).parent / ".env")

IMAGE_DIR = Path(__file__).parent / "image"
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "public"
DATABASE_URL = os.getenv("DATABASE_URL")
AFFILIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG", "be3857-20")
DB_POOL: Optional[ConnectionPool] = None

app = FastAPI(title="Appliance Consumables API")

# Allow the Node UI (default localhost:3000) to talk to the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static assets (e.g., contractor photos) from /assets/*
app.mount("/assets", StaticFiles(directory=IMAGE_DIR), name="assets")


class CategoryGroup(BaseModel):
    category: str
    brands: List[BrandGroup]


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    zip_code: Optional[str] = None
    appliance_category: Optional[str] = None
    model: Optional[str] = None
    preferred_time: Optional[str] = None
    notes: Optional[str] = None


def add_amazon_affiliate_tag(url: Optional[str], tag: str) -> Optional[str]:
    if not url:
        return url
    cleaned = url.strip()
    if not cleaned:
        return None
    try:
        parsed = urlparse(cleaned)
    except ValueError:
        return cleaned
    if parsed.scheme not in ("http", "https"):
        return cleaned
    netloc = parsed.netloc.lower()
    if "amazon." not in netloc:
        return cleaned
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() != "tag"
    ]
    query_items.append(("tag", tag))
    new_query = urlencode(query_items, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def build_amazon_product_url(asin: str, tag: str) -> str:
    base_url = f"https://www.amazon.com/dp/{asin}"
    return add_amazon_affiliate_tag(base_url, tag) or base_url


def build_amazon_search_url(sku: str, tag: str) -> str:
    base_url = f"https://www.amazon.com/s?k={quote_plus(sku)}"
    return add_amazon_affiliate_tag(base_url, tag) or base_url


def apply_affiliate_links(appliances: List[Appliance]) -> None:
    for appliance in appliances:
        for item in appliance.consumables:
            if item.purchase_url:
                item.purchase_url = add_amazon_affiliate_tag(item.purchase_url, AFFILIATE_TAG)
            elif item.asin:
                item.purchase_url = build_amazon_product_url(item.asin, AFFILIATE_TAG)
            elif item.sku:
                item.purchase_url = build_amazon_search_url(item.sku, AFFILIATE_TAG)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
def startup() -> None:
    global DB_POOL
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required to run the API.")
    sslmode = os.getenv("PGSSLMODE", "require")
    DB_POOL = ConnectionPool(DATABASE_URL, kwargs={"sslmode": sslmode})


@app.on_event("shutdown")
def shutdown() -> None:
    if DB_POOL:
        DB_POOL.close()


def search_db(model_query: str) -> List[Appliance]:
    if not DB_POOL:
        raise RuntimeError("Database pool is not initialized.")

    with DB_POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.id, m.model_number, b.name, c.name
                FROM models m
                JOIN brands b ON m.brand_id = b.id
                JOIN categories c ON m.category_id = c.id
                WHERE LOWER(m.model_number) LIKE %s
                  AND COALESCE(m.water_filter_missing, false) = false
                ORDER BY b.name, m.model_number
                """,
                (f"%{model_query.lower()}%",),
            )
            rows = cur.fetchall()
            if not rows:
                return []

            appliances: List[Appliance] = []
            model_index: dict[int, int] = {}
            model_ids: List[int] = []
            for row in rows:
                model_id = row[0]
                model_ids.append(model_id)
                model_index[model_id] = len(appliances)
                appliances.append(
                    Appliance(
                        model=row[1],
                        brand=row[2],
                        category=row[3],
                        consumables=[],
                    )
                )

            cur.execute(
                """
                SELECT mc.model_id, c.name, c.type, c.asin, c.sku, mc.notes, c.purchase_url
                FROM model_consumables mc
                JOIN consumables c ON mc.consumable_id = c.id
                WHERE mc.model_id = ANY(%s)
                ORDER BY c.name
                """,
                (model_ids,),
            )
            for row in cur.fetchall():
                model_id = row[0]
                idx = model_index.get(model_id)
                if idx is None:
                    continue
                appliances[idx].consumables.append(
                    Consumable(
                        name=row[1],
                        type=row[2],
                        asin=row[3],
                        sku=row[4],
                        notes=row[5],
                        purchase_url=row[6],
                    )
                )

            apply_affiliate_links(appliances)
            return appliances


def get_suggestions_db(query: str, limit: int) -> List[Suggestion]:
    """Fetch autocomplete suggestions using prefix + trigram similarity matching."""
    if not DB_POOL:
        raise RuntimeError("Database pool is not initialized.")

    with DB_POOL.connection() as conn:
        with conn.cursor() as cur:
            # Combined query: prioritizes prefix > contains > trigram similarity
            cur.execute(
                """
                WITH scored_models AS (
                    SELECT DISTINCT ON (m.model_number)
                        m.model_number,
                        b.name AS brand,
                        c.name AS category,
                        CASE
                            WHEN LOWER(m.model_number) LIKE %s THEN 1.0
                            WHEN LOWER(m.model_number) LIKE %s THEN 0.8
                            ELSE SIMILARITY(LOWER(m.model_number), %s)
                        END AS score
                    FROM models m
                    JOIN brands b ON m.brand_id = b.id
                    JOIN categories c ON m.category_id = c.id
                    WHERE COALESCE(m.water_filter_missing, false) = false
                      AND (
                          LOWER(m.model_number) LIKE %s
                          OR LOWER(m.model_number) LIKE %s
                          OR SIMILARITY(LOWER(m.model_number), %s) > 0.2
                      )
                )
                SELECT model_number, brand, category, score
                FROM scored_models
                WHERE score > 0.2
                ORDER BY score DESC, model_number ASC
                LIMIT %s
                """,
                (
                    f"{query}%",   # prefix match (score 1.0)
                    f"%{query}%",  # contains match (score 0.8)
                    query,         # similarity score
                    f"{query}%",   # WHERE prefix
                    f"%{query}%",  # WHERE contains
                    query,         # WHERE similarity
                    limit,
                ),
            )

            return [
                Suggestion(model_number=row[0], brand=row[1], category=row[2])
                for row in cur.fetchall()
            ]


def list_categories_db() -> List[CategoryGroup]:
    if not DB_POOL:
        raise RuntimeError("Database pool is not initialized.")

    with DB_POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.id, m.model_number, b.name, c.name
                FROM models m
                JOIN brands b ON m.brand_id = b.id
                JOIN categories c ON m.category_id = c.id
                WHERE COALESCE(m.water_filter_missing, false) = false
                ORDER BY c.name, b.name, m.model_number
                """
            )
            rows = cur.fetchall()
            if not rows:
                return []

            appliances: List[Appliance] = []
            model_index: dict[int, int] = {}
            model_ids: List[int] = []
            for row in rows:
                model_id = row[0]
                model_ids.append(model_id)
                model_index[model_id] = len(appliances)
                appliances.append(
                    Appliance(
                        model=row[1],
                        brand=row[2],
                        category=row[3],
                        consumables=[],
                    )
                )

            cur.execute(
                """
                SELECT mc.model_id, c.name, c.type, c.asin, c.sku, mc.notes, c.purchase_url
                FROM model_consumables mc
                JOIN consumables c ON mc.consumable_id = c.id
                WHERE mc.model_id = ANY(%s)
                ORDER BY c.name
                """,
                (model_ids,),
            )
            for row in cur.fetchall():
                model_id = row[0]
                idx = model_index.get(model_id)
                if idx is None:
                    continue
                appliances[idx].consumables.append(
                    Consumable(
                        name=row[1],
                        type=row[2],
                        asin=row[3],
                        sku=row[4],
                        notes=row[5],
                        purchase_url=row[6],
                    )
                )

    apply_affiliate_links(appliances)
    categories: dict[str, dict[str, List[Appliance]]] = {}
    for appliance in appliances:
        cat = categories.setdefault(appliance.category, {})
        cat.setdefault(appliance.brand, []).append(appliance)

    grouped: List[CategoryGroup] = []
    for category, brand_map in sorted(categories.items()):
        brands = [
            BrandGroup(brand=brand, appliances=items)
            for brand, items in sorted(brand_map.items())
        ]
        grouped.append(CategoryGroup(category=category, brands=brands))

    return grouped


@app.get("/api/consumables", response_model=List[Appliance])
def search(model: str = Query(..., description="Appliance model number")) -> List[Appliance]:
    model_query = model.strip().lower()
    if not model_query:
        raise HTTPException(status_code=400, detail="Model query cannot be empty.")

    matches = search_db(model_query)

    if not matches:
        raise HTTPException(status_code=404, detail="No consumables found for that model.")

    return matches


@app.get("/api/suggestions", response_model=List[Suggestion])
def suggestions(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=15, description="Max suggestions"),
) -> List[Suggestion]:
    """Return autocomplete suggestions with fuzzy matching."""
    query = q.strip().lower()
    if len(query) < 2:
        return []
    return get_suggestions_db(query, limit)


@app.get("/api/categories", response_model=List[CategoryGroup])
def list_categories() -> List[CategoryGroup]:
    return list_categories_db()


@app.get("/api/contractor", response_model=Contractor)
def get_contractor() -> Contractor:
    if not DB_POOL:
        raise RuntimeError("Database pool is not initialized.")

    with DB_POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, company, phone, email, service_area, license, photo, bio
                FROM contractors
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Contractor profile not found.")
            return Contractor(
                name=row[0],
                company=row[1],
                phone=row[2],
                email=row[3],
                service_area=row[4],
                license=row[5],
                photo=row[6],
                bio=row[7],
            )


@app.post("/api/contact")
def submit_contact(request: ContactRequest) -> dict:
    # In a real app this would enqueue to a CRM/email/SMS. For now we log it.
    print("Contact request received:", request.model_dump())
    return {"status": "received", "message": "A local pro will reach out soon."}


@app.get("/config.js")
def config(request: Request) -> Response:
    base_url = str(request.base_url).rstrip("/")
    return Response(
        f'window.API_BASE_URL = "{base_url}";',
        media_type="application/javascript",
    )


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
